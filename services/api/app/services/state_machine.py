from typing import Dict, Set
from app.models.entities import CaseState, UserRole

# Valid state transitions mapping:
# Current State -> Allowed Next States
ALLOWED_TRANSITIONS: Dict[CaseState, Set[CaseState]] = {
    CaseState.SUBMITTED: {CaseState.UNDER_REVIEW, CaseState.VERIFIED, CaseState.REJECTED},
    CaseState.UNDER_REVIEW: {CaseState.VERIFIED, CaseState.REJECTED, CaseState.ASSIGNED},
    CaseState.VERIFIED: {CaseState.ASSIGNED, CaseState.IN_PROGRESS, CaseState.REJECTED},
    CaseState.ASSIGNED: {CaseState.IN_PROGRESS, CaseState.RESOLUTION_CLAIMED},
    CaseState.IN_PROGRESS: {CaseState.RESOLUTION_CLAIMED, CaseState.ASSIGNED},
    CaseState.RESOLUTION_CLAIMED: {CaseState.AWAITING_VERIFICATION, CaseState.RESOLVED, CaseState.DISPUTED},
    CaseState.AWAITING_VERIFICATION: {CaseState.RESOLVED, CaseState.DISPUTED, CaseState.IN_PROGRESS},
    CaseState.RESOLVED: {CaseState.REOPENED},
    CaseState.DISPUTED: {CaseState.IN_PROGRESS, CaseState.UNDER_REVIEW, CaseState.REOPENED},
    CaseState.REOPENED: {CaseState.ASSIGNED, CaseState.IN_PROGRESS, CaseState.UNDER_REVIEW},
    CaseState.REJECTED: set(), # Terminal unless appealed
}

# Role authorizations for transitions
ROLE_TRANSITION_PERMISSIONS: Dict[CaseState, Set[UserRole]] = {
    CaseState.UNDER_REVIEW: {UserRole.REVIEWER, UserRole.ADMINISTRATOR},
    CaseState.VERIFIED: {UserRole.REVIEWER, UserRole.ADMINISTRATOR},
    CaseState.REJECTED: {UserRole.REVIEWER, UserRole.ADMINISTRATOR},
    CaseState.ASSIGNED: {UserRole.REVIEWER, UserRole.OPERATOR, UserRole.ADMINISTRATOR},
    CaseState.IN_PROGRESS: {UserRole.OPERATOR, UserRole.REVIEWER, UserRole.ADMINISTRATOR},
    CaseState.RESOLUTION_CLAIMED: {UserRole.OPERATOR, UserRole.ADMINISTRATOR},
    CaseState.AWAITING_VERIFICATION: {UserRole.OPERATOR, UserRole.REVIEWER, UserRole.ADMINISTRATOR},
    CaseState.RESOLVED: {UserRole.REVIEWER, UserRole.ADMINISTRATOR}, # Operators CANNOT self-resolve!
    CaseState.DISPUTED: {UserRole.CITIZEN, UserRole.REVIEWER, UserRole.ADMINISTRATOR},
    CaseState.REOPENED: {UserRole.REVIEWER, UserRole.CITIZEN, UserRole.ADMINISTRATOR},
}

class CaseStateMachine:
    @staticmethod
    def can_transition(current_state: CaseState, target_state: CaseState, role: UserRole) -> tuple[bool, str]:
        allowed_targets = ALLOWED_TRANSITIONS.get(current_state, set())
        if target_state not in allowed_targets:
            return False, f"Invalid transition from {current_state.value} to {target_state.value}"

        allowed_roles = ROLE_TRANSITION_PERMISSIONS.get(target_state, set())
        if role not in allowed_roles:
            return False, f"Role {role.value} is not authorized to transition case to {target_state.value}"

        return True, ""

    @classmethod
    def transition_case(
        cls,
        db,
        case,
        target_state: CaseState,
        actor,
        notes: str = None,
        event_type: str = None,
        custom_payload: dict = None,
    ):
        """
        Atomically executes state transition, maintains timestamps, and records append-only ledger entry.
        """
        from datetime import datetime, timezone
        from app.services.ledger import LedgerService

        can_trans, err_msg = cls.can_transition(case.state, target_state, actor.role)
        if not can_trans:
            raise PermissionError(err_msg)

        old_state = case.state
        case.state = target_state

        if target_state == CaseState.VERIFIED and not case.verified_at:
            case.verified_at = datetime.now(timezone.utc)
        elif target_state == CaseState.RESOLVED:
            case.resolved_at = datetime.now(timezone.utc)

        actual_event_type = event_type or f"STATE_CHANGED_TO_{target_state.value}"
        payload = custom_payload or {
            "previous_state": old_state.value,
            "new_state": target_state.value,
            "notes": notes,
        }

        public_label = f"{actor.role.value.capitalize()} Action"
        if actor.role == UserRole.REVIEWER:
            public_label = "Community Reviewer"
        elif actor.role == UserRole.OPERATOR:
            public_label = "Public Works Operator"
        elif actor.role == UserRole.CITIZEN:
            public_label = "Citizen Observer"

        LedgerService.append_event(
            db=db,
            case=case,
            event_type=actual_event_type,
            payload=payload,
            actor=actor,
            public_actor_label=public_label,
        )
        return case
