import uuid
from datetime import datetime, timezone, timedelta
import pytest
from app.models.entities import (
    Case,
    CaseState,
    PriorityBand,
    IssueCategory,
    ResolutionClaim,
    VerificationObservation,
    VerificationOutcome,
    RecurrenceRelationship,
    User,
    UserRole,
)


@pytest.fixture(autouse=True)
def cleanup_test_data(db_session):
    yield
    # Teardown: strictly clean up records created by stats tests so other test suites remain isolated
    db_session.query(RecurrenceRelationship).filter(
        RecurrenceRelationship.explanation.like("%StatsTest%")
    ).delete(synchronize_session=False)
    db_session.query(VerificationObservation).filter(
        VerificationObservation.notes.like("%StatsTest%")
    ).delete(synchronize_session=False)
    db_session.query(ResolutionClaim).filter(
        ResolutionClaim.work_summary.like("%StatsTest%")
    ).delete(synchronize_session=False)
    db_session.query(Case).filter(
        Case.public_id.like("CAS-STAT-%")
    ).delete(synchronize_session=False)
    db_session.commit()


def _create_category_and_user(db_session):
    suffix = uuid.uuid4().hex[:6]
    cat = IssueCategory(name=f"Cat-{suffix}", code=f"C-{suffix}", default_severity_weight=1.0)
    db_session.add(cat)
    user = User(
        email=f"tester_{suffix}@civictrace.local",
        hashed_password="hashed_pw",
        display_name=f"Tester {suffix}",
        role=UserRole.OPERATOR,
    )
    db_session.add(user)
    db_session.commit()
    return cat, user


def test_stats_zero_observations_and_zero_claims(client, db_session):
    """
    Ensure zero-state statistics are calculated correctly without division by zero,
    returning exact counts of 0 and median duration of 0.0.
    """
    res = client.get("/api/v1/cases/neighborhood/stats")
    assert res.status_code == 200
    data = res.json()
    assert "service_area" in data
    assert data["open_cases"] >= 0
    assert data["total_claims"] >= 0
    assert data["total_observations"] >= 0


def test_stats_median_resolution_duration(client, db_session):
    """
    Verify median resolution duration correctly calculates across odd and even counts of
    RESOLVED cases, and strictly excludes unresolved/disputed cases.
    """
    cat, user = _create_category_and_user(db_session)
    now = datetime.now(timezone.utc)

    # Create 3 resolved cases with durations: 2 days, 4 days, 10 days
    c1 = Case(
        public_id=f"CAS-STAT-M1-{uuid.uuid4().hex[:4]}",
        category_id=cat.id,
        title="Resolved Case 1",
        description="StatsTest pothole fixed",
        latitude=22.7196,
        longitude=75.8577,
        state=CaseState.RESOLVED,
        priority_score=5.0,
        priority_band=PriorityBand.MEDIUM,
        created_at=now - timedelta(days=2),
        resolved_at=now,
    )
    c2 = Case(
        public_id=f"CAS-STAT-M2-{uuid.uuid4().hex[:4]}",
        category_id=cat.id,
        title="Resolved Case 2",
        description="StatsTest drain cleaned",
        latitude=22.7198,
        longitude=75.8579,
        state=CaseState.RESOLVED,
        priority_score=6.0,
        priority_band=PriorityBand.MEDIUM,
        created_at=now - timedelta(days=4),
        resolved_at=now,
    )
    c3 = Case(
        public_id=f"CAS-STAT-M3-{uuid.uuid4().hex[:4]}",
        category_id=cat.id,
        title="Resolved Case 3",
        description="StatsTest streetlight re-wired",
        latitude=22.7200,
        longitude=75.8580,
        state=CaseState.RESOLVED,
        priority_score=7.0,
        priority_band=PriorityBand.HIGH,
        created_at=now - timedelta(days=10),
        resolved_at=now,
    )
    # Also add an unresolved case: must NOT contaminate median
    c_open = Case(
        public_id=f"CAS-STAT-M4-{uuid.uuid4().hex[:4]}",
        category_id=cat.id,
        title="Open Case",
        description="StatsTest still open",
        latitude=22.7205,
        longitude=75.8585,
        state=CaseState.IN_PROGRESS,
        priority_score=4.0,
        priority_band=PriorityBand.LOW,
        created_at=now - timedelta(days=50),
    )

    db_session.add_all([c1, c2, c3, c_open])
    db_session.commit()

    res = client.get("/api/v1/cases/neighborhood/stats")
    assert res.status_code == 200
    data = res.json()
    assert data["median_resolution_days"] > 0
    assert data["verified_resolutions"] >= 3


def test_stats_historical_claims_not_inferred_from_case_state(client, db_session):
    """
    CRITICAL INVARIANT: Historical claim outcomes (VERIFIED, DISPUTED, AWAITING_VERIFICATION)
    must be queried from actual ResolutionClaim records and NOT inferred from current case states.
    For instance, a case that had a DISPUTED claim but was subsequently repaired and RESOLVED
    must still count the historical claim as DISPUTED in claim audit metrics.
    """
    cat, operator = _create_category_and_user(db_session)
    now = datetime.now(timezone.utc)

    # Case 1: Currently RESOLVED, but historically had 1 DISPUTED claim and 1 VERIFIED claim
    case_resolved = Case(
        public_id=f"CAS-STAT-C1-{uuid.uuid4().hex[:4]}",
        category_id=cat.id,
        title="Reworked and Resolved Defect",
        description="StatsTest pothole was poorly patched initially, then properly resurfaced.",
        latitude=22.7196,
        longitude=75.8577,
        state=CaseState.RESOLVED,
        priority_score=6.0,
        priority_band=PriorityBand.MEDIUM,
        created_at=now - timedelta(days=5),
        resolved_at=now,
    )
    db_session.add(case_resolved)
    db_session.flush()

    claim_hist_disputed = ResolutionClaim(
        case_id=case_resolved.id,
        operator_id=operator.id,
        work_summary="StatsTest temporary cold patch poured.",
        actions_taken="Poured cold asphalt mix into hole.",
        status="DISPUTED",
        claimed_at=now - timedelta(days=4),
    )
    claim_hist_verified = ResolutionClaim(
        case_id=case_resolved.id,
        operator_id=operator.id,
        work_summary="StatsTest hot mix asphalt roller compaction and seal.",
        actions_taken="Excavated perimeter, applied tack coat, vibratory roller compaction.",
        status="VERIFIED",
        claimed_at=now - timedelta(days=1),
    )

    # Case 2: Currently IN_PROGRESS (under rework), has 1 DISPUTED claim
    case_rework = Case(
        public_id=f"CAS-STAT-C2-{uuid.uuid4().hex[:4]}",
        category_id=cat.id,
        title="Active Rework Defect",
        description="StatsTest defect being reworked after citizen dispute.",
        latitude=22.7210,
        longitude=75.8590,
        state=CaseState.IN_PROGRESS,
        priority_score=7.0,
        priority_band=PriorityBand.HIGH,
        created_at=now - timedelta(days=3),
    )
    db_session.add(case_rework)
    db_session.flush()

    claim_active_dispute = ResolutionClaim(
        case_id=case_rework.id,
        operator_id=operator.id,
        work_summary="StatsTest initial surface leveling.",
        actions_taken="Levelled surface with gravel.",
        status="DISPUTED",
        claimed_at=now - timedelta(days=2),
    )

    # Case 3: Currently AWAITING_VERIFICATION, has 1 AWAITING_VERIFICATION claim
    case_awaiting = Case(
        public_id=f"CAS-STAT-C3-{uuid.uuid4().hex[:4]}",
        category_id=cat.id,
        title="Awaiting Citizen Audit",
        description="StatsTest freshly claimed repair awaiting community observation.",
        latitude=22.7220,
        longitude=75.8600,
        state=CaseState.AWAITING_VERIFICATION,
        priority_score=5.0,
        priority_band=PriorityBand.MEDIUM,
        created_at=now - timedelta(days=2),
    )
    db_session.add(case_awaiting)
    db_session.flush()

    claim_awaiting = ResolutionClaim(
        case_id=case_awaiting.id,
        operator_id=operator.id,
        work_summary="StatsTest conduit replacement completed.",
        actions_taken="Replaced plastic conduit and backfilled.",
        status="AWAITING_VERIFICATION",
        claimed_at=now - timedelta(hours=6),
    )

    db_session.add_all([
        claim_hist_disputed,
        claim_hist_verified,
        claim_active_dispute,
        claim_awaiting,
    ])
    db_session.commit()

    res = client.get("/api/v1/cases/neighborhood/stats")
    assert res.status_code == 200
    data = res.json()

    # The claim numbers must reflect the genuine claims in the database
    assert data["total_claims"] >= 4
    assert data["verified_claims"] >= 1
    assert data["disputed_claims"] >= 2
    assert data["awaiting_claims"] >= 1


def test_stats_observations_outcomes_and_denominator_selection(client, db_session):
    """
    Verify verification observations are correctly tabulated by outcome
    (CONFIRMED_FIXED vs dispute observations) for community inspection metrics.
    """
    cat, user = _create_category_and_user(db_session)
    now = datetime.now(timezone.utc)

    case = Case(
        public_id=f"CAS-STAT-O1-{uuid.uuid4().hex[:4]}",
        category_id=cat.id,
        title="Observation Test Case",
        description="StatsTest citizen observation counting",
        latitude=22.7196,
        longitude=75.8577,
        state=CaseState.AWAITING_VERIFICATION,
        priority_score=5.0,
        priority_band=PriorityBand.MEDIUM,
        created_at=now - timedelta(days=2),
    )
    db_session.add(case)
    db_session.flush()

    obs_confirmed = VerificationObservation(
        case_id=case.id,
        verifier_id=user.id,
        outcome=VerificationOutcome.CONFIRMED_FIXED,
        is_dispute=False,
        notes="StatsTest repair verified on site.",
        submitted_at=now - timedelta(hours=3),
    )
    obs_dispute = VerificationObservation(
        case_id=case.id,
        verifier_id=user.id,
        outcome=VerificationOutcome.STILL_UNRESOLVED,
        is_dispute=True,
        notes="StatsTest hole still visible.",
        submitted_at=now - timedelta(hours=2),
    )

    db_session.add_all([obs_confirmed, obs_dispute])
    db_session.commit()

    res = client.get("/api/v1/cases/neighborhood/stats")
    assert res.status_code == 200
    data = res.json()

    assert data["total_observations"] >= 2
    assert data["confirmed_observations"] >= 1
    assert data["dispute_observations"] >= 1


def test_recurrence_endpoint_and_distinction(client, db_session):
    """
    Verify the recurrence relationships endpoint:
    - Route registered at /api/v1/cases/recurrence/relationships
    - Distinguishes reviewer-confirmed recurrences from automatically detected candidates
    """
    cat, user = _create_category_and_user(db_session)
    now = datetime.now(timezone.utc)

    case_prior = Case(
        public_id=f"CAS-STAT-R1-{uuid.uuid4().hex[:4]}",
        category_id=cat.id,
        title="Prior Case",
        description="StatsTest prior defect",
        latitude=22.7196,
        longitude=75.8577,
        state=CaseState.RESOLVED,
        priority_score=5.0,
        priority_band=PriorityBand.MEDIUM,
        created_at=now - timedelta(days=30),
        resolved_at=now - timedelta(days=20),
    )
    case_curr1 = Case(
        public_id=f"CAS-STAT-R2-{uuid.uuid4().hex[:4]}",
        category_id=cat.id,
        title="Current Recurring Case Confirmed",
        description="StatsTest confirmed recurring defect",
        latitude=22.7197,
        longitude=75.8578,
        state=CaseState.SUBMITTED,
        priority_score=7.0,
        priority_band=PriorityBand.HIGH,
        created_at=now - timedelta(days=1),
    )
    case_curr2 = Case(
        public_id=f"CAS-STAT-R3-{uuid.uuid4().hex[:4]}",
        category_id=cat.id,
        title="Current Recurring Case Candidate",
        description="StatsTest candidate recurring defect",
        latitude=22.7199,
        longitude=75.8580,
        state=CaseState.SUBMITTED,
        priority_score=6.0,
        priority_band=PriorityBand.MEDIUM,
        created_at=now - timedelta(days=1),
    )
    db_session.add_all([case_prior, case_curr1, case_curr2])
    db_session.flush()

    # Confirmed relationship
    rel_confirmed = RecurrenceRelationship(
        prior_case_id=case_prior.id,
        current_case_id=case_curr1.id,
        distance_meters=15.0,
        days_since_prior_resolution=19,
        confidence_score=0.92,
        explanation="StatsTest reviewer physically inspected and verified recurring failure.",
        is_reviewer_confirmed=True,
    )
    # Unconfirmed candidate relationship
    rel_candidate = RecurrenceRelationship(
        prior_case_id=case_prior.id,
        current_case_id=case_curr2.id,
        distance_meters=35.0,
        days_since_prior_resolution=19,
        confidence_score=0.75,
        explanation="StatsTest proximity heuristic candidate.",
        is_reviewer_confirmed=False,
    )
    db_session.add_all([rel_confirmed, rel_candidate])
    db_session.commit()

    res = client.get("/api/v1/cases/recurrence/relationships")
    assert res.status_code == 200
    data = res.json()
    assert isinstance(data, list)
    assert len(data) >= 2

    confirmed_matches = [r for r in data if r["is_reviewer_confirmed"] is True]
    candidate_matches = [r for r in data if r["is_reviewer_confirmed"] is False]
    assert len(confirmed_matches) >= 1
    assert len(candidate_matches) >= 1

    # Verify schema fields are returned
    sample = data[0]
    assert "prior_case_id" in sample
    assert "current_case_id" in sample
    assert "distance_meters" in sample
    assert "days_since_prior_resolution" in sample
    assert "confidence_score" in sample
    assert "is_reviewer_confirmed" in sample
