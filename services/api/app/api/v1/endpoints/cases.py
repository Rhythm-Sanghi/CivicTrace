from typing import List, Optional, Dict, Any
from datetime import datetime, timezone
import os
from fastapi import APIRouter, Depends, HTTPException, status, Query, Response
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from app.db.session import get_db
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
from app.services.priority_engine import PriorityEngine
from app.services.export_service import ExportService
from app.services.verification_policy import VerificationPolicyEngine

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

    cases = query.order_by(Case.priority_score.desc(), Case.created_at.desc()).limit(limit).all()
    # Populate report counts
    for c in cases:
        c.report_count = len(c.reports)
    return cases

@router.get("/neighborhood/stats", response_model=NeighborhoodStats)
def get_neighborhood_stats(db: Session = Depends(get_db)):
    """Computes real live dashboard metrics from the database without hardcoded numbers."""
    cases = db.query(Case).all()
    total_reports = db.query(Report).count()

    open_states = [CaseState.SUBMITTED, CaseState.UNDER_REVIEW, CaseState.VERIFIED, CaseState.ASSIGNED, CaseState.IN_PROGRESS]
    open_cases = sum(1 for c in cases if c.state in open_states)
    verified_resolutions = sum(1 for c in cases if c.state == CaseState.RESOLVED)
    disputed_resolutions = sum(1 for c in cases if c.state == CaseState.DISPUTED)
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
        mid = len(sorted_days) // 2
        median_days = round(sorted_days[mid], 1)

    category_counts = {}
    for c in cases:
        cat_name = c.category.name if c.category else "Other"
        category_counts[cat_name] = category_counts.get(cat_name, 0) + 1

    priority_counts = {}
    for c in cases:
        p_band = c.priority_band.value
        priority_counts[p_band] = priority_counts.get(p_band, 0) + 1

    return {
        "service_area": "Indore Central & North Ward",
        "open_cases": open_cases,
        "verified_resolutions": verified_resolutions,
        "disputed_resolutions": disputed_resolutions,
        "awaiting_verification": awaiting_verification,
        "total_reports": total_reports,
        "median_resolution_days": median_days,
        "category_counts": category_counts,
        "priority_counts": priority_counts,
    }

@router.get("/{case_id}", response_model=CasePublic)
def get_case(case_id: str, db: Session = Depends(get_db)):
    case = db.query(Case).filter((Case.id == case_id) | (Case.public_id == case_id)).first()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    case.report_count = len(case.reports)
    return case

@router.get("/{case_id}/events", response_model=List[CaseEventPublic])
def get_case_events(case_id: str, db: Session = Depends(get_db)):
    case = db.query(Case).filter((Case.id == case_id) | (Case.public_id == case_id)).first()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    return db.query(CaseEvent).filter(CaseEvent.case_id == case.id).order_by(CaseEvent.event_index.asc()).all()

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

    can_trans, err_msg = CaseStateMachine.can_transition(case.state, target_state, current_user.role)
    if not can_trans:
        raise HTTPException(status_code=403, detail=err_msg)

    old_state = case.state
    case.state = target_state

    if target_state == CaseState.VERIFIED and not case.verified_at:
        case.verified_at = datetime.now(timezone.utc)
    elif target_state == CaseState.RESOLVED:
        case.resolved_at = datetime.now(timezone.utc)

    # Record event in cryptographic ledger
    LedgerService.append_event(
        db=db,
        case=case,
        event_type=f"STATE_CHANGED_TO_{target_state.value}",
        payload={"previous_state": old_state.value, "new_state": target_state.value, "notes": notes},
        actor=current_user,
        public_actor_label=f"{current_user.role.value.capitalize()} Action",
    )

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
    case.state = CaseState.ASSIGNED

    LedgerService.append_event(
        db=db,
        case=case,
        event_type="CASE_ASSIGNED",
        payload={"department_name": department.name, "assigned_by": current_user.display_name, "notes": notes},
        actor=current_user,
        public_actor_label="Community Reviewer",
    )

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

    claim = ResolutionClaim(
        case_id=case.id,
        operator_id=current_user.id,
        work_summary=claim_in.work_summary,
        actions_taken=claim_in.actions_taken,
        status="AWAITING_VERIFICATION",
    )
    db.add(claim)
    
    # Update case state explicitly to AWAITING_VERIFICATION
    case.state = CaseState.AWAITING_VERIFICATION

    LedgerService.append_event(
        db=db,
        case=case,
        event_type="RESOLUTION_CLAIMED",
        payload={
            "work_summary": claim_in.work_summary,
            "actions_taken": claim_in.actions_taken,
            "operator_id": current_user.display_name,
        },
        actor=current_user,
        public_actor_label="Public Works Operator",
    )

    db.commit()
    db.refresh(claim)
    return claim

@router.post("/{case_id}/verifications", response_model=VerificationPublic)
def submit_verification_observation(
    case_id: str,
    verif_in: VerificationCreate,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    """
    Independent resolution verification submitted by citizen observer or reviewer.
    Demonstrates crucial rule: Operators CANNOT verify their own resolution claims.
    """
    case = db.query(Case).filter((Case.id == case_id) | (Case.public_id == case_id)).first()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    try:
        target_state, event_type, actor_label = VerificationPolicyEngine.evaluate_verification_submission(
            db=db,
            case=case,
            user=current_user,
            outcome=verif_in.outcome,
            notes=verif_in.notes,
            guest_pseudonym=verif_in.guest_pseudonym,
        )
    except PermissionError as pe:
        raise HTTPException(status_code=403, detail=str(pe))
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))

    is_dispute = verif_in.outcome in [VerificationOutcome.STILL_UNRESOLVED, VerificationOutcome.PARTIALLY_FIXED]

    observation = VerificationObservation(
        case_id=case.id,
        verifier_id=current_user.id if current_user else None,
        guest_pseudonym=verif_in.guest_pseudonym or (actor_label if not current_user else None),
        outcome=verif_in.outcome,
        notes=verif_in.notes,
        is_dispute=is_dispute,
    )
    db.add(observation)

    case.state = target_state
    if target_state == CaseState.RESOLVED and not case.resolved_at:
        case.resolved_at = datetime.now(timezone.utc)

    LedgerService.append_event(
        db=db,
        case=case,
        event_type=event_type,
        payload={
            "outcome": verif_in.outcome.value,
            "notes": verif_in.notes,
            "is_dispute": is_dispute,
            "resulting_case_state": target_state.value,
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
    return db.query(VerificationObservation).filter(VerificationObservation.case_id == case.id).all()

@router.get("/{case_id}/export")
def export_case_evidence(case_id: str, db: Session = Depends(get_db)):
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
