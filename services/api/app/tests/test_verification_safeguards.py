import pytest
from app.models.entities import (
    Case,
    User,
    UserRole,
    CaseState,
    VerificationOutcome,
    IssueCategory,
    ResolutionClaim,
    VerificationObservation,
)
from app.services.verification_policy import VerificationPolicyEngine
from app.services.state_machine import CaseStateMachine


def test_operator_blocked_from_self_verification(db_session):
    cat = IssueCategory(name="Test Lights", code="TL01", default_severity_weight=2.0)
    op = User(
        email="op@civictrace.local", hashed_password="p", display_name="Op", role=UserRole.OPERATOR
    )
    case = Case(
        public_id="TEST-V-01",
        category=cat,
        title="Light Out",
        description="Dark street",
        latitude=22.7,
        longitude=75.8,
        state=CaseState.AWAITING_VERIFICATION,
    )
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
    assert "Department operators cannot submit independent verification observations" in str(
        exc_info.value
    )


def test_dispute_triggers_disputed_state(db_session):
    cat = IssueCategory(name="Test Water", code="TW01", default_severity_weight=2.5)
    citizen = User(
        email="c1@civictrace.local",
        hashed_password="p",
        display_name="Citizen 1",
        role=UserRole.CITIZEN,
    )
    case = Case(
        public_id="TEST-V-02",
        category=cat,
        title="Pipe Leak",
        description="Water pipe broken",
        latitude=22.7,
        longitude=75.8,
        state=CaseState.AWAITING_VERIFICATION,
    )
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
    citizen1 = User(
        email="cit1@civictrace.local",
        hashed_password="p",
        display_name="Cit 1",
        role=UserRole.CITIZEN,
    )
    citizen2 = User(
        email="cit2@civictrace.local",
        hashed_password="p",
        display_name="Cit 2",
        role=UserRole.CITIZEN,
    )
    case = Case(
        public_id="TEST-V-03",
        category=cat,
        title="Pothole Fixed?",
        description="Pothole repair claimed",
        latitude=22.7,
        longitude=75.8,
        state=CaseState.AWAITING_VERIFICATION,
    )
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

    obs1 = VerificationObservation(
        case_id=case.id,
        verifier_id=citizen1.id,
        outcome=VerificationOutcome.CONFIRMED_FIXED,
        notes="Looks smooth",
    )
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
        current_state=CaseState.IN_PROGRESS, target_state=CaseState.RESOLVED, role=UserRole.CITIZEN
    )
    assert can_trans is False

    # Operator cannot self-resolve a case directly
    can_trans_op, err_op = CaseStateMachine.can_transition(
        current_state=CaseState.AWAITING_VERIFICATION,
        target_state=CaseState.RESOLVED,
        role=UserRole.OPERATOR,
    )
    assert can_trans_op is False
    assert "not authorized" in err_op


def test_stale_observations_scoped_to_claim_cycle(db_session):
    from app.models.entities import ResolutionClaim, VerificationObservation

    cat = IssueCategory(name="Test Sanitation", code="TS01", default_severity_weight=2.0)
    op = User(
        email="op1@civictrace.local",
        hashed_password="p",
        display_name="Op 1",
        role=UserRole.OPERATOR,
    )
    cit1 = User(
        email="cit1_cycle@civictrace.local",
        hashed_password="p",
        display_name="Cit 1",
        role=UserRole.CITIZEN,
    )
    cit2 = User(
        email="cit2_cycle@civictrace.local",
        hashed_password="p",
        display_name="Cit 2",
        role=UserRole.CITIZEN,
    )
    case = Case(
        public_id="TEST-V-CYCLE",
        category=cat,
        title="Garbage Overflow",
        description="Waste pile",
        latitude=22.7,
        longitude=75.8,
        state=CaseState.AWAITING_VERIFICATION,
    )
    db_session.add_all([cat, op, cit1, cit2, case])
    db_session.commit()

    # Operator claims resolution (Claim 1)
    claim1 = ResolutionClaim(
        case_id=case.id,
        operator_id=op.id,
        work_summary="Cleared garbage initial attempt",
        actions_taken="Collected trash",
        status="AWAITING_VERIFICATION",
    )
    db_session.add(claim1)
    db_session.commit()

    # Citizen 1 confirms fixed on Claim 1 (Quorum not reached yet, need 2)
    st1, _, _ = VerificationPolicyEngine.evaluate_verification_submission(
        db=db_session,
        case=case,
        user=cit1,
        outcome=VerificationOutcome.CONFIRMED_FIXED,
        notes="First check",
        active_claim=claim1,
    )
    assert st1 == CaseState.AWAITING_VERIFICATION
    obs1 = VerificationObservation(
        case_id=case.id,
        resolution_claim_id=claim1.id,
        verifier_id=cit1.id,
        outcome=VerificationOutcome.CONFIRMED_FIXED,
        notes="First check",
    )
    db_session.add(obs1)
    db_session.commit()

    # Citizen 2 discovers trash is still there and disputes it -> Claim 1 is disputed, case is DISPUTED
    st_disp, _, _ = VerificationPolicyEngine.evaluate_verification_submission(
        db=db_session,
        case=case,
        user=cit2,
        outcome=VerificationOutcome.STILL_UNRESOLVED,
        notes="Still full of trash",
        active_claim=claim1,
    )
    assert st_disp == CaseState.DISPUTED
    assert claim1.status == "DISPUTED"
    obs_disp = VerificationObservation(
        case_id=case.id,
        resolution_claim_id=claim1.id,
        verifier_id=cit2.id,
        outcome=VerificationOutcome.STILL_UNRESOLVED,
        notes="Still full",
        is_dispute=True,
    )
    case.state = CaseState.DISPUTED
    db_session.add(obs_disp)
    db_session.commit()

    # Operator performs actual rework and submits a NEW repair claim (Claim 2)
    claim2 = ResolutionClaim(
        case_id=case.id,
        operator_id=op.id,
        work_summary="Cleaned completely second attempt with truck",
        actions_taken="Deep cleaning",
        status="AWAITING_VERIFICATION",
    )
    case.state = CaseState.AWAITING_VERIFICATION
    db_session.add(claim2)
    db_session.commit()

    # CRITICAL CHECK: Citizen 1 (who previously confirmed Claim 1) must NOT be blocked from confirming the NEW Claim 2
    # And their new confirmation on Claim 2 must NOT combine with the stale confirmation on Claim 1 to prematurely resolve!
    st_new_1, _, _ = VerificationPolicyEngine.evaluate_verification_submission(
        db=db_session,
        case=case,
        user=cit1,
        outcome=VerificationOutcome.CONFIRMED_FIXED,
        notes="Re-checked after new rework",
        active_claim=claim2,
    )
    # Total on Claim 2 is only 1 (stale Claim 1 confirmation is excluded). Case must remain AWAITING_VERIFICATION!
    assert st_new_1 == CaseState.AWAITING_VERIFICATION
    obs_new_1 = VerificationObservation(
        case_id=case.id,
        resolution_claim_id=claim2.id,
        verifier_id=cit1.id,
        outcome=VerificationOutcome.CONFIRMED_FIXED,
        notes="Re-checked",
    )
    db_session.add(obs_new_1)
    db_session.commit()

    # Citizen 2 now also checks and confirms fixed on Claim 2 -> Now quorum of 2 is reached on Claim 2!
    st_new_2, _, _ = VerificationPolicyEngine.evaluate_verification_submission(
        db=db_session,
        case=case,
        user=cit2,
        outcome=VerificationOutcome.CONFIRMED_FIXED,
        notes="Checked second time, now clean",
        active_claim=claim2,
    )
    assert st_new_2 == CaseState.RESOLVED
    assert claim2.status == "VERIFIED"


def test_dispute_cannot_be_overridden_by_later_confirmations(db_session):
    """
    Issue 03 Regression Test:
    Sequence: CONFIRMED_FIXED -> STILL_UNRESOLVED (dispute) -> CONFIRMED_FIXED
    Once an active claim is disputed, further confirmations must NOT auto-resolve the case.
    The case must remain DISPUTED until explicit Reviewer/Admin adjudication or rework cycle.
    """
    cat = IssueCategory(name="Drainage Test", code="DR01", default_severity_weight=2.0)
    op = User(
        email="op_drain@civictrace.local",
        hashed_password="p",
        display_name="Drain Op",
        role=UserRole.OPERATOR,
    )
    cit1 = User(
        email="c_seq1@civictrace.local",
        hashed_password="p",
        display_name="Seq Cit 1",
        role=UserRole.CITIZEN,
    )
    cit2 = User(
        email="c_seq2@civictrace.local",
        hashed_password="p",
        display_name="Seq Cit 2",
        role=UserRole.CITIZEN,
    )
    cit3 = User(
        email="c_seq3@civictrace.local",
        hashed_password="p",
        display_name="Seq Cit 3",
        role=UserRole.CITIZEN,
    )
    case = Case(
        public_id="TEST-SEQ-01",
        category=cat,
        title="Blocked Sump",
        description="Drain blocked",
        latitude=22.7,
        longitude=75.8,
        state=CaseState.AWAITING_VERIFICATION,
    )
    db_session.add_all([cat, op, cit1, cit2, cit3, case])
    db_session.commit()

    claim = ResolutionClaim(
        case_id=case.id,
        operator_id=op.id,
        work_summary="Cleared drain conduit",
        actions_taken="Flushed line",
        status="AWAITING_VERIFICATION",
    )
    db_session.add(claim)
    db_session.commit()

    # 1. Citizen 1 confirms fixed
    st1, _, _ = VerificationPolicyEngine.evaluate_verification_submission(
        db=db_session,
        case=case,
        user=cit1,
        outcome=VerificationOutcome.CONFIRMED_FIXED,
        notes="Looks clean",
        active_claim=claim,
    )
    assert st1 == CaseState.AWAITING_VERIFICATION
    obs1 = VerificationObservation(
        case_id=case.id,
        resolution_claim_id=claim.id,
        verifier_id=cit1.id,
        outcome=VerificationOutcome.CONFIRMED_FIXED,
        notes="Looks clean",
    )
    db_session.add(obs1)
    db_session.commit()

    # 2. Citizen 2 disputes (STILL_UNRESOLVED)
    st2, _, _ = VerificationPolicyEngine.evaluate_verification_submission(
        db=db_session,
        case=case,
        user=cit2,
        outcome=VerificationOutcome.STILL_UNRESOLVED,
        notes="Still overflowing at back",
        active_claim=claim,
    )
    assert st2 == CaseState.DISPUTED
    assert claim.status == "DISPUTED"
    case.state = CaseState.DISPUTED
    obs2 = VerificationObservation(
        case_id=case.id,
        resolution_claim_id=claim.id,
        verifier_id=cit2.id,
        outcome=VerificationOutcome.STILL_UNRESOLVED,
        notes="Still overflowing",
        is_dispute=True,
    )
    db_session.add(obs2)
    db_session.commit()

    # 3. Citizen 3 attempts to submit a CONFIRMED_FIXED vote
    # Because claim is DISPUTED, the dispute CANNOT be silently overridden; case must remain DISPUTED!
    st3, _, _ = VerificationPolicyEngine.evaluate_verification_submission(
        db=db_session,
        case=case,
        user=cit3,
        outcome=VerificationOutcome.CONFIRMED_FIXED,
        notes="Looks okay from my side",
        active_claim=claim,
    )
    assert st3 == CaseState.DISPUTED
    assert claim.status == "DISPUTED"


def test_sybil_multiple_ordinary_accounts_cannot_auto_close_under_conservative_policy(
    db_session, monkeypatch
):
    """
    Threat Model Test (Issue 04):
    Demonstrates that when REQUIRE_TRUSTED_IDENTITY_FOR_AUTO_RESOLVE is enabled (conservative policy),
    an arbitrary number of self-registered ordinary citizen accounts (Sybil scenario) CANNOT
    trigger automatic state closure to RESOLVED. The case remains safely in AWAITING_VERIFICATION
    until vetted Reviewer/Administrator sign-off.
    """
    from app.core.config import settings

    monkeypatch.setattr(settings, "REQUIRE_TRUSTED_IDENTITY_FOR_AUTO_RESOLVE", True)

    cat = IssueCategory(name="Water Pipe Sybil Test", code="WP-SYBIL", default_severity_weight=1.5)
    operator = User(
        email="operator.sybil@civictrace.local",
        hashed_password="hash",
        display_name="Field Operator",
        role=UserRole.OPERATOR,
    )
    case = Case(
        public_id="TEST-SYBIL-01",
        category=cat,
        title="Burst Water Mains",
        description="Water mains burst on MG Road",
        latitude=22.72,
        longitude=75.86,
        state=CaseState.AWAITING_VERIFICATION,
    )
    claim = ResolutionClaim(
        case=case,
        operator=operator,
        work_summary="Replaced valve gasket",
        actions_taken="Installed new cast iron valve",
        status="AWAITING_VERIFICATION",
    )
    db_session.add_all([cat, operator, case, claim])
    db_session.commit()

    # Simulate an attacker registering 5 separate ordinary citizen accounts
    sybil_citizens = [
        User(
            email=f"sybil_{i}@attacker.local",
            hashed_password="hash",
            display_name=f"Sybil Observer {i}",
            role=UserRole.CITIZEN,
        )
        for i in range(1, 6)
    ]
    db_session.add_all(sybil_citizens)
    db_session.commit()

    # Each Sybil submits CONFIRMED_FIXED
    for i, citizen in enumerate(sybil_citizens, start=1):
        target_state, event_type, _ = VerificationPolicyEngine.evaluate_verification_submission(
            db=db_session,
            case=case,
            user=citizen,
            outcome=VerificationOutcome.CONFIRMED_FIXED,
            notes=f"Sybil account {i} confirms repair is completely fixed",
            active_claim=claim,
        )
        # In conservative mode, ordinary self-registered citizen accounts CANNOT auto-resolve!
        assert target_state == CaseState.AWAITING_VERIFICATION, (
            f"Security failure: Sybil account #{i} caused case to advance to {target_state}!"
        )
        assert event_type == "VERIFICATION_CONFIRMATION_LOGGED"
        assert claim.status == "AWAITING_VERIFICATION"

        obs = VerificationObservation(
            case_id=case.id,
            resolution_claim_id=claim.id,
            verifier_id=citizen.id,
            outcome=VerificationOutcome.CONFIRMED_FIXED,
            notes=f"Sybil observation {i}",
        )
        db_session.add(obs)
        db_session.commit()

    # Vetted Community Reviewer signs off: Case moves to RESOLVED
    reviewer = User(
        email="vetted.reviewer@civictrace.local",
        hashed_password="hash",
        display_name="Authorized Reviewer",
        role=UserRole.REVIEWER,
    )
    db_session.add(reviewer)
    db_session.commit()

    final_state, final_event, _ = VerificationPolicyEngine.evaluate_verification_submission(
        db=db_session,
        case=case,
        user=reviewer,
        outcome=VerificationOutcome.CONFIRMED_FIXED,
        notes="Official inspection corroborated repair",
        active_claim=claim,
    )
    assert final_state == CaseState.RESOLVED
    assert final_event == "RESOLUTION_VERIFIED_AND_CLOSED"
    assert claim.status == "VERIFIED"


def test_ordinary_registration_cannot_set_verified_identity(client, db_session):
    """
    Verifies that ordinary registration endpoint strictly enforces:
    - is_identity_verified defaults to False
    - identity_provider defaults to None
    - Any client payload attempting to inject is_identity_verified=True is ignored.
    """
    payload = {
        "email": "infiltrator@attacker.local",
        "password": "StrongPassword2026!",
        "display_name": "Infiltrator Account",
        "is_identity_verified": True,
        "identity_provider": "FORGED_PROVIDER",
    }
    resp = client.post("/api/v1/auth/register", json=payload)
    assert resp.status_code == 201
    data = resp.json()
    assert data["is_identity_verified"] is False
    assert data["identity_provider"] is None

    # Check database model directly
    db_user = db_session.query(User).filter(User.email == "infiltrator@attacker.local").first()
    assert db_user is not None
    assert db_user.is_identity_verified is False
    assert db_user.identity_provider is None


def test_identity_enrollment_endpoint_authorization(client, db_session):
    """
    Verifies that verified identity assurance requires an authorized administrator enrollment process.
    - Non-admin callers receive 403 Forbidden.
    - Authenticated administrators can enroll citizens.
    """
    from app.core.security import create_access_token, get_password_hash

    # Create an ordinary citizen
    citizen = User(
        email="citizen.enrollee@civictrace.local",
        hashed_password=get_password_hash("Pass2026!"),
        display_name="Citizen Enrollee",
        role=UserRole.CITIZEN,
        is_identity_verified=False,
    )
    # Create a reviewer
    reviewer = User(
        email="reviewer.unauth@civictrace.local",
        hashed_password=get_password_hash("Pass2026!"),
        display_name="Reviewer Unauth",
        role=UserRole.REVIEWER,
    )
    # Create an admin
    admin = User(
        email="admin.auth@civictrace.local",
        hashed_password=get_password_hash("Pass2026!"),
        display_name="Admin Auth",
        role=UserRole.ADMINISTRATOR,
    )
    db_session.add_all([citizen, reviewer, admin])
    db_session.commit()

    rev_token = create_access_token(subject=reviewer.id)
    admin_token = create_access_token(subject=admin.id)

    # Reviewer attempts to enroll citizen -> 403 Forbidden
    res_rev = client.post(
        f"/api/v1/auth/users/{citizen.id}/verify-identity?provider=AADHAAR_MUNICIPAL",
        headers={"Authorization": f"Bearer {rev_token}"},
    )
    assert res_rev.status_code == 403

    # Admin enrolls citizen -> 200 OK
    res_admin = client.post(
        f"/api/v1/auth/users/{citizen.id}/verify-identity?provider=AADHAAR_MUNICIPAL",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert res_admin.status_code == 200
    res_data = res_admin.json()
    assert res_data["is_identity_verified"] is True
    assert res_data["identity_provider"] == "AADHAAR_MUNICIPAL"

    db_session.refresh(citizen)
    assert citizen.is_identity_verified is True
    assert citizen.identity_provider == "AADHAAR_MUNICIPAL"


def test_trusted_identity_citizens_can_auto_resolve_under_conservative_policy(db_session):
    """
    Verifies that enrolled identity-verified citizens CAN satisfy quorum and trigger
    resolution under conservative policy without needing separate reviewer intervention.
    """

    cat = IssueCategory(name="Drainage", code="DRN", default_severity_weight=2.0)
    operator = User(
        email="drain.op@civictrace.local",
        hashed_password="hash",
        display_name="Drain Op",
        role=UserRole.OPERATOR,
    )
    case = Case(
        public_id="CAS-VERIF-AUTO",
        category=cat,
        title="Cleared Drain",
        description="Drain cleared",
        latitude=22.7,
        longitude=75.8,
        state=CaseState.AWAITING_VERIFICATION,
    )
    db_session.add_all([cat, operator, case])
    db_session.flush()

    claim = ResolutionClaim(
        case_id=case.id,
        operator_id=operator.id,
        work_summary="Cleared drain obstruction",
        actions_taken="Flushed drainage pipe",
        status="AWAITING_VERIFICATION",
    )
    # Two enrolled identity-verified citizens
    v_cit1 = User(
        email="verified_1@civictrace.local",
        hashed_password="hash",
        display_name="Verified Citizen 1",
        role=UserRole.CITIZEN,
        is_identity_verified=True,
        identity_provider="AADHAAR_MUNICIPAL",
    )
    v_cit2 = User(
        email="verified_2@civictrace.local",
        hashed_password="hash",
        display_name="Verified Citizen 2",
        role=UserRole.CITIZEN,
        is_identity_verified=True,
        identity_provider="DIGILOCKER",
    )
    db_session.add_all([claim, v_cit1, v_cit2])
    db_session.commit()

    # First observation recorded
    s1, e1, _ = VerificationPolicyEngine.evaluate_verification_submission(
        db=db_session,
        case=case,
        user=v_cit1,
        outcome=VerificationOutcome.CONFIRMED_FIXED,
        notes="Inspected drain, flow restored",
        active_claim=claim,
    )
    assert s1 == CaseState.AWAITING_VERIFICATION
    assert e1 == "VERIFICATION_CONFIRMATION_LOGGED"
    obs1 = VerificationObservation(
        case_id=case.id,
        resolution_claim_id=claim.id,
        verifier_id=v_cit1.id,
        outcome=VerificationOutcome.CONFIRMED_FIXED,
        notes="Inspected drain",
    )
    db_session.add(obs1)
    db_session.commit()

    # Second verified observation reaches quorum -> auto-resolves to RESOLVED
    s2, e2, _ = VerificationPolicyEngine.evaluate_verification_submission(
        db=db_session,
        case=case,
        user=v_cit2,
        outcome=VerificationOutcome.CONFIRMED_FIXED,
        notes="Also confirmed water flowing freely",
        active_claim=claim,
    )
    assert s2 == CaseState.RESOLVED
    assert e2 == "RESOLUTION_VERIFIED_AND_CLOSED"
    assert claim.status == "VERIFIED"
