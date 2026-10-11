import enum
from datetime import datetime, timezone
import uuid

from sqlalchemy import (
    Column,
    String,
    Integer,
    Float,
    Boolean,
    DateTime,
    ForeignKey,
    Text,
    Enum as SQLEnum,
    Index
)
from sqlalchemy.orm import relationship

from app.db.session import Base

def generate_uuid() -> str:
    return str(uuid.uuid4())

def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class UserRole(str, enum.Enum):
    CITIZEN = "CITIZEN"
    REVIEWER = "REVIEWER"
    OPERATOR = "OPERATOR"
    ADMINISTRATOR = "ADMINISTRATOR"


class CaseState(str, enum.Enum):
    SUBMITTED = "SUBMITTED"
    UNDER_REVIEW = "UNDER_REVIEW"
    VERIFIED = "VERIFIED"
    ASSIGNED = "ASSIGNED"
    IN_PROGRESS = "IN_PROGRESS"
    RESOLUTION_CLAIMED = "RESOLUTION_CLAIMED"
    AWAITING_VERIFICATION = "AWAITING_VERIFICATION"
    RESOLVED = "RESOLVED"
    DISPUTED = "DISPUTED"
    REOPENED = "REOPENED"
    REJECTED = "REJECTED"


class ReportModerationStatus(str, enum.Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    FLAGGED = "FLAGGED"
    REJECTED = "REJECTED"


class VerificationOutcome(str, enum.Enum):
    CONFIRMED_FIXED = "CONFIRMED_FIXED"
    STILL_UNRESOLVED = "STILL_UNRESOLVED"
    PARTIALLY_FIXED = "PARTIALLY_FIXED"
    UNABLE_TO_VERIFY = "UNABLE_TO_VERIFY"


class PriorityBand(str, enum.Enum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class User(Base):
    __tablename__ = "users"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    email = Column(String(255), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    display_name = Column(String(100), nullable=False)
    role = Column(SQLEnum(UserRole), default=UserRole.CITIZEN, nullable=False)
    department_id = Column(String(36), ForeignKey("departments.id"), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)

    department = relationship("Department", back_populates="members")
    reports = relationship("Report", back_populates="reporter")
    case_events = relationship("CaseEvent", back_populates="actor")


class Department(Base):
    __tablename__ = "departments"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    name = Column(String(120), unique=True, nullable=False)
    description = Column(Text, nullable=True)
    service_area_id = Column(String(36), ForeignKey("service_areas.id"), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)

    service_area = relationship("ServiceArea", back_populates="departments")
    members = relationship("User", back_populates="department")
    assignments = relationship("CaseAssignment", back_populates="department")


class ServiceArea(Base):
    __tablename__ = "service_areas"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    name = Column(String(120), unique=True, nullable=False)
    city = Column(String(100), default="Indore", nullable=False)
    # Stored bounding boxes or center for search
    center_latitude = Column(Float, nullable=False)
    center_longitude = Column(Float, nullable=False)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)

    departments = relationship("Department", back_populates="service_area")
    cases = relationship("Case", back_populates="service_area")


class IssueCategory(Base):
    __tablename__ = "issue_categories"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    name = Column(String(100), unique=True, nullable=False)
    code = Column(String(50), unique=True, nullable=False)
    description = Column(Text, nullable=True)
    default_severity_weight = Column(Float, default=1.0, nullable=False) # Factor for civic priority
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)

    reports = relationship("Report", back_populates="category")
    cases = relationship("Case", back_populates="category")


class Report(Base):
    __tablename__ = "reports"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    public_id = Column(String(30), unique=True, index=True, nullable=False) # E.g., RPT-2026-0001
    category_id = Column(String(36), ForeignKey("issue_categories.id"), nullable=False)
    reporter_id = Column(String(36), ForeignKey("users.id"), nullable=True) # None for guest reporting
    guest_pseudonym = Column(String(100), nullable=True) # Privacy-preserving pseudonym for guest

    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=False)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    address_reference = Column(String(255), nullable=True)
    accuracy_meters = Column(Float, nullable=True)

    moderation_status = Column(SQLEnum(ReportModerationStatus), default=ReportModerationStatus.APPROVED, nullable=False)
    moderation_notes = Column(Text, nullable=True)

    case_id = Column(String(36), ForeignKey("cases.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)

    category = relationship("IssueCategory", back_populates="reports")
    reporter = relationship("User", back_populates="reports")
    case = relationship("Case", back_populates="reports")
    evidence_assets = relationship("EvidenceAsset", back_populates="report")

    __table_args__ = (
        Index("idx_reports_coords", "latitude", "longitude"),
    )


class Case(Base):
    __tablename__ = "cases"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    public_id = Column(String(30), unique=True, index=True, nullable=False) # E.g., CAS-2026-0001
    category_id = Column(String(36), ForeignKey("issue_categories.id"), nullable=False)
    service_area_id = Column(String(36), ForeignKey("service_areas.id"), nullable=True)

    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=False)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    address_reference = Column(String(255), nullable=True)

    state = Column(SQLEnum(CaseState), default=CaseState.SUBMITTED, nullable=False)
    priority_score = Column(Float, default=1.0, nullable=False)
    priority_band = Column(SQLEnum(PriorityBand), default=PriorityBand.LOW, nullable=False)
    priority_breakdown = Column(Text, nullable=True) # JSON explainability string

    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)
    verified_at = Column(DateTime(timezone=True), nullable=True)
    resolved_at = Column(DateTime(timezone=True), nullable=True)

    category = relationship("IssueCategory", back_populates="cases")
    service_area = relationship("ServiceArea", back_populates="cases")
    reports = relationship("Report", back_populates="case")
    assignments = relationship("CaseAssignment", back_populates="case")
    events = relationship("CaseEvent", back_populates="case", order_by="CaseEvent.event_index")
    resolution_claims = relationship("ResolutionClaim", back_populates="case")
    verifications = relationship("VerificationObservation", back_populates="case")

    __table_args__ = (
        Index("idx_cases_coords", "latitude", "longitude"),
        Index("idx_cases_state", "state"),
    )


class DuplicateCandidate(Base):
    __tablename__ = "duplicate_candidates"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    report_id = Column(String(36), ForeignKey("reports.id"), nullable=False)
    target_case_id = Column(String(36), ForeignKey("cases.id"), nullable=False)

    distance_meters = Column(Float, nullable=False)
    spatial_score = Column(Float, nullable=False)
    text_score = Column(Float, nullable=False)
    category_score = Column(Float, nullable=False)
    temporal_score = Column(Float, nullable=False)
    composite_score = Column(Float, nullable=False)
    explanation = Column(Text, nullable=False) # JSON or markdown rationale

    status = Column(String(20), default="PENDING", nullable=False) # PENDING, APPROVED, REJECTED
    reviewed_by_id = Column(String(36), ForeignKey("users.id"), nullable=True)
    reviewed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)

    report = relationship("Report")
    target_case = relationship("Case")
    reviewer = relationship("User")


class CaseAssignment(Base):
    __tablename__ = "case_assignments"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    case_id = Column(String(36), ForeignKey("cases.id"), nullable=False)
    department_id = Column(String(36), ForeignKey("departments.id"), nullable=False)
    assigned_by_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    notes = Column(Text, nullable=True)
    assigned_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)

    case = relationship("Case", back_populates="assignments")
    department = relationship("Department", back_populates="assignments")
    assigned_by = relationship("User")


class CaseEvent(Base):
    """
    Append-only evidence and accountability ledger with SHA-256 hash chaining.
    """
    __tablename__ = "case_events"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    case_id = Column(String(36), ForeignKey("cases.id"), nullable=False)
    event_index = Column(Integer, nullable=False) # 1-based sequential index for this case
    event_type = Column(String(50), nullable=False)
    actor_id = Column(String(36), ForeignKey("users.id"), nullable=True)
    public_actor_label = Column(String(100), nullable=False) # E.g., "Citizen Observer", "Public Works Operator"

    payload_json = Column(Text, nullable=False) # Canonical JSON string
    schema_version = Column(Integer, default=1, nullable=False)
    previous_event_hash = Column(String(64), nullable=False)
    current_event_hash = Column(String(64), nullable=False)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)

    case = relationship("Case", back_populates="events")
    actor = relationship("User", back_populates="case_events")

    __table_args__ = (
        Index("idx_case_events_case_idx", "case_id", "event_index", unique=True),
    )


class EvidenceAsset(Base):
    __tablename__ = "evidence_assets"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    report_id = Column(String(36), ForeignKey("reports.id"), nullable=True)
    case_id = Column(String(36), ForeignKey("cases.id"), nullable=True)
    resolution_claim_id = Column(String(36), ForeignKey("resolution_claims.id"), nullable=True)
    verification_id = Column(String(36), ForeignKey("verification_observations.id"), nullable=True)

    file_name = Column(String(255), nullable=False)
    file_path = Column(String(500), nullable=False)
    file_size = Column(Integer, nullable=False)
    mime_type = Column(String(100), nullable=False)
    sha256_hash = Column(String(64), nullable=False)
    caption = Column(String(255), nullable=True)
    is_public = Column(Boolean, default=True, nullable=False)
    uploaded_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)

    report = relationship("Report", back_populates="evidence_assets")
    case = relationship("Case")
    resolution_claim = relationship("ResolutionClaim", back_populates="evidence_assets")
    verification = relationship("VerificationObservation", back_populates="evidence_assets")


class ResolutionClaim(Base):
    __tablename__ = "resolution_claims"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    case_id = Column(String(36), ForeignKey("cases.id"), nullable=False)
    operator_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    work_summary = Column(Text, nullable=False)
    actions_taken = Column(Text, nullable=False)
    claimed_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    status = Column(String(30), default="AWAITING_VERIFICATION", nullable=False) # AWAITING_VERIFICATION, VERIFIED, DISPUTED

    case = relationship("Case", back_populates="resolution_claims")
    operator = relationship("User")
    evidence_assets = relationship("EvidenceAsset", back_populates="resolution_claim")
    verifications = relationship("VerificationObservation", back_populates="resolution_claim")


class VerificationObservation(Base):
    __tablename__ = "verification_observations"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    case_id = Column(String(36), ForeignKey("cases.id"), nullable=False)
    resolution_claim_id = Column(String(36), ForeignKey("resolution_claims.id"), nullable=True)
    verifier_id = Column(String(36), ForeignKey("users.id"), nullable=True) # Citizen verifier or guest
    guest_pseudonym = Column(String(100), nullable=True)

    outcome = Column(SQLEnum(VerificationOutcome), nullable=False)
    notes = Column(Text, nullable=False)
    is_dispute = Column(Boolean, default=False, nullable=False)
    submitted_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)

    case = relationship("Case", back_populates="verifications")
    resolution_claim = relationship("ResolutionClaim", back_populates="verifications")
    verifier = relationship("User")
    evidence_assets = relationship("EvidenceAsset", back_populates="verification")


class RecurrenceRelationship(Base):
    __tablename__ = "recurrence_relationships"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    prior_case_id = Column(String(36), ForeignKey("cases.id"), nullable=False)
    current_case_id = Column(String(36), ForeignKey("cases.id"), nullable=False)
    distance_meters = Column(Float, nullable=False)
    days_since_prior_resolution = Column(Integer, nullable=False)
    confidence_score = Column(Float, nullable=False)
    explanation = Column(Text, nullable=False)
    is_reviewer_confirmed = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)

    prior_case = relationship("Case", foreign_keys=[prior_case_id])
    current_case = relationship("Case", foreign_keys=[current_case_id])


class IntegrityCheckpoint(Base):
    __tablename__ = "integrity_checkpoints"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    checkpoint_index = Column(Integer, unique=True, nullable=False)
    total_events_covered = Column(Integer, nullable=False)
    root_hash = Column(String(64), nullable=False)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
