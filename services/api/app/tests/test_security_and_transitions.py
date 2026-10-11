import pytest
from app.models.entities import User, UserRole, Report, Case, IssueCategory
from app.api.v1.endpoints.reports import validate_magic_bytes
from app.core.sequences import allocate_report_public_id
from app.core.rate_limiter import check_rate_limit, reset_rate_limits
from app.services.state_machine import CaseStateMachine, CaseState
from fastapi import HTTPException

def test_magic_bytes_detection():
    # Valid JPEG
    valid_jpg = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00"
    assert validate_magic_bytes(valid_jpg, "image/jpeg") is True
    # Spoofed JPEG (actually plaintext executable or script)
    assert validate_magic_bytes(b"#!/bin/bash\necho bad", "image/jpeg") is False

    # Valid PNG
    valid_png = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR"
    assert validate_magic_bytes(valid_png, "image/png") is True
    assert validate_magic_bytes(b"GIF89a", "image/png") is False

    # Valid PDF
    valid_pdf = b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n"
    assert validate_magic_bytes(valid_pdf, "application/pdf") is True
    assert validate_magic_bytes(b"<!DOCTYPE html>", "application/pdf") is False

def test_collision_resistant_monotonic_sequence_allocators(db_session):
    cat = IssueCategory(name="Seq Cat", code="SEQ01", default_severity_weight=1.0)
    db_session.add(cat)
    db_session.commit()

    id1 = allocate_report_public_id(db_session, year=2026)
    assert id1.startswith("RPT-2026-")

    r1 = Report(
        public_id=id1,
        category_id=cat.id,
        title="Test report 1",
        description="Description 1",
        latitude=22.7,
        longitude=75.8,
    )
    db_session.add(r1)
    db_session.commit()

    id2 = allocate_report_public_id(db_session, year=2026)
    assert id2 != id1
    num1 = int(id1.split("-")[-1])
    num2 = int(id2.split("-")[-1])
    assert num2 > num1

def test_atomic_state_machine_transition_with_ledger(db_session):
    cat = IssueCategory(name="SM Cat", code="SM01", default_severity_weight=2.0)
    reviewer = User(email="rev_sm@civictrace.local", hashed_password="p", display_name="Rev SM", role=UserRole.REVIEWER)
    case = Case(
        public_id="TEST-SM-001",
        category=cat,
        title="Pothole SM Test",
        description="Testing atomic transition",
        latitude=22.7,
        longitude=75.8,
        state=CaseState.SUBMITTED,
    )
    db_session.add_all([cat, reviewer, case])
    db_session.commit()

    updated = CaseStateMachine.transition_case(
        db=db_session,
        case=case,
        target_state=CaseState.VERIFIED,
        actor=reviewer,
        notes="Field verified by community reviewer",
    )
    assert updated.state == CaseState.VERIFIED
    assert updated.verified_at is not None

    # Verify that ledger event was atomically appended
    assert len(case.events) == 1
    assert case.events[0].event_type == "STATE_CHANGED_TO_VERIFIED"
    assert case.events[0].public_actor_label == "Community Reviewer"

def test_rate_limiter_enforcement():
    reset_rate_limits()
    class DummyClient:
        host = "192.168.1.100"
    class DummyRequest:
        client = DummyClient()

    req = DummyRequest()
    # 5 requests with max 5 should succeed
    for _ in range(5):
        check_rate_limit(req, max_requests=5, window_seconds=10, action_key="test_act")

    # 6th request should fail with 429
    with pytest.raises(HTTPException) as exc:
        check_rate_limit(req, max_requests=5, window_seconds=10, action_key="test_act")
    assert exc.value.status_code == 429
    assert "Rate limit exceeded" in str(exc.value.detail)


def test_unapproved_evidence_download_protection(client, db_session):
    import os
    from app.models.entities import EvidenceAsset, ReportModerationStatus
    from app.core.security import create_access_token
    from app.core.config import settings

    cat = IssueCategory(name="Evidence Test Cat", code="ETC01", default_severity_weight=1.5)
    cit_owner = User(email="owner@civictrace.local", hashed_password="p", display_name="Owner Citizen", role=UserRole.CITIZEN)
    cit_other = User(email="other@civictrace.local", hashed_password="p", display_name="Other Citizen", role=UserRole.CITIZEN)
    reviewer = User(email="rev_evid@civictrace.local", hashed_password="p", display_name="Reviewer Evid", role=UserRole.REVIEWER)
    db_session.add_all([cat, cit_owner, cit_other, reviewer])
    db_session.commit()

    # Create report with PENDING moderation status
    report = Report(
        public_id="RPT-TEST-EVID-001",
        category_id=cat.id,
        reporter_id=cit_owner.id,
        title="Pending issue with sensitive evidence",
        description="Private description awaiting approval",
        latitude=22.7,
        longitude=75.8,
        moderation_status=ReportModerationStatus.PENDING,
    )
    db_session.add(report)
    db_session.commit()

    # Create test evidence file on disk
    test_file_path = os.path.join(settings.UPLOAD_DIR, "test_pending_evidence.jpg")
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    with open(test_file_path, "wb") as f:
        f.write(b"\xff\xd8\xff\xe0\x00\x10JFIF\x00test-evidence-payload")

    asset = EvidenceAsset(
        report_id=report.id,
        file_name="pending_photo.jpg",
        file_path=test_file_path,
        file_size=32,
        mime_type="image/jpeg",
        sha256_hash="dummyhash123",
        is_public=False,
    )
    db_session.add(asset)
    db_session.commit()

    download_url = f"/api/v1/reports/evidence/{asset.id}/download"

    # 1. Anonymous public download must be rejected with 401
    anon_resp = client.get(download_url)
    assert anon_resp.status_code == 401
    assert "Authentication required" in anon_resp.json()["detail"]

    # 2. Unrelated citizen download must be rejected with 403
    other_token = create_access_token(cit_other.id)
    other_resp = client.get(download_url, headers={"Authorization": f"Bearer {other_token}"})
    assert other_resp.status_code == 403
    assert "Access denied" in other_resp.json()["detail"]

    # 3. Owner citizen can download their own pending evidence
    owner_token = create_access_token(cit_owner.id)
    owner_resp = client.get(download_url, headers={"Authorization": f"Bearer {owner_token}"})
    assert owner_resp.status_code == 200

    # 4. Reviewer can download pending evidence for review
    rev_token = create_access_token(reviewer.id)
    rev_resp = client.get(download_url, headers={"Authorization": f"Bearer {rev_token}"})
    assert rev_resp.status_code == 200

    # 5. When reviewer approves the report, evidence becomes publicly accessible
    mod_resp = client.post(
        f"/api/v1/reports/{report.id}/moderate",
        headers={"Authorization": f"Bearer {rev_token}"},
        json={"decision": "APPROVED", "notes": "Approved for public visibility"},
    )
    assert mod_resp.status_code == 200

    # Refresh asset state
    db_session.refresh(asset)
    assert asset.is_public is True

    # Anonymous download now succeeds (200 OK)
    anon_approved_resp = client.get(download_url)
    assert anon_approved_resp.status_code == 200

    # Clean up test file
    if os.path.exists(test_file_path):
        os.remove(test_file_path)
