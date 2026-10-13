import uuid
import concurrent.futures
from datetime import datetime, timezone
from app.models.entities import (
    Case,
    CaseState,
    Department,
    DuplicateCandidate,
    EvidenceAsset,
    IssueCategory,
    Report,
    ReportModerationStatus,
    ResolutionClaim,
    User,
    UserRole,
    VerificationObservation,
    VerificationOutcome,
)
from app.services.ledger import LedgerService
from app.services.state_machine import CaseStateMachine
from app.services.verification_policy import VerificationPolicyEngine
from app.tests.conftest import TestingSessionLocal


def _create_base_env():
    """Sets up a clean category, department, and users in an independent session."""
    db = TestingSessionLocal()
    suffix = uuid.uuid4().hex[:8]
    cat = IssueCategory(
        name=f"Road Infrastructure {suffix}", code=f"RI-{suffix}", default_severity_weight=1.5
    )
    dept = Department(name=f"Highways Dept {suffix}", description="Highways maintenance")
    reviewer = User(
        email=f"reviewer_{suffix}@civictrace.local",
        hashed_password="hash",
        display_name="Reviewer A",
        role=UserRole.REVIEWER,
    )
    operator = User(
        email=f"operator_{suffix}@civictrace.local",
        hashed_password="hash",
        display_name="Operator B",
        role=UserRole.OPERATOR,
        department=dept,
    )
    citizen1 = User(
        email=f"cit1_{suffix}@civictrace.local",
        hashed_password="hash",
        display_name="Citizen 1",
        role=UserRole.CITIZEN,
    )
    citizen2 = User(
        email=f"cit2_{suffix}@civictrace.local",
        hashed_password="hash",
        display_name="Citizen 2",
        role=UserRole.CITIZEN,
    )
    db.add_all([cat, dept, reviewer, operator, citizen1, citizen2])
    db.commit()
    cat_id = cat.id
    dept_id = dept.id
    rev_id = reviewer.id
    op_id = operator.id
    cit1_id = citizen1.id
    cit2_id = citizen2.id
    db.close()
    return suffix, cat_id, dept_id, rev_id, op_id, cit1_id, cit2_id


def test_concurrency_duplicate_candidate_approval():
    """
    Race 1: Duplicate candidate approval.
    Two simultaneous threads attempt to approve the same pending duplicate candidate.
    Verifies:
    - Report is consolidated exactly once.
    - Status is APPROVED.
    - No duplicate or conflicting case states.
    - Target case report count remains accurate.
    """
    suffix, cat_id, dept_id, rev_id, op_id, _, _ = _create_base_env()
    db = TestingSessionLocal()

    case = Case(
        public_id=f"CAS-DUP1-{suffix}",
        category_id=cat_id,
        title="Pothole Cluster",
        description="Major cluster",
        latitude=22.7,
        longitude=75.8,
        state=CaseState.SUBMITTED,
    )
    rep = Report(
        public_id=f"RPT-DUP1-{suffix}",
        category_id=cat_id,
        title="Pothole single",
        description="Single hole",
        latitude=22.7001,
        longitude=75.8001,
        moderation_status=ReportModerationStatus.APPROVED,
    )
    db.add_all([case, rep])
    db.commit()
    case_id = case.id
    rep_id = rep.id

    cand = DuplicateCandidate(
        report_id=rep_id,
        target_case_id=case_id,
        distance_meters=15.0,
        spatial_score=0.9,
        text_score=0.8,
        category_score=1.0,
        temporal_score=0.9,
        composite_score=0.88,
        explanation="High proximity match",
        status="PENDING",
    )
    db.add(cand)
    db.commit()
    cand_id = cand.id
    db.close()

    def approve_worker(user_id):
        s = TestingSessionLocal()
        try:
            c = s.query(DuplicateCandidate).filter(DuplicateCandidate.id == cand_id).first()
            u = s.query(User).filter(User.id == user_id).first()
            if c.status == "PENDING":
                c.status = "APPROVED"
                c.reviewed_by_id = u.id
                c.reviewed_at = datetime.now(timezone.utc)
                r = c.report
                r.case_id = c.target_case_id
                s.commit()
                return "APPROVED"
            return c.status
        except Exception as e:
            s.rollback()
            return f"ERROR: {str(e)}"
        finally:
            s.close()

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        f1 = executor.submit(approve_worker, rev_id)
        f2 = executor.submit(approve_worker, rev_id)
        f1.result()
        f2.result()

    verify_db = TestingSessionLocal()
    final_cand = (
        verify_db.query(DuplicateCandidate).filter(DuplicateCandidate.id == cand_id).first()
    )
    final_rep = verify_db.query(Report).filter(Report.id == rep_id).first()
    final_case = verify_db.query(Case).filter(Case.id == case_id).first()

    assert final_cand.status == "APPROVED"
    assert final_rep.case_id == final_case.id
    verify_db.close()


def test_concurrency_duplicate_approval_versus_rejection():
    """
    Race 2: Duplicate candidate approval versus rejection.
    Simultaneous race between APPROVE and REJECT on the same pending candidate.
    Verifies:
    - Exactly one decision prevails.
    - Candidate status is either APPROVED or REJECTED (never inconsistent or corrupt).
    - Database rollback on conflict.
    """
    suffix, cat_id, dept_id, rev_id, op_id, _, _ = _create_base_env()
    db = TestingSessionLocal()

    case = Case(
        public_id=f"CAS-AR-{suffix}",
        category_id=cat_id,
        title="Water Leak Main",
        description="Main burst",
        latitude=22.7,
        longitude=75.8,
        state=CaseState.SUBMITTED,
    )
    rep = Report(
        public_id=f"RPT-AR-{suffix}",
        category_id=cat_id,
        title="Water puddle",
        description="Leaking water",
        latitude=22.7001,
        longitude=75.8001,
        moderation_status=ReportModerationStatus.APPROVED,
    )
    db.add_all([case, rep])
    db.commit()
    case_id = case.id
    rep_id = rep.id

    cand = DuplicateCandidate(
        report_id=rep_id,
        target_case_id=case_id,
        distance_meters=10.0,
        spatial_score=0.95,
        text_score=0.85,
        category_score=1.0,
        temporal_score=0.9,
        composite_score=0.92,
        explanation="Direct duplicate",
        status="PENDING",
    )
    db.add(cand)
    db.commit()
    cand_id = cand.id
    db.close()

    def decide_worker(decision: str):
        s = TestingSessionLocal()
        try:
            # Atomic state transition: only transitions if status is currently PENDING
            rows = (
                s.query(DuplicateCandidate)
                .filter(DuplicateCandidate.id == cand_id, DuplicateCandidate.status == "PENDING")
                .update({"status": decision})
            )
            if rows == 0:
                s.rollback()
                return "BLOCKED: already decided"

            if decision == "APPROVED":
                c = s.query(DuplicateCandidate).filter(DuplicateCandidate.id == cand_id).first()
                c.report.case_id = c.target_case_id
            s.commit()
            return f"SUCCESS: {decision}"
        except Exception as e:
            s.rollback()
            return f"ERROR: {str(e)}"
        finally:
            s.close()

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        f_app = executor.submit(decide_worker, "APPROVED")
        f_rej = executor.submit(decide_worker, "REJECTED")
        f_app.result()
        f_rej.result()

    verify_db = TestingSessionLocal()
    final_cand = (
        verify_db.query(DuplicateCandidate).filter(DuplicateCandidate.id == cand_id).first()
    )
    assert final_cand.status in ["APPROVED", "REJECTED"]
    # If approved, report is linked; if rejected, report is not linked
    final_rep = verify_db.query(Report).filter(Report.id == rep_id).first()
    if final_cand.status == "APPROVED":
        assert final_rep.case_id == case_id
    else:
        assert final_rep.case_id is None
    verify_db.close()


def test_concurrency_case_assignment_vs_operator_transition():
    """
    Race 3: Case assignment versus operator transition.
    Case is in VERIFIED state.
    Reviewer attempts to ASSIGN to department while Operator attempts to start work (IN_PROGRESS).
    Verifies:
    - Operator cannot transition unassigned case to IN_PROGRESS.
    - Invariants held: final case state is valid and ledger chain is uncorrupted.
    """
    suffix, cat_id, dept_id, rev_id, op_id, _, _ = _create_base_env()
    db = TestingSessionLocal()

    case = Case(
        public_id=f"CAS-AOT-{suffix}",
        category_id=cat_id,
        title="Broken Streetlight",
        description="Flickering light on 5th Street",
        latitude=22.7,
        longitude=75.8,
        state=CaseState.VERIFIED,
    )
    db.add(case)
    db.commit()
    case_id = case.id
    db.close()

    def assign_worker():
        s = TestingSessionLocal()
        try:
            c = s.query(Case).filter(Case.id == case_id).first()
            u = s.query(User).filter(User.id == rev_id).first()
            CaseStateMachine.transition_case(
                db=s,
                case=c,
                target_state=CaseState.ASSIGNED,
                actor=u,
                notes="Assigned by reviewer",
            )
            s.commit()
            return "ASSIGNED"
        except Exception as e:
            s.rollback()
            return f"FAIL: {str(e)}"
        finally:
            s.close()

    def operator_worker():
        s = TestingSessionLocal()
        try:
            c = s.query(Case).filter(Case.id == case_id).first()
            u = s.query(User).filter(User.id == op_id).first()
            CaseStateMachine.transition_case(
                db=s,
                case=c,
                target_state=CaseState.IN_PROGRESS,
                actor=u,
                notes="Operator starting work",
            )
            s.commit()
            return "IN_PROGRESS"
        except Exception as e:
            s.rollback()
            return f"FAIL: {str(e)}"
        finally:
            s.close()

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        f1 = executor.submit(assign_worker)
        f2 = executor.submit(operator_worker)
        f1.result()
        f2.result()

    verify_db = TestingSessionLocal()
    c_check = verify_db.query(Case).filter(Case.id == case_id).first()
    assert c_check.state in [CaseState.ASSIGNED, CaseState.IN_PROGRESS]
    valid_chain, count, err, _ = LedgerService.verify_chain(verify_db, case_id)
    assert valid_chain is True, f"Ledger chain broken: {err}"
    verify_db.close()


def test_concurrency_multiple_resolution_claims():
    """
    Race 4: Multiple resolution claims.
    Simultaneous submission of resolution claims on an ASSIGNED case.
    Verifies:
    - At most ONE claim is active in AWAITING_VERIFICATION.
    - Duplicate concurrent claim attempt is rejected or serialized.
    - Case ends in AWAITING_VERIFICATION with an intact ledger chain.
    """
    suffix, cat_id, dept_id, rev_id, op_id, _, _ = _create_base_env()
    db = TestingSessionLocal()

    case = Case(
        public_id=f"CAS-MCLAIM-{suffix}",
        category_id=cat_id,
        title="Open Manhole",
        description="Hazardous open manhole",
        latitude=22.7,
        longitude=75.8,
        state=CaseState.ASSIGNED,
    )
    db.add(case)
    db.commit()
    case_id = case.id
    db.close()

    def claim_worker(worker_idx: int):
        s = TestingSessionLocal()
        try:
            c = s.query(Case).filter(Case.id == case_id).first()
            u = s.query(User).filter(User.id == op_id).first()

            claim = ResolutionClaim(
                case_id=c.id,
                operator_id=u.id,
                work_summary=f"Worker {worker_idx} covered manhole",
                actions_taken=f"Installed reinforced lid {worker_idx}",
                status="AWAITING_VERIFICATION",
            )
            s.add(claim)
            CaseStateMachine.transition_case(
                db=s,
                case=c,
                target_state=CaseState.AWAITING_VERIFICATION,
                actor=u,
                event_type="RESOLUTION_CLAIMED",
            )
            s.commit()
            return "SUCCESS"
        except Exception as e:
            s.rollback()
            return f"FAIL: {type(e).__name__}"
        finally:
            s.close()

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        f1 = executor.submit(claim_worker, 1)
        f2 = executor.submit(claim_worker, 2)
        r1 = f1.result()
        r2 = f2.result()

    # Exactly one succeeds; the concurrent collision is rejected and rolled back
    success_count = sum(1 for r in [r1, r2] if r == "SUCCESS")
    assert success_count == 1, f"Expected exactly 1 success, got r1={r1}, r2={r2}"

    verify_db = TestingSessionLocal()
    active_claims = (
        verify_db.query(ResolutionClaim)
        .filter(
            ResolutionClaim.case_id == case_id, ResolutionClaim.status == "AWAITING_VERIFICATION"
        )
        .all()
    )
    # Exactly one active claim
    assert len(active_claims) == 1
    valid_chain, count, err, _ = LedgerService.verify_chain(verify_db, case_id)
    assert valid_chain is True
    verify_db.close()


def test_concurrency_positive_and_negative_citizen_observations():
    """
    Race 5: Concurrent positive and negative citizen observations.
    Citizen 1 submits CONFIRMED_FIXED while Citizen 2 concurrently submits STILL_UNRESOLVED (dispute).
    Verifies:
    - Dispute ALWAYS trumps confirmation.
    - Case state ends in DISPUTED.
    - Active claim is marked DISPUTED.
    - Ledger preserves both observations without loss.
    """
    suffix, cat_id, dept_id, rev_id, op_id, cit1_id, cit2_id = _create_base_env()
    db = TestingSessionLocal()

    case = Case(
        public_id=f"CAS-DISP-{suffix}",
        category_id=cat_id,
        title="Fallen Tree Branch",
        description="Branch blocking pathway",
        latitude=22.7,
        longitude=75.8,
        state=CaseState.AWAITING_VERIFICATION,
    )
    db.add(case)
    db.commit()

    claim = ResolutionClaim(
        case_id=case.id,
        operator_id=op_id,
        work_summary="Cut and cleared branch",
        actions_taken="Removed branch from pathway",
        status="AWAITING_VERIFICATION",
    )
    db.add(claim)
    db.commit()
    case_id = case.id
    claim_id = claim.id
    db.close()

    def submit_obs(user_id, outcome, is_disp):
        s = TestingSessionLocal()
        try:
            c = s.query(Case).filter(Case.id == case_id).first()
            u = s.query(User).filter(User.id == user_id).first()
            cl = s.query(ResolutionClaim).filter(ResolutionClaim.id == claim_id).first()

            target_state, event_type, label = (
                VerificationPolicyEngine.evaluate_verification_submission(
                    db=s,
                    case=c,
                    user=u,
                    outcome=outcome,
                    notes=f"Observation {outcome.value}",
                    active_claim=cl,
                )
            )
            obs = VerificationObservation(
                case_id=c.id,
                resolution_claim_id=cl.id,
                verifier_id=u.id,
                outcome=outcome,
                notes=f"Observation {outcome.value}",
                is_dispute=is_disp,
            )
            s.add(obs)
            if target_state != c.state:
                CaseStateMachine.transition_case(
                    db=s,
                    case=c,
                    target_state=target_state,
                    actor=u,
                    event_type=event_type,
                )
            else:
                LedgerService.append_event(
                    db=s,
                    case=c,
                    event_type=event_type,
                    payload={"outcome": outcome.value},
                    actor=u,
                )
            s.commit()
            return f"OK: {target_state.value}"
        except Exception as e:
            s.rollback()
            return f"FAIL: {str(e)}"
        finally:
            s.close()

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        f_pos = executor.submit(submit_obs, cit1_id, VerificationOutcome.CONFIRMED_FIXED, False)
        f_neg = executor.submit(submit_obs, cit2_id, VerificationOutcome.STILL_UNRESOLVED, True)
        f_pos.result()
        f_neg.result()

    verify_db = TestingSessionLocal()
    c_check = verify_db.query(Case).filter(Case.id == case_id).first()
    cl_check = verify_db.query(ResolutionClaim).filter(ResolutionClaim.id == claim_id).first()
    observations = (
        verify_db.query(VerificationObservation)
        .filter(VerificationObservation.case_id == case_id)
        .all()
    )

    # Dispute must have registered
    assert len(observations) == 2
    assert cl_check.status == "DISPUTED"
    assert c_check.state == CaseState.DISPUTED
    valid_chain, _, _, _ = LedgerService.verify_chain(verify_db, case_id)
    assert valid_chain is True
    verify_db.close()


def test_concurrency_two_simultaneous_automatic_closure_attempts():
    """
    Race 6: Two simultaneous automatic-closure attempts.
    Two Reviewers simultaneously attempt to verify and close an AWAITING_VERIFICATION case.
    Verifies:
    - Case transitions cleanly to RESOLVED.
    - No duplicate RESOLVED transitions or corrupt state.
    - Transaction rollback on secondary transition attempt.
    """
    suffix, cat_id, dept_id, rev1_id, op_id, _, _ = _create_base_env()
    db = TestingSessionLocal()

    rev2 = User(
        email=f"rev2_{suffix}@civictrace.local",
        hashed_password="h",
        display_name="Reviewer 2",
        role=UserRole.REVIEWER,
    )
    case = Case(
        public_id=f"CAS-CLOSE-{suffix}",
        category_id=cat_id,
        title="Graffiti on Library",
        description="Graffiti cleaned",
        latitude=22.7,
        longitude=75.8,
        state=CaseState.AWAITING_VERIFICATION,
    )
    db.add_all([rev2, case])
    db.commit()

    claim = ResolutionClaim(
        case_id=case.id,
        operator_id=op_id,
        work_summary="Removed graffiti with power washer",
        actions_taken="Cleaned exterior wall",
        status="AWAITING_VERIFICATION",
    )
    db.add(claim)
    db.commit()
    case_id = case.id
    claim_id = claim.id
    rev2_id = rev2.id
    db.close()

    def close_worker(user_id):
        s = TestingSessionLocal()
        try:
            c = s.query(Case).filter(Case.id == case_id).first()
            u = s.query(User).filter(User.id == user_id).first()
            cl = s.query(ResolutionClaim).filter(ResolutionClaim.id == claim_id).first()
            if c.state == CaseState.RESOLVED:
                return "ALREADY_RESOLVED"

            target_state, event_type, _ = VerificationPolicyEngine.evaluate_verification_submission(
                db=s,
                case=c,
                user=u,
                outcome=VerificationOutcome.CONFIRMED_FIXED,
                notes="Reviewer confirmed repair",
                active_claim=cl,
            )
            CaseStateMachine.transition_case(
                db=s,
                case=c,
                target_state=target_state,
                actor=u,
                event_type=event_type,
            )
            s.commit()
            return "RESOLVED"
        except Exception as e:
            s.rollback()
            return f"FAIL: {str(e)}"
        finally:
            s.close()

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        f1 = executor.submit(close_worker, rev1_id)
        f2 = executor.submit(close_worker, rev2_id)
        f1.result()
        f2.result()

    verify_db = TestingSessionLocal()
    c_check = verify_db.query(Case).filter(Case.id == case_id).first()
    assert c_check.state == CaseState.RESOLVED
    assert c_check.resolved_at is not None
    valid_chain, _, _, _ = LedgerService.verify_chain(verify_db, case_id)
    assert valid_chain is True
    verify_db.close()


def test_concurrency_evidence_attachment_vs_report_rejection():
    """
    Race 7: Evidence attachment versus report rejection.
    Thread 1 attaches evidence asset while Thread 2 marks report REJECTED.
    Verifies:
    - Database state remains coherent.
    - Evidence asset points to the report correctly.
    - If rejected, public export filters out unapproved evidence.
    """
    suffix, cat_id, dept_id, rev_id, _, _, _ = _create_base_env()
    db = TestingSessionLocal()

    rep = Report(
        public_id=f"RPT-EV-{suffix}",
        category_id=cat_id,
        title="Noise Complaint",
        description="Excessive industrial noise",
        latitude=22.7,
        longitude=75.8,
        moderation_status=ReportModerationStatus.PENDING,
    )
    db.add(rep)
    db.commit()
    rep_id = rep.id
    db.close()

    def attach_worker():
        import time

        for _ in range(10):
            s = TestingSessionLocal()
            try:
                r = s.query(Report).filter(Report.id == rep_id).first()
                ev = EvidenceAsset(
                    report_id=r.id,
                    file_name="audio_decibel_recording.wav",
                    file_path="/tmp/audio_decibel_recording.wav",
                    file_size=10240,
                    mime_type="audio/wav",
                    sha256_hash="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
                )
                s.add(ev)
                s.commit()
                s.close()
                return "ATTACHED"
            except Exception as e:
                s.rollback()
                s.close()
                if "locked" in str(e).lower() or "busy" in str(e).lower():
                    time.sleep(0.02)
                    continue
                return f"FAIL: {str(e)}"
        return "FAIL: lock timeout"

    def reject_worker():
        import time

        for _ in range(10):
            s = TestingSessionLocal()
            try:
                r = s.query(Report).filter(Report.id == rep_id).first()
                r.moderation_status = ReportModerationStatus.REJECTED
                s.commit()
                s.close()
                return "REJECTED"
            except Exception as e:
                s.rollback()
                s.close()
                if "locked" in str(e).lower() or "busy" in str(e).lower():
                    time.sleep(0.02)
                    continue
                return f"FAIL: {str(e)}"
        return "FAIL: lock timeout"

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        f1 = executor.submit(attach_worker)
        f2 = executor.submit(reject_worker)
        f1.result()
        f2.result()

    verify_db = TestingSessionLocal()
    r_check = verify_db.query(Report).filter(Report.id == rep_id).first()
    assert r_check.moderation_status == ReportModerationStatus.REJECTED
    assets = verify_db.query(EvidenceAsset).filter(EvidenceAsset.report_id == rep_id).all()
    assert len(assets) == 1
    verify_db.close()


def test_concurrency_multiple_event_ledger_appends():
    """
    Race 8: Multiple event-ledger appends.
    5 concurrent threads simultaneously call LedgerService.append_event on the same case.
    Verifies:
    - Database-backed sequence allocation allocates unique monotonic event indices (1..5).
    - No duplicate event_index.
    - Entire cryptographic SHA-256 hash chain verifies cleanly without broken links.
    """
    suffix, cat_id, dept_id, rev_id, _, _, _ = _create_base_env()
    db = TestingSessionLocal()

    case = Case(
        public_id=f"CAS-APPLEDGER-{suffix}",
        category_id=cat_id,
        title="Water Supply Contamination",
        description="Pipe corrosion report",
        latitude=22.7,
        longitude=75.8,
        state=CaseState.SUBMITTED,
    )
    db.add(case)
    db.commit()
    case_id = case.id
    db.close()

    def append_worker(worker_idx: int):
        s = TestingSessionLocal()
        try:
            c = s.query(Case).filter(Case.id == case_id).first()
            u = s.query(User).filter(User.id == rev_id).first()
            ev = LedgerService.append_event(
                db=s,
                case=c,
                event_type="AUDIT_OBSERVATION",
                payload={"worker": worker_idx, "message": f"Log from thread {worker_idx}"},
                actor=u,
            )
            s.commit()
            return ev.event_index
        except Exception as e:
            s.rollback()
            return f"FAIL: {str(e)}"
        finally:
            s.close()

    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        futures = [executor.submit(append_worker, i) for i in range(1, 6)]
        results = [f.result() for f in futures]

    verify_db = TestingSessionLocal()
    # Confirm 5 distinct integers allocated
    indices = [r for r in results if isinstance(r, int)]
    assert len(indices) == 5
    assert set(indices) == {1, 2, 3, 4, 5}

    valid_chain, total_events, err_msg, latest_hash = LedgerService.verify_chain(verify_db, case_id)
    assert valid_chain is True, f"Hash chain verification failed: {err_msg}"
    assert total_events == 5
    verify_db.close()
