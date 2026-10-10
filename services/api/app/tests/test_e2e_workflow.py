import pytest
import os
import zipfile
import json
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.main import app
from app.db.session import Base, get_db
from app.models.entities import User, UserRole, IssueCategory, Case, Report, CaseState
from app.services.export_service import ExportService
from app.core.security import get_password_hash, create_access_token

TEST_DB_URL = "sqlite:///./test_e2e_civictrace.db"
e2e_engine = create_engine(TEST_DB_URL, connect_args={"check_same_thread": False})
TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=e2e_engine)

@pytest.fixture(scope="module")
def setup_db():
    Base.metadata.drop_all(bind=e2e_engine)
    Base.metadata.create_all(bind=e2e_engine)
    yield
    Base.metadata.drop_all(bind=e2e_engine)

@pytest.fixture
def session(setup_db):
    db = TestingSession()
    try:
        yield db
    finally:
        db.close()

@pytest.fixture
def client(session):
    def override_get_db():
        try:
            yield session
        finally:
            pass
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()

def test_full_civic_accountability_lifecycle_e2e(client, session):
    # 1. Setup seed category & roles
    cat = IssueCategory(
        name="Pothole Test Category",
        code="TEST_POTHOLE",
        description="Damaged road for e2e testing",
        default_severity_weight=2.5,
    )
    reviewer = User(
        email="test_reviewer@civictrace.local",
        hashed_password=get_password_hash("pass"),
        display_name="Test Reviewer",
        role=UserRole.REVIEWER,
    )
    operator = User(
        email="test_operator@civictrace.local",
        hashed_password=get_password_hash("pass"),
        display_name="Test Operator",
        role=UserRole.OPERATOR,
    )
    citizen = User(
        email="test_citizen@civictrace.local",
        hashed_password=get_password_hash("pass"),
        display_name="Test Citizen",
        role=UserRole.CITIZEN,
    )
    session.add_all([cat, reviewer, operator, citizen])
    session.commit()

    token_reviewer = create_access_token(reviewer.id)
    token_operator = create_access_token(operator.id)
    token_citizen = create_access_token(citizen.id)

    # 2. Citizen reports an issue
    rpt_payload = {
        "category_id": cat.id,
        "title": "Severe road cavity on Central MG Road",
        "description": "Large hole causing scooter accidents during evening transit",
        "latitude": 22.7188,
        "longitude": 75.8562,
        "address_reference": "MG Road near Rajwada",
        "guest_pseudonym": "Concerned Resident",
    }
    r1 = client.post("/api/v1/reports", json=rpt_payload, headers={"Authorization": f"Bearer {token_citizen}"})
    assert r1.status_code == 201
    created_report = r1.json()
    case_id = created_report["case_id"]
    assert case_id is not None

    # Verify initial case was automatically established in SUBMITTED state
    c_res = client.get(f"/api/v1/cases/{case_id}")
    assert c_res.status_code == 200
    case_data = c_res.json()
    assert case_data["state"] == "SUBMITTED"

    # 3. Reviewer reviews and verifies case
    v_res = client.post(
        f"/api/v1/cases/{case_id}/transition?target_state=VERIFIED&notes=Ground%20corroboration%20confirmed",
        headers={"Authorization": f"Bearer {token_reviewer}"},
    )
    assert v_res.status_code == 200
    assert v_res.json()["state"] == "VERIFIED"

    # 4. Department Operator starts work and claims resolution
    trans_prog = client.post(
        f"/api/v1/cases/{case_id}/transition?target_state=IN_PROGRESS&notes=Crew%20dispatched",
        headers={"Authorization": f"Bearer {token_operator}"},
    )
    assert trans_prog.status_code == 200

    claim_payload = {
        "work_summary": "Asphalt patch applied and compacted using steam roller",
        "actions_taken": "Replaced aggregate base, laid bitumen hot mix, leveled surface",
    }
    claim_res = client.post(
        f"/api/v1/cases/{case_id}/claims",
        json=claim_payload,
        headers={"Authorization": f"Bearer {token_operator}"},
    )
    assert claim_res.status_code == 200

    # Ensure case is now AWAITING_VERIFICATION (not prematurely resolved!)
    case_after_claim = client.get(f"/api/v1/cases/{case_id}").json()
    assert case_after_claim["state"] == "AWAITING_VERIFICATION"

    # 5. Citizen Dispute Scenario:
    # Citizen checks on site, finds pothole still open, submits STILL_UNRESOLVED dispute
    dispute_payload = {
        "outcome": "STILL_UNRESOLVED",
        "notes": "Visited location at 7 PM. Hole is merely covered in loose gravel which is already shifting.",
        "guest_pseudonym": "Local Commuter Aarav",
    }
    disp_res = client.post(
        f"/api/v1/cases/{case_id}/verifications",
        json=dispute_payload,
        headers={"Authorization": f"Bearer {token_citizen}"},
    )
    assert disp_res.status_code == 200
    assert disp_res.json()["is_dispute"] is True

    # Case must transition to DISPUTED
    case_after_disp = client.get(f"/api/v1/cases/{case_id}").json()
    assert case_after_disp["state"] == "DISPUTED"

    # 6. Verify cryptographic hash chain of ledger events
    ledger_res = client.get(f"/api/v1/cases/{case_id}/events/verify")
    assert ledger_res.status_code == 200
    ledger_status = ledger_res.json()
    assert ledger_status["is_valid"] is True
    assert ledger_status["total_events"] >= 4

    # 7. Operator CANNOT verify their own resolution claim (RBAC & Conflict-of-Interest Guard)
    invalid_op_verif = client.post(
        f"/api/v1/cases/{case_id}/verifications",
        json={"outcome": "CONFIRMED_FIXED", "notes": "Self verification attempt"},
        headers={"Authorization": f"Bearer {token_operator}"},
    )
    assert invalid_op_verif.status_code == 403

    # 8. Export ZIP evidence package and verify manifest
    export_res = client.get(f"/api/v1/cases/{case_id}/export")
    assert export_res.status_code == 200
    assert export_res.headers["content-type"] == "application/zip"

    # 9. Verify package integrity
    # Save temp zip to test verifier
    temp_zip = f"temp_test_export_{case_data['public_id']}.zip"
    with open(temp_zip, "wb") as f:
        f.write(export_res.content)

    is_valid_export, logs = ExportService.verify_export_package(temp_zip)
    assert is_valid_export is True

    # Tamper test on export package: modify observations.json
    with zipfile.ZipFile(temp_zip, "a") as zf:
        zf.writestr("observations.json", "TAMPERED DATA PAYLOAD")

    is_valid_after_tamper, tamper_logs = ExportService.verify_export_package(temp_zip)
    assert is_valid_after_tamper is False
    assert any("TAMPER DETECTED" in l for l in tamper_logs)

    # Cleanup temp test file
    if os.path.exists(temp_zip):
        os.remove(temp_zip)
