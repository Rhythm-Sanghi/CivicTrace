from typing import List, Dict, Set
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
