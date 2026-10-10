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
