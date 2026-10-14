from typing import List, Optional
import os
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from app.db.session import get_db
from app.core.config import settings
from app.core.rate_limiter import check_rate_limit
from app.models.entities import (
    Case,
    Report,
    CaseState,
    User,
    UserRole,
    VerificationOutcome,
    ResolutionClaim,
    VerificationObservation,
    CaseEvent,
    RecurrenceRelationship,
    Department,
    CaseAssignment,
    ReportModerationStatus,
)
from app.schemas.all_schemas import (
    CasePublic,
    CaseEventPublic,
    CaseEventChainValidation,
    ResolutionClaimCreate,
    ResolutionClaimPublic,
    VerificationCreate,
    VerificationPublic,
    RecurrencePublic,
    NeighborhoodStats,
)
from app.api.deps import get_current_user_optional, get_current_user, require_roles
from app.services.state_machine import CaseStateMachine
from app.services.ledger import LedgerService
from app.services.export_service import ExportService
from app.services.verification_policy import VerificationPolicyEngine
from app.services.priority_engine import PriorityEngine

router = APIRouter()


@router.get("", response_model=List[CasePublic])
def list_cases(
    db: Session = Depends(get_db),
    state: Optional[CaseState] = None,
    category_id: Optional[str] = None,
    priority_band: Optional[str] = None,
    min_lat: Optional[float] = None,
    max_lat: Optional[float] = None,
    min_lon: Optional[float] = None,
    max_lon: Optional[float] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=200),
):
    query = db.query(Case)
    if state:
        query = query.filter(Case.state == state)
    if category_id:
        query = query.filter(Case.category_id == category_id)
    if priority_band:
        query = query.filter(Case.priority_band == priority_band)

    # Geospatial bounding-box query for responsive map filtering
    if min_lat is not None and max_lat is not None:
        query = query.filter(Case.latitude.between(min_lat, max_lat))
    if min_lon is not None and max_lon is not None:
        query = query.filter(Case.longitude.between(min_lon, max_lon))

    cases = (
        query.order_by(Case.priority_score.desc(), Case.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )
    # Populate report counts (only counting approved corroborating reports)
    for c in cases:
        c.report_count = sum(
            1 for r in c.reports if r.moderation_status == ReportModerationStatus.APPROVED
        )
    return cases


@router.get("/neighborhood/stats", response_model=NeighborhoodStats)
def get_neighborhood_stats(db: Session = Depends(get_db)):
    """Computes real live dashboard metrics from the database without hardcoded numbers."""
    cases = db.query(Case).all()
    total_reports = (
        db.query(Report).filter(Report.moderation_status == ReportModerationStatus.APPROVED).count()
    )

    open_states = [
        CaseState.SUBMITTED,
        CaseState.UNDER_REVIEW,
        CaseState.VERIFIED,
        CaseState.ASSIGNED,
        CaseState.IN_PROGRESS,
        CaseState.REOPENED,
    ]
    open_cases = sum(1 for c in cases if c.state in open_states)
    verified_resolutions = sum(1 for c in cases if c.state == CaseState.RESOLVED)
    disputed_resolutions = sum(1 for c in cases if c.state == CaseState.DISPUTED)
    reopened_cases = sum(1 for c in cases if c.state == CaseState.REOPENED)
    awaiting_verification = sum(1 for c in cases if c.state == CaseState.AWAITING_VERIFICATION)

    # Resolution duration calculations for truly resolved cases
    resolution_durations_days = []
    for c in cases:
        if c.state == CaseState.RESOLVED and c.resolved_at and c.created_at:
            delta = (c.resolved_at - c.created_at).total_seconds() / 86400.0
            resolution_durations_days.append(delta)

    median_days = 0.0
    if resolution_durations_days:
        sorted_days = sorted(resolution_durations_days)
        n = len(sorted_days)
        if n % 2 == 1:
            median_days = round(sorted_days[n // 2], 1)
        else:
            mid = n // 2
            median_days = round((sorted_days[mid - 1] + sorted_days[mid]) / 2.0, 1)

    category_counts = {}
    for c in cases:
        cat_name = c.category.name if c.category else "Other"
        category_counts[cat_name] = category_counts.get(cat_name, 0) + 1

    priority_counts = {}
    for c in cases:
        p_band = c.priority_band.value
        priority_counts[p_band] = priority_counts.get(p_band, 0) + 1

    total_claims = db.query(ResolutionClaim).count()
    verified_claims = (
        db.query(ResolutionClaim).filter(ResolutionClaim.status == "VERIFIED").count()
    )
    disputed_claims = (
        db.query(ResolutionClaim).filter(ResolutionClaim.status == "DISPUTED").count()
    )
    awaiting_claims = (
        db.query(ResolutionClaim).filter(ResolutionClaim.status == "AWAITING_VERIFICATION").count()
    )
    total_observations = db.query(VerificationObservation).count()
    confirmed_observations = (
        db.query(VerificationObservation)
        .filter(VerificationObservation.outcome == VerificationOutcome.CONFIRMED_FIXED)
        .count()
    )
    dispute_observations = (
        db.query(VerificationObservation)
        .filter(VerificationObservation.is_dispute == True)  # noqa: E712
        .count()
    )

    return {
        "service_area": "Indore Central & North Ward",
        "open_cases": open_cases,
        "verified_resolutions": verified_resolutions,
        "disputed_resolutions": disputed_resolutions,
        "reopened_cases": reopened_cases,
        "awaiting_verification": awaiting_verification,
        "total_reports": total_reports,
        "median_resolution_days": median_days,
        "category_counts": category_counts,
        "priority_counts": priority_counts,
        "total_claims": total_claims,
        "verified_claims": verified_claims,
        "disputed_claims": disputed_claims,
        "awaiting_claims": awaiting_claims,
        "total_observations": total_observations,
        "confirmed_observations": confirmed_observations,
        "dispute_observations": dispute_observations,
    }


@router.get("/{case_id}", response_model=CasePublic)
def get_case(case_id: str, db: Session = Depends(get_db)):
    case = db.query(Case).filter((Case.id == case_id) | (Case.public_id == case_id)).first()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    case.report_count = sum(
        1 for r in case.reports if r.moderation_status == ReportModerationStatus.APPROVED
    )
    return case


@router.get("/{case_id}/events", response_model=List[CaseEventPublic])
def get_case_events(case_id: str, db: Session = Depends(get_db)):
    case = db.query(Case).filter((Case.id == case_id) | (Case.public_id == case_id)).first()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    return (
        db.query(CaseEvent)
        .filter(CaseEvent.case_id == case.id)
        .order_by(CaseEvent.event_index.asc())
        .all()
    )


@router.get("/{case_id}/events/verify", response_model=CaseEventChainValidation)
def verify_case_events_ledger(case_id: str, db: Session = Depends(get_db)):
    case = db.query(Case).filter((Case.id == case_id) | (Case.public_id == case_id)).first()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    is_valid, total, err, latest_hash = LedgerService.verify_chain(db, case.id)
    return {
        "case_id": case.public_id,
        "is_valid": is_valid,
        "total_events": total,
        "error_message": err,
        "latest_event_hash": latest_hash,
    }


@router.post("/recalculate-priorities")
def recalculate_priorities(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.REVIEWER, UserRole.ADMINISTRATOR)),
):
    """
    Reviewer/Administrator trigger to refresh dynamic civic priority scores
    across all open cases taking into account time elapsed and corroborated reports.
    """
    updated = PriorityEngine.recalculate_open_case_priorities(db)
    return {"status": "success", "updated_cases": updated}


@router.post("/{case_id}/transition", response_model=CasePublic)
def transition_case_state(
    case_id: str,
    target_state: CaseState,
    notes: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    case = db.query(Case).filter((Case.id == case_id) | (Case.public_id == case_id)).first()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    # Issue 01 & 07: Operator department-scoped verification
    if current_user.role == UserRole.OPERATOR:
        latest_assignment = (
            db.query(CaseAssignment)
            .filter(CaseAssignment.case_id == case.id)
            .order_by(CaseAssignment.assigned_at.desc())
            .first()
        )
        if latest_assignment and latest_assignment.department_id and current_user.department_id:
            if current_user.department_id != latest_assignment.department_id:
                raise HTTPException(
                    status_code=403,
                    detail="Department scope mismatch: operator is not assigned to the department handling this case.",
                )

    try:
        CaseStateMachine.transition_case(
            db=db,
            case=case,
            target_state=target_state,
            actor=current_user,
            notes=notes,
        )
    except PermissionError as pe:
        raise HTTPException(status_code=403, detail=str(pe))

    db.commit()
    db.refresh(case)
    case.report_count = len(case.reports)
    return case


@router.post("/{case_id}/assign", response_model=CasePublic)
def assign_case_department(
    case_id: str,
    department_id: str,
    notes: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.REVIEWER, UserRole.ADMINISTRATOR)),
):
    case = db.query(Case).filter((Case.id == case_id) | (Case.public_id == case_id)).first()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    department = db.query(Department).filter(Department.id == department_id).first()
    if not department:
        raise HTTPException(status_code=404, detail="Department not found")

    assignment = CaseAssignment(
        case_id=case.id,
        department_id=department.id,
        assigned_by_id=current_user.id,
        notes=notes,
    )
    db.add(assignment)

    try:
        CaseStateMachine.transition_case(
            db=db,
            case=case,
            target_state=CaseState.ASSIGNED,
            actor=current_user,
            event_type="CASE_ASSIGNED",
            custom_payload={
                "department_name": department.name,
                "assigned_by": current_user.display_name,
                "notes": notes,
            },
        )
    except PermissionError as pe:
        raise HTTPException(status_code=403, detail=str(pe))

    db.commit()
    db.refresh(case)
    case.report_count = len(case.reports)
    return case


@router.post("/{case_id}/claims", response_model=ResolutionClaimPublic)
def submit_resolution_claim(
    case_id: str,
    claim_in: ResolutionClaimCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.OPERATOR, UserRole.ADMINISTRATOR)),
):
    case = db.query(Case).filter((Case.id == case_id) | (Case.public_id == case_id)).first()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    # Issue 01: Validate eligible prior states
    eligible_states = [CaseState.ASSIGNED, CaseState.IN_PROGRESS, CaseState.DISPUTED]
    if case.state not in eligible_states:
        raise HTTPException(
            status_code=400,
            detail=f"Resolution claims cannot be filed against case in '{case.state.value}' state. Must be ASSIGNED, IN_PROGRESS, or DISPUTED.",
        )

    # Issue 01: Verify department-scoped operator authorization (unless Administrator override)
    latest_assignment = (
        db.query(CaseAssignment)
        .filter(CaseAssignment.case_id == case.id)
        .order_by(CaseAssignment.assigned_at.desc())
        .first()
    )
    if current_user.role == UserRole.OPERATOR:
        if latest_assignment and latest_assignment.department_id:
            if (
                current_user.department_id
                and current_user.department_id != latest_assignment.department_id
            ):
                raise HTTPException(
                    status_code=403,
                    detail="Department scope mismatch: operator is not assigned to the department handling this case.",
                )
        elif latest_assignment is None and not current_user.department_id:
            # If neither case nor operator is tied to a specific department in unconfigured setups, log warning or allow
            pass
        elif latest_assignment is None and current_user.department_id:
            # Auto-record assignment for the operator's department
            auto_assign = CaseAssignment(
                case_id=case.id,
                department_id=current_user.department_id,
                assigned_by_id=current_user.id,
                notes="Automatic department assignment upon operator work claim",
            )
            db.add(auto_assign)
            db.flush()

    # Issue 01: Prevent multiple simultaneous active claims
    existing_active_claim = (
        db.query(ResolutionClaim)
        .filter(
            ResolutionClaim.case_id == case.id, ResolutionClaim.status == "AWAITING_VERIFICATION"
        )
        .first()
    )
    if existing_active_claim:
        raise HTTPException(
            status_code=400,
            detail="An active resolution claim is already pending verification for this case.",
        )

    claim = ResolutionClaim(
        case_id=case.id,
        operator_id=current_user.id,
        work_summary=claim_in.work_summary,
        actions_taken=claim_in.actions_taken,
        status="AWAITING_VERIFICATION",
    )
    db.add(claim)

    # Issue 14: Centralized State Machine Transition with atomic ledger appending
    try:
        CaseStateMachine.transition_case(
            db=db,
            case=case,
            target_state=CaseState.AWAITING_VERIFICATION,
            actor=current_user,
            event_type="RESOLUTION_CLAIMED",
            custom_payload={
                "work_summary": claim_in.work_summary,
                "actions_taken": claim_in.actions_taken,
                "operator_id": current_user.display_name,
                "department_id": latest_assignment.department_id
                if latest_assignment
                else getattr(current_user, "department_id", None),
            },
        )
    except PermissionError as pe:
        raise HTTPException(status_code=403, detail=str(pe))

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="An active resolution claim is already pending verification for this case.",
        )

    db.refresh(claim)
    return claim


@router.post("/{case_id}/verifications", response_model=VerificationPublic)
def submit_verification_observation(
    case_id: str,
    verif_in: VerificationCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    """
    Independent resolution verification submitted by citizen observer or reviewer.
    Demonstrates crucial rule: Operators CANNOT verify their own resolution claims.
    """
    check_rate_limit(
        request,
        max_requests=settings.RATE_LIMIT_REPORT_MAX,
        window_seconds=settings.RATE_LIMIT_WINDOW_SECONDS,
        action_key="submit_verification",
    )

    case = db.query(Case).filter((Case.id == case_id) | (Case.public_id == case_id)).first()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    active_claim = (
        db.query(ResolutionClaim)
        .filter(ResolutionClaim.case_id == case.id)
        .order_by(ResolutionClaim.claimed_at.desc())
        .first()
    )

    try:
        target_state, event_type, actor_label = (
            VerificationPolicyEngine.evaluate_verification_submission(
                db=db,
                case=case,
                user=current_user,
                outcome=verif_in.outcome,
                notes=verif_in.notes,
                guest_pseudonym=verif_in.guest_pseudonym,
                active_claim=active_claim,
            )
        )
    except PermissionError as pe:
        raise HTTPException(status_code=403, detail=str(pe))
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))

    is_dispute = verif_in.outcome in [
        VerificationOutcome.STILL_UNRESOLVED,
        VerificationOutcome.PARTIALLY_FIXED,
    ]

    observation = VerificationObservation(
        case_id=case.id,
        resolution_claim_id=active_claim.id if active_claim else None,
        verifier_id=current_user.id if current_user else None,
        guest_pseudonym=verif_in.guest_pseudonym or (actor_label if not current_user else None),
        outcome=verif_in.outcome,
        notes=verif_in.notes,
        is_dispute=is_dispute,
    )
    db.add(observation)

    if target_state != case.state:
        try:
            # Issue 14: Centralized state machine transition with atomic ledger event
            CaseStateMachine.transition_case(
                db=db,
                case=case,
                target_state=target_state,
                actor=current_user
                if current_user
                else User(
                    email="guest@civictrace.local",
                    hashed_password="",
                    display_name=actor_label,
                    role=UserRole.CITIZEN,
                ),
                event_type=event_type,
                custom_payload={
                    "outcome": verif_in.outcome.value,
                    "notes": verif_in.notes,
                    "is_dispute": is_dispute,
                    "resulting_case_state": target_state.value,
                },
            )
        except PermissionError as pe:
            raise HTTPException(status_code=403, detail=str(pe))
    else:
        # State unchanged; record the logged observation on append-only ledger
        LedgerService.append_event(
            db=db,
            case=case,
            event_type=event_type,
            payload={
                "outcome": verif_in.outcome.value,
                "notes": verif_in.notes,
                "is_dispute": is_dispute,
                "resulting_case_state": case.state.value,
            },
            actor=current_user,
            public_actor_label=actor_label,
        )

    db.commit()
    db.refresh(observation)
    return observation


@router.get("/{case_id}/claims", response_model=List[ResolutionClaimPublic])
def list_case_claims(case_id: str, db: Session = Depends(get_db)):
    case = db.query(Case).filter((Case.id == case_id) | (Case.public_id == case_id)).first()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    return db.query(ResolutionClaim).filter(ResolutionClaim.case_id == case.id).all()


@router.get("/{case_id}/verifications", response_model=List[VerificationPublic])
def list_case_verifications(case_id: str, db: Session = Depends(get_db)):
    case = db.query(Case).filter((Case.id == case_id) | (Case.public_id == case_id)).first()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    return (
        db.query(VerificationObservation).filter(VerificationObservation.case_id == case.id).all()
    )


@router.get("/{case_id}/export")
def export_case_evidence(case_id: str, request: Request, db: Session = Depends(get_db)):
    check_rate_limit(
        request,
        max_requests=settings.RATE_LIMIT_EXPORT_MAX,
        window_seconds=settings.RATE_LIMIT_WINDOW_SECONDS,
        action_key="export_package",
    )
    case = db.query(Case).filter((Case.id == case_id) | (Case.public_id == case_id)).first()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    zip_path = ExportService.generate_case_export_package(db, case.id)
    return FileResponse(
        path=zip_path,
        filename=os.path.basename(zip_path),
        media_type="application/zip",
    )


@router.get("/recurrence/relationships", response_model=List[RecurrencePublic])
def list_recurrences(db: Session = Depends(get_db)):
    return db.query(RecurrenceRelationship).all()
