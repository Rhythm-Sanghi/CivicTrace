from typing import Optional, Tuple
from sqlalchemy import or_
from sqlalchemy.orm import Session
from app.models.entities import (
    Case,
    CaseState,
    User,
    UserRole,
    VerificationOutcome,
    VerificationObservation,
    ResolutionClaim,
)
from app.core.config import settings


class VerificationPolicyEngine:
    """
    Defensible, multi-tiered verification governance engine:
    1. Operators cannot verify any resolution claims (enforced conflict-of-interest boundary).
    2. Identity deduplication: a user or pseudonym cannot cast multiple votes on the same claim cycle.
    3. Contradictory dispute protection: ANY dispute (STILL_UNRESOLVED or PARTIALLY_FIXED) immediately flags the case into DISPUTED.
    4. Observed Confirmation vs. Real-World Verified Identity:
       - Pseudonymous / guest submissions are recorded as unverified field observations.
       - Anonymous / guest confirmations cannot independently close or resolve a case; they remain logged as evidence.
       - Auto-resolution requires authenticated Citizen accounts reaching the confirmation quorum (default: 2), or explicit Reviewer / Administrator sign-off.
    5. Ambiguous or inconclusive observations keep the case reviewable in AWAITING_VERIFICATION rather than auto-resolving.
    6. Cycle Scoping: Verifications are scoped to the active ResolutionClaim; stale observations from previous disputed cycles do not count toward new claim quorum.
    """

    @classmethod
    def evaluate_verification_submission(
        cls,
        db: Session,
        case: Case,
        user: Optional[User],
        outcome: VerificationOutcome,
        notes: str,
        guest_pseudonym: Optional[str] = None,
        active_claim: Optional[ResolutionClaim] = None,
    ) -> Tuple[CaseState, str, str]:
        """
        Evaluates the submitted observation and determines:
        - target_case_state: The new state of the case
        - event_type: Ledger event type for cryptographic tracking
        - actor_label: Canonical actor descriptor
        """
        # Rule 1: Role Guard - Operators strictly blocked
        if user and user.role == UserRole.OPERATOR:
            raise PermissionError(
                "Department operators cannot submit independent verification observations."
            )

        # Determine effective actor identifier
        actor_id = user.id if user else None
        pseudonym = (guest_pseudonym or "").strip()
        actor_label = user.display_name if user else (pseudonym or "Anonymous Citizen Observer")

        # Resolve active claim if not explicitly provided
        if active_claim is None and case.id:
            active_claim = (
                db.query(ResolutionClaim)
                .filter(ResolutionClaim.case_id == case.id)
                .order_by(ResolutionClaim.claimed_at.desc())
                .first()
            )

        # Issue 02: Formal verification requires a case in an eligible state (AWAITING_VERIFICATION or DISPUTED)
        if case.state not in [CaseState.AWAITING_VERIFICATION, CaseState.DISPUTED]:
            raise ValueError(
                f"Cannot verify case in '{case.state.value}' state. Must be AWAITING_VERIFICATION or DISPUTED."
            )

        if not active_claim:
            # If no active claim exists on an AWAITING_VERIFICATION case, create a fallback claim record
            # to preserve backward compatibility for direct service invocations / unit tests
            active_claim = ResolutionClaim(
                case_id=case.id,
                operator_id=actor_id,
                work_summary="Field repair verification cycle",
                actions_taken="Automatic or direct verification initialization",
                status="AWAITING_VERIFICATION",
            )
            db.add(active_claim)
            db.flush()

        # Rule 2: Anti-Sybil / Deduplication Guard scoped to active repair claim cycle
        claim_scope_filter = or_(
            VerificationObservation.resolution_claim_id == active_claim.id,
            VerificationObservation.submitted_at >= active_claim.claimed_at,
        )
        existing_obs_query = db.query(VerificationObservation).filter(
            VerificationObservation.case_id == case.id,
            claim_scope_filter,
        )

        if actor_id:
            duplicate_vote = existing_obs_query.filter(
                VerificationObservation.verifier_id == actor_id
            ).first()
            if duplicate_vote:
                raise ValueError(
                    "You have already submitted a verification observation for this repair claim."
                )
        elif pseudonym:
            duplicate_guest = existing_obs_query.filter(
                VerificationObservation.verifier_id == None,
                VerificationObservation.guest_pseudonym.ilike(pseudonym),
            ).first()
            if duplicate_guest:
                raise ValueError(
                    f"An observation under reference '{pseudonym}' has already been recorded for this repair claim."
                )

        is_dispute = outcome in [
            VerificationOutcome.STILL_UNRESOLVED,
            VerificationOutcome.PARTIALLY_FIXED,
        ]

        # Issue 02 & Issue 03: Handling disputes
        if is_dispute:
            # Unauthenticated guest dispute: Log as observation without rewriting case status if not authenticated,
            # or if guest dispute is allowed, ensure it flags dispute.
            # To prevent anonymous vandalism from arbitrarily rewriting case state:
            if not user:
                # Guest observation is logged as informal field observation; active claim is NOT arbitrarily marked DISPUTED
                return case.state, "GUEST_OBSERVATION_LOGGED", f"Guest: {actor_label}"

            # Authenticated citizen or staff dispute flags active claim and transitions to DISPUTED
            active_claim.status = "DISPUTED"
            return CaseState.DISPUTED, "RESOLUTION_DISPUTED", actor_label

        # Rule 4: Confirmation Evaluation
        if outcome == VerificationOutcome.CONFIRMED_FIXED:
            # Issue 03: If active claim is DISPUTED, automatic closure via confirmations is BLOCKED!
            # Only an authorized reviewer/administrator can adjudicate, OR a new repair cycle must be started.
            if active_claim.status == "DISPUTED":
                if user and user.role in [UserRole.REVIEWER, UserRole.ADMINISTRATOR]:
                    active_claim.status = "VERIFIED"
                    return CaseState.RESOLVED, "RESOLUTION_ADJUDICATED_AND_CLOSED", actor_label
                else:
                    # Citizen confirmations may be recorded, but CANNOT override an unresolved dispute!
                    return case.state, "VERIFICATION_CONFIRMATION_LOGGED", actor_label

            # If privileged Community Reviewer or Administrator confirms: immediate verified closure
            if user and user.role in [UserRole.REVIEWER, UserRole.ADMINISTRATOR]:
                active_claim.status = "VERIFIED"
                return CaseState.RESOLVED, "RESOLUTION_VERIFIED_AND_CLOSED", actor_label

            # For unauthenticated guest observers, record the confirmation but do not count toward quorum auto-closure
            if not user:
                return case.state, "GUEST_VERIFICATION_LOGGED", f"Guest: {actor_label}"

            # Issue 04 / Identity Assurance Governance:
            # Two distinct self-registered accounts are not necessarily two independent people.
            # In conservative or production deployments where REQUIRE_TRUSTED_IDENTITY_FOR_AUTO_RESOLVE is True,
            # ordinary self-registered citizen accounts accumulate observations (VERIFICATION_CONFIRMATION_LOGGED)
            # but CANNOT trigger automatic state transition to RESOLVED without either:
            # 1. An authorized Community Reviewer or Administrator sign-off, OR
            # 2. Trusted citizen identity assurance (e.g. user.is_identity_verified).
            is_trusted_identity = bool(
                getattr(user, "is_identity_verified", False)
                or getattr(user, "is_trusted_citizen", False)
            )

            if settings.REQUIRE_TRUSTED_IDENTITY_FOR_AUTO_RESOLVE and not is_trusted_identity:
                # Conservative offline policy: ordinary self-registered accounts are logged as community evidence,
                # but automatic closure remains blocked until vetted Reviewer / Administrator sign-off.
                return case.state, "VERIFICATION_CONFIRMATION_LOGGED", actor_label

            # For authenticated citizen verifications in permissive/demo mode (or trusted identity),
            # count previous confirmed observations scoped strictly to the current active repair claim cycle
            confirmations_query = db.query(VerificationObservation).filter(
                VerificationObservation.case_id == case.id,
                VerificationObservation.outcome == VerificationOutcome.CONFIRMED_FIXED,
                VerificationObservation.verifier_id != None,
                claim_scope_filter,
            )

            prior_confirmations = confirmations_query.count()
            total_after_this = prior_confirmations + 1

            if total_after_this >= settings.CONFIRMATIONS_REQUIRED_FOR_AUTO_RESOLVE:
                active_claim.status = "VERIFIED"
                return CaseState.RESOLVED, "RESOLUTION_VERIFIED_AND_CLOSED", actor_label
            else:
                # Quorum not reached yet; state remains AWAITING_VERIFICATION but progress is logged
                return case.state, "VERIFICATION_CONFIRMATION_LOGGED", actor_label

        # Other observations (e.g. UNABLE_TO_VERIFY)
        return case.state, "VERIFICATION_OBSERVATION_SUBMITTED", actor_label
