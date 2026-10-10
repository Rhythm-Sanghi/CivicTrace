from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime, timezone
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
    ) -> Tuple[CaseState, str, str]:
        """
        Evaluates the submitted observation and determines:
        - target_case_state: The new state of the case
        - event_type: Ledger event type for cryptographic tracking
        - actor_label: Canonical actor descriptor
        """
        # Rule 1: Role Guard - Operators strictly blocked
        if user and user.role == UserRole.OPERATOR:
            raise PermissionError("Department operators cannot submit independent verification observations.")

        # Determine effective actor identifier
        actor_id = user.id if user else None
        pseudonym = (guest_pseudonym or "").strip()
        actor_label = user.display_name if user else (pseudonym or "Anonymous Citizen Observer")

        # Rule 2: Anti-Sybil / Deduplication Guard
        # Check if this exact authenticated user or guest pseudonym has already submitted on this case
        existing_obs_query = db.query(VerificationObservation).filter(
            VerificationObservation.case_id == case.id
        )
        if actor_id:
            duplicate_vote = existing_obs_query.filter(VerificationObservation.verifier_id == actor_id).first()
            if duplicate_vote:
                raise ValueError("You have already submitted a verification observation for this case.")
        elif pseudonym:
            duplicate_guest = existing_obs_query.filter(
                VerificationObservation.verifier_id == None,
                VerificationObservation.guest_pseudonym.ilike(pseudonym)
            ).first()
            if duplicate_guest:
                raise ValueError(f"An observation under reference '{pseudonym}' has already been recorded for this case.")

        is_dispute = outcome in [VerificationOutcome.STILL_UNRESOLVED, VerificationOutcome.PARTIALLY_FIXED]

        # Rule 3: Contradictory observations trigger instant DISPUTED state
        if is_dispute:
            return CaseState.DISPUTED, "RESOLUTION_DISPUTED", actor_label

        # Rule 4: Confirmation Evaluation
        if outcome == VerificationOutcome.CONFIRMED_FIXED:
            # If privileged Community Reviewer or Administrator confirms: immediate verified closure
            if user and user.role in [UserRole.REVIEWER, UserRole.ADMINISTRATOR]:
                return CaseState.RESOLVED, "RESOLUTION_VERIFIED_AND_CLOSED", actor_label

            # For unauthenticated guest observers, record the confirmation but do not count toward quorum auto-closure
            if not user:
                return case.state, "GUEST_VERIFICATION_LOGGED", f"Guest: {actor_label}"

            # For authenticated citizen verifications, count previous confirmed observations from authenticated users
            prior_confirmations = (
                db.query(VerificationObservation)
                .filter(
                    VerificationObservation.case_id == case.id,
                    VerificationObservation.outcome == VerificationOutcome.CONFIRMED_FIXED,
                    VerificationObservation.verifier_id != None,
                )
                .count()
            )
            total_after_this = prior_confirmations + 1

            if total_after_this >= settings.CONFIRMATIONS_REQUIRED_FOR_AUTO_RESOLVE:
                return CaseState.RESOLVED, "RESOLUTION_VERIFIED_AND_CLOSED", actor_label
            else:
                # Quorum not reached yet; state remains AWAITING_VERIFICATION but progress is logged
                return case.state, "VERIFICATION_CONFIRMATION_LOGGED", actor_label

        # Other observations (e.g. UNABLE_TO_VERIFY)
        return case.state, "VERIFICATION_OBSERVATION_SUBMITTED", actor_label
