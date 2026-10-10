import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.main import app
from app.db.session import Base, get_db
from app.db.seed import seed_database
from app.services.ledger import LedgerService
from app.services.duplicate_engine import haversine_distance_meters
from app.services.export_service import ExportService
from app.models.entities import Case, User, UserRole

# Use memory or dedicated test sqlite db
SQLALCHEMY_DATABASE_URL = "sqlite:///./test_civictrace.db"
test_engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)

@pytest.fixture(scope="session", autouse=True)
def setup_test_db():
    Base.metadata.drop_all(bind=test_engine)
    Base.metadata.create_all(bind=test_engine)
    yield
    Base.metadata.drop_all(bind=test_engine)

@pytest.fixture
def db_session():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()

@pytest.fixture
def client(db_session):
    def override_get_db():
        try:
            yield db_session
        finally:
            pass
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()

def test_health_check(client):
    res = client.get("/health")
    assert res.status_code == 200
    assert res.json()["status"] == "healthy"

def test_haversine_formula():
    # Rajwada to Chhappan Dukan in Indore is ~2.6 km
    d = haversine_distance_meters(22.7188, 75.8562, 22.7231, 75.8812)
    assert 2400 < d < 2800

def test_append_only_ledger_hash_chaining(db_session):
    # Create test case
    case = Case(
        public_id="TEST-CAS-001",
        category_id="fake-cat",
        title="Test Ledger Broken Light",
        description="Testing cryptographic chain",
        latitude=22.7,
        longitude=75.8,
        priority_score=2.0,
    )
    db_session.add(case)
    db_session.commit()

    # Append 3 events
    e1 = LedgerService.append_event(db_session, case, "REPORT_CREATED", {"detail": "Initial report"})
    e2 = LedgerService.append_event(db_session, case, "INVESTIGATION_STARTED", {"officer": "Team A"})
    e3 = LedgerService.append_event(db_session, case, "RESOLUTION_CLAIMED", {"work": "Fixed bulb"})
    db_session.commit()

    # Verify chain
    is_valid, count, err, latest_hash = LedgerService.verify_chain(db_session, case.id)
    assert is_valid is True
    assert count == 3
    assert err is None
    assert latest_hash == e3.current_event_hash

    # TAMPER TEST: Modify payload of event 2 directly in the database
    e2.payload_json = '{"tampered": "illegal change"}'
    db_session.commit()

    # Re-verify should detect tampering immediately
    is_valid_after_tamper, _, tamper_err, _ = LedgerService.verify_chain(db_session, case.id)
    assert is_valid_after_tamper is False
    assert "tampering detected" in tamper_err

def test_export_package_and_manifest_tamper_detection(db_session):
    case = Case(
        public_id="TEST-EXP-001",
        category_id="cat-exp",
        title="Export Test Case",
        description="Testing ZIP export manifest",
        latitude=22.7,
        longitude=75.8,
        priority_score=1.5,
    )
    db_session.add(case)
    db_session.commit()

    LedgerService.append_event(db_session, case, "REPORT_CREATED", {"title": "Export issue"})
    db_session.commit()

    zip_path = ExportService.generate_case_export_package(db_session, case.id)
    assert zip_path.endswith(".zip")

    # Verify valid package
    is_valid, logs = ExportService.verify_export_package(zip_path)
    assert is_valid is True
    assert any("SUCCESS" in l for l in logs)
