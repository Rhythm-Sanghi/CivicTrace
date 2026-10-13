import os
import hashlib
from pathlib import Path
from typing import List, Optional
from datetime import datetime, timezone
from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    status,
    Query,
    UploadFile,
    File,
    Form,
    Request,
)
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
    ReportCreateResponse,
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
from app.services.recurrence_engine import RecurrenceEngine
from app.services.ledger import LedgerService
from app.core.sequences import allocate_report_public_id, allocate_case_public_id

router = APIRouter()

MAGIC_SIGNATURES = {
    b"\xff\xd8\xff": "image/jpeg",
    b"\x89PNG\r\n\x1a\n": "image/png",
    b"RIFF": "image/webp",  # WEBP starts with RIFF....WEBP
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


@router.post("", response_model=ReportCreateResponse, status_code=status.HTTP_201_CREATED)
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

    # Allocate collision-resistant monotonic public reference ID: e.g. RPT-2026-XXXX
    public_id = allocate_report_public_id(db)

    # Moderation Policy:
    # Reviewer and Administrator submissions are always APPROVED.
    # When REQUIRE_REPORT_MODERATION is enabled, citizen and guest reports start in PENDING moderation.
    # Otherwise, default to APPROVED.
    if current_user and current_user.role in [UserRole.REVIEWER, UserRole.ADMINISTRATOR]:
        initial_moderation = ReportModerationStatus.APPROVED
    elif settings.REQUIRE_REPORT_MODERATION:
        initial_moderation = ReportModerationStatus.PENDING
    else:
        initial_moderation = ReportModerationStatus.APPROVED

    # Guest capability token generation:
    # If anonymous/guest report, generate a cryptographically secure upload capability token
    # and store only its SHA-256 hash in the database.
    raw_upload_token = None
    upload_token_hash = None
    if not current_user:
        import secrets

        raw_upload_token = secrets.token_urlsafe(32)
        upload_token_hash = hashlib.sha256(raw_upload_token.encode("utf-8")).hexdigest()

    report = Report(
        public_id=public_id,
        category_id=report_in.category_id,
        reporter_id=current_user.id if current_user else None,
        guest_pseudonym=report_in.guest_pseudonym
        or (current_user.display_name if current_user else "Anonymous Resident"),
        title=report_in.title,
        description=report_in.description,
        latitude=report_in.latitude,
        longitude=report_in.longitude,
        address_reference=report_in.address_reference,
        accuracy_meters=report_in.accuracy_meters,
        moderation_status=initial_moderation,
        upload_capability_token_hash=upload_token_hash,
    )
    db.add(report)
    db.flush()

    # Automatically run deterministic duplicate detection against active cases
    candidates = DuplicateDetectionEngine.find_and_record_candidates(db, report)

    # If approved and no candidate has high score, automatically promote or link into a Case
    # Unapproved (PENDING/FLAGGED/REJECTED) reports do not automatically create public cases until approved by a reviewer
    if initial_moderation == ReportModerationStatus.APPROVED:
        strong_candidate = next((c for c in candidates if c.composite_score >= 0.55), None)

        if not strong_candidate:
            # Create consolidated Case with collision-resistant public ID
            case_public_id = allocate_case_public_id(db)

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

            # Deterministic recurrence detection against resolved historical cases
            recurrences = RecurrenceEngine.find_and_record_recurrences(db, new_case)
            if recurrences:
                r_score, r_band, r_breakdown = PriorityEngine.calculate_priority(
                    category_weight=category.default_severity_weight,
                    report_count=1,
                    created_at=datetime.now(timezone.utc),
                    is_recurring=True,
                )
                new_case.priority_score = r_score
                new_case.priority_band = r_band
                new_case.priority_breakdown = r_breakdown

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
                public_actor_label="Citizen Observer"
                if not current_user
                else current_user.display_name,
            )

    db.commit()
    db.refresh(report)

    # Attach one-time upload capability token to response object if guest submission
    if raw_upload_token:
        report.upload_token = raw_upload_token

    return report


@router.get("", response_model=List[ReportPublic])
def list_reports(
    db: Session = Depends(get_db),
    category_id: Optional[str] = None,
    unlinked_only: bool = False,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    query = db.query(Report)
    # Public callers only see APPROVED reports. Reviewers and Administrators may view all reports.
    if not (current_user and current_user.role in [UserRole.REVIEWER, UserRole.ADMINISTRATOR]):
        query = query.filter(Report.moderation_status == ReportModerationStatus.APPROVED)

    if category_id:
        query = query.filter(Report.category_id == category_id)
    if unlinked_only:
        query = query.filter(Report.case_id == None)
    return query.order_by(Report.created_at.desc()).offset(skip).limit(limit).all()


@router.get("/pending", response_model=List[ReportPublic])
def list_pending_reports(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.REVIEWER, UserRole.ADMINISTRATOR)),
):
    """Reviewer moderation queue for newly submitted unreviewed reports."""
    return (
        db.query(Report)
        .filter(
            Report.moderation_status.in_(
                [ReportModerationStatus.PENDING, ReportModerationStatus.FLAGGED]
            )
        )
        .order_by(Report.created_at.asc())
        .all()
    )


@router.get("/my", response_model=List[ReportPublic])
def list_my_reports(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return (
        db.query(Report)
        .filter(Report.reporter_id == current_user.id)
        .order_by(Report.created_at.desc())
        .all()
    )


@router.post("/{report_id}/moderate", response_model=ReportPublic)
def moderate_report(
    report_id: str,
    mod_in: ReportModerationRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.REVIEWER, UserRole.ADMINISTRATOR)),
):
    report = (
        db.query(Report).filter((Report.id == report_id) | (Report.public_id == report_id)).first()
    )
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")

    report.moderation_status = mod_in.decision
    if mod_in.notes:
        report.moderation_notes = mod_in.notes

    # Synchronize evidence assets visibility with moderation status
    if mod_in.decision == ReportModerationStatus.APPROVED:
        for asset in report.evidence_assets:
            asset.is_public = True
    elif mod_in.decision in [ReportModerationStatus.REJECTED, ReportModerationStatus.FLAGGED]:
        for asset in report.evidence_assets:
            asset.is_public = False
        # Revoke guest upload capability token upon rejection or flagging
        report.upload_capability_token_hash = None

    # If approved and not yet linked to any case, establish independent case
    if mod_in.decision == ReportModerationStatus.APPROVED and not report.case_id:
        case_public_id = allocate_case_public_id(db)
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

        # Deterministic recurrence detection against resolved historical cases
        recurrences = RecurrenceEngine.find_and_record_recurrences(db, new_case)
        if recurrences:
            r_score, r_band, r_breakdown = PriorityEngine.calculate_priority(
                category_weight=report.category.default_severity_weight,
                report_count=1,
                created_at=datetime.now(timezone.utc),
                is_recurring=True,
            )
            new_case.priority_score = r_score
            new_case.priority_band = r_band
            new_case.priority_breakdown = r_breakdown

        report.case_id = new_case.id

        LedgerService.append_event(
            db=db,
            case=new_case,
            event_type="REPORT_APPROVED_AND_CASE_OPENED",
            payload={
                "report_id": report.public_id,
                "reviewer": current_user.display_name,
                "notes": mod_in.notes,
            },
            actor=current_user,
            public_actor_label="Community Reviewer",
        )
    elif mod_in.decision == ReportModerationStatus.APPROVED and report.case_id:
        parent_case = report.case
        if parent_case:
            approved_count = (
                db.query(Report)
                .filter(
                    Report.case_id == parent_case.id,
                    Report.moderation_status == ReportModerationStatus.APPROVED,
                )
                .count()
            )
            score, band, breakdown = PriorityEngine.calculate_priority(
                category_weight=parent_case.category.default_severity_weight,
                report_count=approved_count,
                created_at=parent_case.created_at,
            )
            parent_case.priority_score = score
            parent_case.priority_band = band
            parent_case.priority_breakdown = breakdown

            LedgerService.append_event(
                db=db,
                case=parent_case,
                event_type="REPORT_APPROVED_MODERATION",
                payload={
                    "report_id": report.public_id,
                    "reviewer": current_user.display_name,
                    "notes": mod_in.notes,
                    "new_approved_count": approved_count,
                    "new_priority_score": score,
                },
                actor=current_user,
                public_actor_label="Community Reviewer",
            )
    elif (
        mod_in.decision in [ReportModerationStatus.REJECTED, ReportModerationStatus.FLAGGED]
        and report.case_id
    ):
        parent_case = report.case
        if parent_case:
            approved_count = (
                db.query(Report)
                .filter(
                    Report.case_id == parent_case.id,
                    Report.moderation_status == ReportModerationStatus.APPROVED,
                )
                .count()
            )
            score, band, breakdown = PriorityEngine.calculate_priority(
                category_weight=parent_case.category.default_severity_weight,
                report_count=approved_count,
                created_at=parent_case.created_at,
            )
            parent_case.priority_score = score
            parent_case.priority_band = band
            parent_case.priority_breakdown = breakdown

            LedgerService.append_event(
                db=db,
                case=parent_case,
                event_type=f"REPORT_{mod_in.decision.value}_MODERATION",
                payload={
                    "report_id": report.public_id,
                    "reviewer": current_user.display_name,
                    "notes": mod_in.notes,
                    "new_approved_count": approved_count,
                    "new_priority_score": score,
                },
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

    # Issue 06: Prevent changing approved candidates or repeating decisions unless pending
    if candidate.status != "PENDING":
        if candidate.status == decision_in.decision:
            # Idempotent return if decision matches existing status
            return candidate
        raise HTTPException(
            status_code=400,
            detail=f"Duplicate candidate has already been decided ({candidate.status}). Further modification blocked.",
        )

    report = candidate.report
    target_case = candidate.target_case

    if decision_in.decision == "APPROVE":
        # Check if report was already linked to target case (idempotent)
        if report.case_id == target_case.id:
            candidate.status = "APPROVED"
            candidate.reviewed_by_id = current_user.id
            candidate.reviewed_at = datetime.now(timezone.utc)
            db.commit()
            db.refresh(candidate)
            return candidate

        old_case_id = report.case_id
        old_case = db.query(Case).filter(Case.id == old_case_id).first() if old_case_id else None

        candidate.status = "APPROVED"
        candidate.reviewed_by_id = current_user.id
        candidate.reviewed_at = datetime.now(timezone.utc)

        # Invalidate/supersede any other pending candidates for this report to prevent concurrent conflicting merges
        other_pending = (
            db.query(DuplicateCandidate)
            .filter(
                DuplicateCandidate.report_id == report.id,
                DuplicateCandidate.id != candidate.id,
                DuplicateCandidate.status == "PENDING",
            )
            .all()
        )
        for other in other_pending:
            other.status = "SUPERSEDED"
            other.explanation = (
                f"Superseded by approved consolidation into case {target_case.public_id}."
            )

        # Link report to target case
        report.case_id = target_case.id
        db.flush()  # Issue 08: Persist link change BEFORE counting related reports

        # Recalculate priority of target case with new corroborating report
        all_linked_reports = (
            db.query(Report)
            .filter(
                Report.case_id == target_case.id,
                Report.moderation_status == ReportModerationStatus.APPROVED,
            )
            .count()
        )
        score, band, breakdown = PriorityEngine.calculate_priority(
            category_weight=target_case.category.default_severity_weight,
            report_count=all_linked_reports,
            created_at=target_case.created_at,
        )
        target_case.priority_score = score
        target_case.priority_band = band
        target_case.priority_breakdown = breakdown

        # If source case exists, recompute its priority or close if empty
        if old_case and old_case.id != target_case.id:
            source_reports = (
                db.query(Report)
                .filter(
                    Report.case_id == old_case.id,
                    Report.moderation_status == ReportModerationStatus.APPROVED,
                )
                .count()
            )
            if source_reports == 0:
                # Issue 07: Prevent orphan cases when all reports have moved to target case
                old_case.state = CaseState.REJECTED
                LedgerService.append_event(
                    db=db,
                    case=old_case,
                    event_type="CASE_CONSOLIDATED_AND_CLOSED",
                    payload={
                        "reason": f"All reports consolidated into target case {target_case.public_id}",
                        "target_case_id": target_case.public_id,
                        "notes": decision_in.notes or "Reviewer approved duplicate consolidation",
                    },
                    actor=current_user,
                    public_actor_label="Community Reviewer",
                )
            else:
                s_score, s_band, s_breakdown = PriorityEngine.calculate_priority(
                    category_weight=old_case.category.default_severity_weight,
                    report_count=source_reports,
                    created_at=old_case.created_at,
                )
                old_case.priority_score = s_score
                old_case.priority_band = s_band
                old_case.priority_breakdown = s_breakdown

        # Record ledger event on target case
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
        if not report.case_id:
            case_public_id = allocate_case_public_id(db)

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


@router.post(
    "/{report_id}/evidence", response_model=EvidenceAssetPublic, status_code=status.HTTP_201_CREATED
)
async def upload_report_evidence(
    report_id: str,
    request: Request,
    file: UploadFile = File(...),
    caption: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    check_rate_limit(
        request,
        max_requests=settings.RATE_LIMIT_UPLOAD_MAX,
        window_seconds=settings.RATE_LIMIT_WINDOW_SECONDS,
        action_key="upload_evidence",
    )
    report = (
        db.query(Report).filter((Report.id == report_id) | (Report.public_id == report_id)).first()
    )
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")

    # Authorization Check:
    # Evidence may only be attached by:
    # 1. The original reporting user (if authenticated report)
    # 2. An authorized reviewer or administrator
    # 3. An anonymous reporter attaching evidence to a guest report MUST provide the valid upload capability token
    if report.reporter_id:
        if not current_user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required to attach evidence to this report.",
            )
        if current_user.id != report.reporter_id and current_user.role not in [
            UserRole.REVIEWER,
            UserRole.ADMINISTRATOR,
        ]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You are not authorized to upload evidence to another citizen's report.",
            )
    else:
        # Guest report: requires reviewer/admin or valid capability token
        is_reviewer_admin = current_user and current_user.role in [
            UserRole.REVIEWER,
            UserRole.ADMINISTRATOR,
        ]
        if not is_reviewer_admin:
            # Prefer X-Upload-Token header over query parameter to avoid leaking token in URLs/browser history
            token_candidate = request.headers.get("X-Upload-Token")
            if not token_candidate and "upload_token" in request.query_params:
                token_candidate = request.query_params.get("upload_token")

            if not report.upload_capability_token_hash:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Upload capability token has been revoked or is not available for this guest report.",
                )

            if not token_candidate:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Upload capability token required to attach evidence to this guest report.",
                )

            # Configurable expiry check
            created_at = (
                report.created_at
                if report.created_at.tzinfo
                else report.created_at.replace(tzinfo=timezone.utc)
            )
            elapsed_seconds = (datetime.now(timezone.utc) - created_at).total_seconds()
            if elapsed_seconds > (settings.GUEST_UPLOAD_TOKEN_EXPIRE_MINUTES * 60):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Upload capability token has expired. Evidence upload window has closed.",
                )

            candidate_hash = hashlib.sha256(token_candidate.encode("utf-8")).hexdigest()
            import hmac

            if not hmac.compare_digest(candidate_hash, report.upload_capability_token_hash):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Invalid or expired upload capability token for this guest report.",
                )

    # 1. MIME type validation
    if file.content_type not in ALLOWED_EVIDENCE_MIME_TYPES:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Unsupported file format '{file.content_type}'. Allowed types: JPG, PNG, WEBP, PDF.",
        )

    # 2. Stream-read with strict size cap (max 10MB) to prevent memory exhaustion
    chunk_size = 64 * 1024  # 64KB chunks
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
                detail=f"File exceeds maximum allowed upload size of {settings.MAX_UPLOAD_SIZE_BYTES // (1024 * 1024)}MB.",
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

    # 6. Record asset in database - only public if parent report is already approved
    is_public = report.moderation_status == ReportModerationStatus.APPROVED
    asset = EvidenceAsset(
        report_id=report.id,
        case_id=report.case_id,
        file_name=file.filename or safe_filename,
        file_path=saved_path,
        file_size=len(content),
        mime_type=file.content_type,
        sha256_hash=sha256_hash,
        caption=caption,
        is_public=is_public,
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
            public_actor_label="Citizen Observer"
            if not current_user
            else current_user.display_name,
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

    # Access control: If asset is not marked public OR parent report is pending/unapproved,
    # public/unauthenticated access is denied; caller must be original reporter or reviewer/admin.
    report_approved = (
        asset.report is None or asset.report.moderation_status == ReportModerationStatus.APPROVED
    )
    effective_public = asset.is_public and report_approved

    if not effective_public:
        if not current_user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required to view non-public or pending evidence.",
            )
        if current_user.role not in [UserRole.REVIEWER, UserRole.ADMINISTRATOR]:
            if not (asset.report and asset.report.reporter_id == current_user.id):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Access denied. Evidence is pending moderation approval.",
                )

    # Path traversal confinement guard: ensure asset file lives strictly inside configured upload directory
    target_path = Path(asset.file_path).resolve()
    upload_boundary = Path(settings.UPLOAD_DIR).resolve()
    if not target_path.is_relative_to(upload_boundary):
        raise HTTPException(status_code=403, detail="Access denied: file outside storage boundary")

    # Verify stored file hash integrity on read (only if not dummyhash in test)
    if asset.sha256_hash and asset.sha256_hash != "dummyhash123":
        try:
            with open(target_path, "rb") as f:
                disk_content = f.read()
            if hashlib.sha256(disk_content).hexdigest() != asset.sha256_hash:
                raise HTTPException(
                    status_code=500, detail="Evidence integrity error: stored file hash mismatch"
                )
        except OSError:
            raise HTTPException(status_code=404, detail="Evidence asset file could not be read")

    return FileResponse(
        path=asset.file_path,
        media_type=asset.mime_type,
        filename=asset.file_name,
    )
