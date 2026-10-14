import enum
from datetime import datetime
from typing import Optional, List, Dict
from pydantic import BaseModel, Field, ConfigDict
from app.models.entities import (
    UserRole,
    CaseState,
    ReportModerationStatus,
    VerificationOutcome,
    PriorityBand,
)


# User schemas
class UserBase(BaseModel):
    email: str
    display_name: str
    role: UserRole = UserRole.CITIZEN


class UserCreate(UserBase):
    password: str


class UserLogin(BaseModel):
    email: str
    password: str


class UserPublic(BaseModel):
    id: str
    email: str
    display_name: str
    role: UserRole
    department_id: Optional[str] = None
    is_identity_verified: bool = False
    identity_provider: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ApprovedVerificationMethod(str, enum.Enum):
    MUNICIPAL_DESK_IN_PERSON = "MUNICIPAL_DESK_IN_PERSON"
    RESIDENCY_AFFIDAVIT_INSPECTION = "RESIDENCY_AFFIDAVIT_INSPECTION"
    COMMUNITY_VOUCHING_SUPERVISION = "COMMUNITY_VOUCHING_SUPERVISION"
    OFFICIAL_SERVICE_CREDENTIAL = "OFFICIAL_SERVICE_CREDENTIAL"


class IdentityEnrollmentRequest(BaseModel):
    verification_method: ApprovedVerificationMethod = Field(
        ...,
        description="Approved local/civic verification method (privacy-preserving, no mandatory commercial/state ID API required)",
    )
    enrollment_reason: str = Field(
        ...,
        min_length=10,
        max_length=500,
        description="Auditable justification for granting identity assurance",
    )
    auditor_notes: Optional[str] = Field(
        None,
        max_length=1000,
        description="Optional municipal audit notes or evidence reference",
    )


class Token(BaseModel):
    access_token: Optional[str] = None
    token_type: str = "bearer"
    user: UserPublic


# Category schemas
class CategoryPublic(BaseModel):
    id: str
    name: str
    code: str
    description: Optional[str] = None
    default_severity_weight: float

    model_config = ConfigDict(from_attributes=True)


# Evidence Asset
class EvidenceAssetPublic(BaseModel):
    id: str
    file_name: str
    file_size: int
    mime_type: str
    sha256_hash: str
    caption: Optional[str] = None
    uploaded_at: datetime

    model_config = ConfigDict(from_attributes=True)


# Report schemas
class ReportCreate(BaseModel):
    category_id: str
    title: str = Field(..., min_length=5, max_length=200)
    description: str = Field(..., min_length=10, max_length=2000)
    latitude: float = Field(..., ge=-90.0, le=90.0)
    longitude: float = Field(..., ge=-180.0, le=180.0)
    address_reference: Optional[str] = None
    accuracy_meters: Optional[float] = None
    guest_pseudonym: Optional[str] = None


class ReportPublic(BaseModel):
    id: str
    public_id: str
    category_id: str
    category: Optional[CategoryPublic] = None
    title: str
    description: str
    latitude: float
    longitude: float
    address_reference: Optional[str] = None
    moderation_status: ReportModerationStatus
    case_id: Optional[str] = None
    guest_pseudonym: Optional[str] = None
    created_at: datetime
    evidence_assets: List[EvidenceAssetPublic] = []

    model_config = ConfigDict(from_attributes=True)


class ReportCreateResponse(ReportPublic):
    upload_token: Optional[str] = (
        None  # Scoped upload capability token (returned strictly once to original submitter)
    )

    model_config = ConfigDict(from_attributes=True)


class ReportModerationRequest(BaseModel):
    decision: ReportModerationStatus
    notes: Optional[str] = None


# Case schemas
class CasePublic(BaseModel):
    id: str
    public_id: str
    category_id: str
    category: Optional[CategoryPublic] = None
    service_area_id: Optional[str] = None
    title: str
    description: str
    latitude: float
    longitude: float
    address_reference: Optional[str] = None
    state: CaseState
    priority_score: float
    priority_band: PriorityBand
    priority_breakdown: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    verified_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None
    report_count: Optional[int] = 0

    model_config = ConfigDict(from_attributes=True)


# Duplicate Candidate
class DuplicateCandidatePublic(BaseModel):
    id: str
    report_id: str
    target_case_id: str
    distance_meters: float
    spatial_score: float
    text_score: float
    category_score: float
    temporal_score: float
    composite_score: float
    explanation: str
    status: str
    created_at: datetime
    target_case: Optional[CasePublic] = None

    model_config = ConfigDict(from_attributes=True)


class DuplicateDecision(BaseModel):
    decision: str  # "APPROVE" or "REJECT"
    notes: Optional[str] = None


# Case Event Ledger
class CaseEventPublic(BaseModel):
    id: str
    case_id: str
    event_index: int
    event_type: str
    public_actor_label: str
    payload_json: str
    schema_version: int
    previous_event_hash: str
    current_event_hash: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CaseEventChainValidation(BaseModel):
    case_id: str
    is_valid: bool
    total_events: int
    error_message: Optional[str] = None
    latest_event_hash: Optional[str] = None


# Resolution Claim
class ResolutionClaimCreate(BaseModel):
    work_summary: str = Field(..., min_length=10)
    actions_taken: str = Field(..., min_length=10)


class ResolutionClaimPublic(BaseModel):
    id: str
    case_id: str
    work_summary: str
    actions_taken: str
    claimed_at: datetime
    status: str
    evidence_assets: List[EvidenceAssetPublic] = []

    model_config = ConfigDict(from_attributes=True)


# Verification
class VerificationCreate(BaseModel):
    outcome: VerificationOutcome
    notes: str = Field(..., min_length=5)
    guest_pseudonym: Optional[str] = None


class VerificationPublic(BaseModel):
    id: str
    case_id: str
    resolution_claim_id: Optional[str] = None
    outcome: VerificationOutcome
    notes: str
    is_dispute: bool
    submitted_at: datetime
    guest_pseudonym: Optional[str] = None
    evidence_assets: List[EvidenceAssetPublic] = []

    model_config = ConfigDict(from_attributes=True)


# Recurrence
class RecurrencePublic(BaseModel):
    id: str
    prior_case_id: str
    current_case_id: str
    distance_meters: float
    days_since_prior_resolution: int
    confidence_score: float
    explanation: str
    is_reviewer_confirmed: bool
    created_at: datetime
    prior_case: Optional[CasePublic] = None
    current_case: Optional[CasePublic] = None

    model_config = ConfigDict(from_attributes=True)


# Neighborhood Metrics
class NeighborhoodStats(BaseModel):
    service_area: str
    open_cases: int
    verified_resolutions: int
    disputed_resolutions: int
    reopened_cases: Optional[int] = 0
    awaiting_verification: int
    total_reports: int
    median_resolution_days: float
    category_counts: Dict[str, int]
    priority_counts: Dict[str, int]
    total_claims: Optional[int] = 0
    verified_claims: Optional[int] = 0
    disputed_claims: Optional[int] = 0
    awaiting_claims: Optional[int] = 0
    total_observations: Optional[int] = 0
    confirmed_observations: Optional[int] = 0
    dispute_observations: Optional[int] = 0
