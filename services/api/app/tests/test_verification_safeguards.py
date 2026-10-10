import pytest
from app.models.entities import Case, User, UserRole, CaseState, VerificationOutcome, IssueCategory
from app.services.verification_policy import VerificationPolicyEngine
from app.services.state_machine import CaseStateMachine

def test_operator_blocked_from_self_verification(db_session):
    cat = IssueCategory(name="Test Lights", code="TL01", default_severity_weight=2.0)
    op = User(email="op@civictrace.local", hashed_password="p", display_name="Op", role=UserRole.OPERATOR)
    case = Case(public_id="TEST-V-01", category=cat, title="Light Out", description="Dark street", latitude=22.7, longitude=75.8, state=CaseState.AWAITING_VERIFICATION)
    db_session.add_all([cat, op, case])
    db_session.commit()

    with pytest.raises(PermissionError) as exc_info:
        VerificationPolicyEngine.evaluate_verification_submission(
            db=db_session,
            case=case,
            user=op,
            outcome=VerificationOutcome.CONFIRMED_FIXED,
            notes="I checked my own repair",
        )
    assert "Department operators cannot submit independent verification observations" in str(exc_info.value)

def test_dispute_triggers_disputed_state(db_session):
    cat = IssueCategory(name="Test Water", code="TW01", default_severity_weight=2.5)
    citizen = User(email="c1@civictrace.local", hashed_password="p", display_name="Citizen 1", role=UserRole.CITIZEN)
    case = Case(public_id="TEST-V-02", category=cat, title="Pipe Leak", description="Water pipe broken", latitude=22.7, longitude=75.8, state=CaseState.AWAITING_VERIFICATION)
    db_session.add_all([cat, citizen, case])
    db_session.commit()

    target_state, event_type, actor = VerificationPolicyEngine.evaluate_verification_submission(
        db=db_session,
        case=case,
        user=citizen,
        outcome=VerificationOutcome.STILL_UNRESOLVED,
        notes="Water is still actively flooding street",
    )
    assert target_state == CaseState.DISPUTED
    assert event_type == "RESOLUTION_DISPUTED"
    assert actor == "Citizen 1"

def test_quorum_confirmation_and_identity_deduplication(db_session):
    cat = IssueCategory(name="Test Road", code="TR01", default_severity_weight=2.5)
    citizen1 = User(email="cit1@civictrace.local", hashed_password="p", display_name="Cit 1", role=UserRole.CITIZEN)
    citizen2 = User(email="cit2@civictrace.local", hashed_password="p", display_name="Cit 2", role=UserRole.CITIZEN)
    case = Case(public_id="TEST-V-03", category=cat, title="Pothole Fixed?", description="Pothole repair claimed", latitude=22.7, longitude=75.8, state=CaseState.AWAITING_VERIFICATION)
    db_session.add_all([cat, citizen1, citizen2, case])
    db_session.commit()

    # First citizen confirmation: Quorum requires 2, so should remain AWAITING_VERIFICATION
    st1, evt1, _ = VerificationPolicyEngine.evaluate_verification_submission(
        db=db_session,
        case=case,
        user=citizen1,
        outcome=VerificationOutcome.CONFIRMED_FIXED,
        notes="Looks smooth to me",
    )
    assert st1 == CaseState.AWAITING_VERIFICATION
    assert evt1 == "VERIFICATION_CONFIRMATION_LOGGED"

    # Anti-sybil check: Citizen 1 trying to cast a second vote on the same case
    # Fake recording the first observation in DB
    from app.models.entities import VerificationObservation
    obs1 = VerificationObservation(case_id=case.id, verifier_id=citizen1.id, outcome=VerificationOutcome.CONFIRMED_FIXED, notes="Looks smooth")
    db_session.add(obs1)
    db_session.commit()

    with pytest.raises(ValueError) as dup_err:
        VerificationPolicyEngine.evaluate_verification_submission(
            db=db_session,
            case=case,
            user=citizen1,
            outcome=VerificationOutcome.CONFIRMED_FIXED,
            notes="Second confirmation attempt",
        )
    assert "already submitted a verification observation" in str(dup_err.value)

    # Second distinct citizen confirmation: Reaches quorum of 2, transitioning to RESOLVED
    st2, evt2, _ = VerificationPolicyEngine.evaluate_verification_submission(
        db=db_session,
        case=case,
        user=citizen2,
        outcome=VerificationOutcome.CONFIRMED_FIXED,
        notes="Second independent check confirms road is level",
    )
    assert st2 == CaseState.RESOLVED
    assert evt2 == "RESOLUTION_VERIFIED_AND_CLOSED"

def test_unauthorized_state_transition_blocked():
    # Citizen cannot arbitrarily transition case to RESOLVED without verification workflow
    can_trans, err = CaseStateMachine.can_transition(
        current_state=CaseState.IN_PROGRESS,
        target_state=CaseState.RESOLVED,
        role=UserRole.CITIZEN
    )
    assert can_trans is False

    # Operator cannot self-resolve a case directly
    can_trans_op, err_op = CaseStateMachine.can_transition(
        current_state=CaseState.AWAITING_VERIFICATION,
        target_state=CaseState.RESOLVED,
        role=UserRole.OPERATOR
    )
    assert can_trans_op is False
    assert "not authorized" in err_op
