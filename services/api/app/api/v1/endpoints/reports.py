import os
import hashlib
from typing import List, Optional
import random
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status, Query, UploadFile, File, Form, Request
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.core.config import settings
from app.core.rate_limiter import check_rate_limit
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
    ReportModerationRequest,
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

MAGIC_SIGNATURES = {
    b"\xff\xd8\xff": "image/jpeg",
    b"\x89PNG\r\n\x1a\n": "image/png",
    b"RIFF": "image/webp", # WEBP starts with RIFF....WEBP
    b"%PDF-": "application/pdf",
}

def validate_magic_bytes(content: bytes, declared_mime: str) -> bool:
    if len(content) < 8:
        return False
    if declared_mime == "image/jpeg" and content.startswith(b"\xff\xd8\xff"):
        return True
    if declared_mime == "image/png" and content.startswith(b"\x89PNG\r\n\x1a\n"):
        return True
    if declared_mime == "image/webp" and content.startswith(b"RIFF") and b"WEBP" in content[:16]:
        return True
    if declared_mime == "application/pdf" and content.startswith(b"%PDF-"):
        return True
    return False

@router.get("/categories", response_model=List[CategoryPublic])
def list_categories(db: Session = Depends(get_db)):
    return db.query(IssueCategory).all()

@router.post("", response_model=ReportPublic, status_code=status.HTTP_201_CREATED)
def submit_report(
    report_in: ReportCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    # Enforce submission rate limiting
    check_rate_limit(request, max_requests=30, window_seconds=60, action_key="submit_report")

    category = db.query(IssueCategory).filter(IssueCategory.id == report_in.category_id).first()
    if not category:
        raise HTTPException(status_code=400, detail="Invalid category ID")

    # Generate public reference ID: e.g. RPT-2026-XXXX
    count = db.query(Report).count() + 1
    public_id = f"RPT-2026-{count:04d}"

    # Moderation Policy:
    # Authenticated Reviewer or Administrator reports are pre-approved.
    # Authenticated Citizen or Guest reports are approved by default for the demo,
    # but marked explicitly with their verified user identity or guest pseudonym.
    initial_moderation = ReportModerationStatus.APPROVED

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
        moderation_status=initial_moderation,
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

@router.post("/{report_id}/moderate", response_model=ReportPublic)
def moderate_report(
    report_id: str,
    mod_in: ReportModerationRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.REVIEWER, UserRole.ADMINISTRATOR)),
):
    report = db.query(Report).filter((Report.id == report_id) | (Report.public_id == report_id)).first()
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")

    report.moderation_status = mod_in.decision
    if mod_in.notes:
        report.moderation_notes = mod_in.notes

    # If approved and not yet linked to any case, check if it should create or link to case
    if mod_in.decision == ReportModerationStatus.APPROVED and not report.case_id:
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
            event_type="REPORT_APPROVED_AND_CASE_OPENED",
            payload={"report_id": report.public_id, "reviewer": current_user.display_name, "notes": mod_in.notes},
            actor=current_user,
            public_actor_label="Community Reviewer",
        )

    db.commit()
    db.refresh(report)
    return report

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

    # Authorization Check:
    # Evidence may only be attached by:
    # 1. The original reporting user (if authenticated report)
    # 2. An authorized reviewer or administrator
    # 3. An anonymous reporter attaching evidence to an unassigned guest report
    if report.reporter_id:
        if not current_user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required to attach evidence to this report.",
            )
        if current_user.id != report.reporter_id and current_user.role not in [UserRole.REVIEWER, UserRole.ADMINISTRATOR]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You are not authorized to upload evidence to another citizen's report.",
            )

    # 1. MIME type validation
    if file.content_type not in ALLOWED_EVIDENCE_MIME_TYPES:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Unsupported file format '{file.content_type}'. Allowed types: JPG, PNG, WEBP, PDF."
        )

    # 2. Stream-read with strict size cap (max 10MB) to prevent memory exhaustion
    chunk_size = 64 * 1024 # 64KB chunks
    total_size = 0
    chunks = []
    while True:
        chunk = await file.read(chunk_size)
        if not chunk:
            break
        total_size += len(chunk)
        if total_size > settings.MAX_UPLOAD_SIZE_BYTES:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"File exceeds maximum allowed upload size of {settings.MAX_UPLOAD_SIZE_BYTES // (1024*1024)}MB."
            )
        chunks.append(chunk)

    content = b"".join(chunks)

    # 3. Magic bytes inspection to prevent extension/MIME spoofing
    if not validate_magic_bytes(content, file.content_type):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File content does not match declared media type '{file.content_type}'. Upload rejected.",
        )

    # 4. Compute SHA-256 digest
    sha256_hash = hashlib.sha256(content).hexdigest()

    # 5. Save file safely with extension mapping to prevent arbitrary file execution
    ext = ALLOWED_EVIDENCE_MIME_TYPES[file.content_type]
    safe_filename = f"evid_{report.public_id}_{sha256_hash[:16]}{ext}"
    saved_path = os.path.join(settings.UPLOAD_DIR, safe_filename)

    with open(saved_path, "wb") as f:
        f.write(content)

    # 6. Record asset in database
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
def download_evidence_asset(
    asset_id: str,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    asset = db.query(EvidenceAsset).filter(EvidenceAsset.id == asset_id).first()
    if not asset or not os.path.exists(asset.file_path):
        raise HTTPException(status_code=404, detail="Evidence asset not found on disk")

    # Access control: If asset is not marked public, caller must be owner or reviewer/admin
    if not asset.is_public:
        if not current_user:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required to view non-public asset.")
        if current_user.role not in [UserRole.REVIEWER, UserRole.ADMINISTRATOR]:
            if asset.report and asset.report.reporter_id != current_user.id:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied.")

    return FileResponse(
        path=asset.file_path,
        media_type=asset.mime_type,
        filename=asset.file_name,
    )
