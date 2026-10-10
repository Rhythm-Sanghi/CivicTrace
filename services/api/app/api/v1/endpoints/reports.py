import os
import hashlib
from typing import List, Optional
import random
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status, Query, UploadFile, File, Form
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.core.config import settings
from app.models.entities import (
    Report,
    Case,
    IssueCategory,
    User,
    UserRole,
    ReportModerationStatus,
    CaseState,
    DuplicateCandidate,
    EvidenceAsset,
)
from app.schemas.all_schemas import (
    ReportCreate,
    ReportPublic,
    CategoryPublic,
    DuplicateCandidatePublic,
    DuplicateDecision,
    EvidenceAssetPublic,
)
from app.api.deps import get_current_user_optional, get_current_user, require_roles
from app.services.duplicate_engine import DuplicateDetectionEngine
from app.services.priority_engine import PriorityEngine
from app.services.ledger import LedgerService

router = APIRouter()

@router.get("/categories", response_model=List[CategoryPublic])
def list_categories(db: Session = Depends(get_db)):
    return db.query(IssueCategory).all()

@router.post("", response_model=ReportPublic, status_code=status.HTTP_201_CREATED)
def submit_report(
    report_in: ReportCreate,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    category = db.query(IssueCategory).filter(IssueCategory.id == report_in.category_id).first()
    if not category:
        raise HTTPException(status_code=400, detail="Invalid category ID")

    # Generate public reference ID: e.g. RPT-2026-XXXX
    count = db.query(Report).count() + 1
    public_id = f"RPT-2026-{count:04d}"

    report = Report(
        public_id=public_id,
        category_id=report_in.category_id,
        reporter_id=current_user.id if current_user else None,
        guest_pseudonym=report_in.guest_pseudonym if not current_user else current_user.display_name,
        title=report_in.title,
        description=report_in.description,
        latitude=report_in.latitude,
        longitude=report_in.longitude,
        address_reference=report_in.address_reference,
        accuracy_meters=report_in.accuracy_meters,
        moderation_status=ReportModerationStatus.APPROVED, # Default to approved unless flagged
    )
    db.add(report)
    db.flush()

    # Automatically run deterministic duplicate detection against active cases
    candidates = DuplicateDetectionEngine.find_and_record_candidates(db, report)

    # If no candidate has high score, automatically promote or link
    # For transparency: if no strong candidates found (composite < 0.55), automatically promote this report into a new public Case
    strong_candidate = next((c for c in candidates if c.composite_score >= 0.55), None)
    
    if not strong_candidate:
        # Create consolidated Case
        case_count = db.query(Case).count() + 1
        case_public_id = f"CAS-2026-{case_count:04d}"
        
        score, band, breakdown = PriorityEngine.calculate_priority(
            category_weight=category.default_severity_weight,
            report_count=1,
            created_at=datetime.now(timezone.utc),
        )

        new_case = Case(
            public_id=case_public_id,
            category_id=category.id,
            title=report.title,
            description=report.description,
            latitude=report.latitude,
            longitude=report.longitude,
            address_reference=report.address_reference,
            state=CaseState.SUBMITTED,
            priority_score=score,
            priority_band=band,
            priority_breakdown=breakdown,
        )
        db.add(new_case)
        db.flush()

        report.case_id = new_case.id

        # Record in append-only cryptographic ledger
        LedgerService.append_event(
            db=db,
            case=new_case,
            event_type="REPORT_CREATED",
            payload={
                "report_id": report.public_id,
                "title": report.title,
                "category": category.name,
                "coordinates": {"lat": report.latitude, "lon": report.longitude},
            },
            actor=current_user,
            public_actor_label="Citizen Observer" if not current_user else current_user.display_name,
        )

    db.commit()
    db.refresh(report)
    return report

@router.get("", response_model=List[ReportPublic])
def list_reports(
    db: Session = Depends(get_db),
    category_id: Optional[str] = None,
    unlinked_only: bool = False,
    limit: int = Query(50, ge=1, le=100),
):
    query = db.query(Report)
    if category_id:
        query = query.filter(Report.category_id == category_id)
    if unlinked_only:
        query = query.filter(Report.case_id == None)
    return query.order_by(Report.created_at.desc()).limit(limit).all()

@router.get("/my", response_model=List[ReportPublic])
def list_my_reports(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return db.query(Report).filter(Report.reporter_id == current_user.id).order_by(Report.created_at.desc()).all()

@router.get("/duplicates/pending", response_model=List[DuplicateCandidatePublic])
def list_pending_duplicates(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.REVIEWER, UserRole.ADMINISTRATOR)),
):
    return (
        db.query(DuplicateCandidate)
        .filter(DuplicateCandidate.status == "PENDING")
        .order_by(DuplicateCandidate.composite_score.desc())
        .all()
    )

@router.post("/duplicates/{candidate_id}/decision", response_model=DuplicateCandidatePublic)
def decide_duplicate(
    candidate_id: str,
    decision_in: DuplicateDecision,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.REVIEWER, UserRole.ADMINISTRATOR)),
):
    candidate = db.query(DuplicateCandidate).filter(DuplicateCandidate.id == candidate_id).first()
    if not candidate:
        raise HTTPException(status_code=404, detail="Duplicate candidate record not found")

    if decision_in.decision == "APPROVE":
        candidate.status = "APPROVED"
        candidate.reviewed_by_id = current_user.id
        candidate.reviewed_at = datetime.now(timezone.utc)

        # Link report to target case
        report = candidate.report
        target_case = candidate.target_case
        report.case_id = target_case.id

        # Recalculate priority of target case with new corroborating report
        all_linked_reports = db.query(Report).filter(Report.case_id == target_case.id).count()
        score, band, breakdown = PriorityEngine.calculate_priority(
            category_weight=target_case.category.default_severity_weight,
            report_count=all_linked_reports,
            created_at=target_case.created_at,
        )
        target_case.priority_score = score
        target_case.priority_band = band
        target_case.priority_breakdown = breakdown

        # Record ledger event
        LedgerService.append_event(
            db=db,
            case=target_case,
            event_type="REPORT_LINKED",
            payload={
                "report_id": report.public_id,
                "similarity_score": candidate.composite_score,
                "notes": decision_in.notes or "Reviewer approved duplicate consolidation",
                "new_priority_score": score,
            },
            actor=current_user,
            public_actor_label="Community Reviewer",
        )
    elif decision_in.decision == "REJECT":
        candidate.status = "REJECTED"
        candidate.reviewed_by_id = current_user.id
        candidate.reviewed_at = datetime.now(timezone.utc)

        # If report is still unlinked, promote to independent case
        report = candidate.report
        if not report.case_id:
            case_count = db.query(Case).count() + 1
            case_public_id = f"CAS-2026-{case_count:04d}"
            
            score, band, breakdown = PriorityEngine.calculate_priority(
                category_weight=report.category.default_severity_weight,
                report_count=1,
                created_at=datetime.now(timezone.utc),
            )
            new_case = Case(
                public_id=case_public_id,
                category_id=report.category_id,
                title=report.title,
                description=report.description,
                latitude=report.latitude,
                longitude=report.longitude,
                address_reference=report.address_reference,
                state=CaseState.SUBMITTED,
                priority_score=score,
                priority_band=band,
                priority_breakdown=breakdown,
            )
            db.add(new_case)
            db.flush()
            report.case_id = new_case.id

            LedgerService.append_event(
                db=db,
                case=new_case,
                event_type="CASE_CREATED_AFTER_DUPLICATE_REJECTION",
                payload={"report_id": report.public_id, "reviewer_notes": decision_in.notes},
                actor=current_user,
                public_actor_label="Community Reviewer",
            )
    else:
        raise HTTPException(status_code=400, detail="Decision must be 'APPROVE' or 'REJECT'")

    db.commit()
    db.refresh(candidate)
    return candidate

ALLOWED_EVIDENCE_MIME_TYPES = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "application/pdf": ".pdf",
}

@router.post("/{report_id}/evidence", response_model=EvidenceAssetPublic, status_code=status.HTTP_201_CREATED)
async def upload_report_evidence(
    report_id: str,
    file: UploadFile = File(...),
    caption: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    report = db.query(Report).filter((Report.id == report_id) | (Report.public_id == report_id)).first()
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")

    # 1. MIME type validation
    if file.content_type not in ALLOWED_EVIDENCE_MIME_TYPES:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Unsupported file format '{file.content_type}'. Allowed types: JPG, PNG, WEBP, PDF."
        )

    # 2. Read and size validation (max 10MB)
    content = await file.read()
    if len(content) > settings.MAX_UPLOAD_SIZE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File exceeds maximum allowed upload size of {settings.MAX_UPLOAD_SIZE_BYTES // (1024*1024)}MB."
        )

    # 3. Compute SHA-256 digest
    sha256_hash = hashlib.sha256(content).hexdigest()

    # 4. Save file safely with extension mapping to prevent executable execution
    ext = ALLOWED_EVIDENCE_MIME_TYPES[file.content_type]
    safe_filename = f"evid_{report.public_id}_{sha256_hash[:16]}{ext}"
    saved_path = os.path.join(settings.UPLOAD_DIR, safe_filename)

    with open(saved_path, "wb") as f:
        f.write(content)

    # 5. Record asset in database
    asset = EvidenceAsset(
        report_id=report.id,
        case_id=report.case_id,
        file_name=file.filename or safe_filename,
        file_path=saved_path,
        file_size=len(content),
        mime_type=file.content_type,
        sha256_hash=sha256_hash,
        caption=caption,
        is_public=True,
    )
    db.add(asset)

    # If linked to a case, record on append-only cryptographic ledger
    if report.case:
        LedgerService.append_event(
            db=db,
            case=report.case,
            event_type="EVIDENCE_ADDED",
            payload={
                "report_id": report.public_id,
                "file_name": asset.file_name,
                "sha256": asset.sha256_hash,
                "size_bytes": asset.file_size,
                "caption": caption,
            },
            actor=current_user,
            public_actor_label="Citizen Observer" if not current_user else current_user.display_name,
        )

    db.commit()
    db.refresh(asset)
    return asset

@router.get("/evidence/{asset_id}/download")
def download_evidence_asset(asset_id: str, db: Session = Depends(get_db)):
    asset = db.query(EvidenceAsset).filter(EvidenceAsset.id == asset_id).first()
    if not asset or not os.path.exists(asset.file_path):
        raise HTTPException(status_code=404, detail="Evidence asset not found on disk")
    return FileResponse(
        path=asset.file_path,
        media_type=asset.mime_type,
        filename=asset.file_name,
    )
