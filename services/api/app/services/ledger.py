import hashlib
from typing import Optional, Dict, Any, Tuple
from sqlalchemy.orm import Session
from app.models.entities import Case, CaseEvent, User
from app.core.security import canonical_json

GENESIS_PREVIOUS_HASH = "0" * 64

class LedgerService:
    @staticmethod
    def append_event(
        db: Session,
        case: Case,
        event_type: str,
        payload: Dict[str, Any],
        actor: Optional[User] = None,
        public_actor_label: Optional[str] = None,
    ) -> CaseEvent:
        """
        Appends an event to the append-only ledger for the given case.
        Computes SHA-256 hash chaining:
        current_event_hash = SHA256(previous_event_hash + canonical_json(event_metadata_and_payload))
        """
        # Find latest event for this case
        last_event = (
            db.query(CaseEvent)
            .filter(CaseEvent.case_id == case.id)
            .order_by(CaseEvent.event_index.desc())
            .first()
        )

        next_index = 1 if not last_event else last_event.event_index + 1
        previous_hash = GENESIS_PREVIOUS_HASH if not last_event else last_event.current_event_hash

        if not public_actor_label:
            if actor:
                if actor.role.value == "CITIZEN":
                    public_actor_label = "Citizen Observer"
                elif actor.role.value == "REVIEWER":
                    public_actor_label = "Community Reviewer"
                elif actor.role.value == "OPERATOR":
                    public_actor_label = "Public Works Operator"
                elif actor.role.value == "ADMINISTRATOR":
                    public_actor_label = "System Administrator"
                else:
                    public_actor_label = "System"
            else:
                public_actor_label = "System Event"

        payload_serialized = canonical_json(payload)

        # Hash structure: string with previous_hash, case_id, event_index, event_type, payload
        hash_preimage = f"{previous_hash}|{case.id}|{next_index}|{event_type}|{payload_serialized}"
        current_hash = hashlib.sha256(hash_preimage.encode("utf-8")).hexdigest()

        event = CaseEvent(
            case_id=case.id,
            event_index=next_index,
            event_type=event_type,
            actor_id=actor.id if actor else None,
            public_actor_label=public_actor_label,
            payload_json=payload_serialized,
            schema_version=1,
            previous_event_hash=previous_hash,
            current_event_hash=current_hash,
        )
        db.add(event)
        db.flush()
        return event

    @staticmethod
    def verify_chain(db: Session, case_id: str) -> Tuple[bool, int, Optional[str], Optional[str]]:
        """
        Verifies the cryptographic hash integrity of the entire event timeline for a case.
        Returns: (is_valid, total_events, error_message, latest_hash)
        """
        events = (
            db.query(CaseEvent)
            .filter(CaseEvent.case_id == case_id)
            .order_by(CaseEvent.event_index.asc())
            .all()
        )

        if not events:
            return True, 0, None, None

        expected_previous_hash = GENESIS_PREVIOUS_HASH
        for idx, event in enumerate(events, start=1):
            if event.event_index != idx:
                return (
                    False,
                    len(events),
                    f"Index sequence broken at event {event.id}: expected index {idx}, got {event.event_index}",
                    None,
                )

            if event.previous_event_hash != expected_previous_hash:
                return (
                    False,
                    len(events),
                    f"Previous hash link mismatch at event index {idx} ({event.id}): expected {expected_previous_hash}, got {event.previous_event_hash}",
                    None,
                )

            # Recompute current hash
            hash_preimage = f"{event.previous_event_hash}|{event.case_id}|{event.event_index}|{event.event_type}|{event.payload_json}"
            recomputed_hash = hashlib.sha256(hash_preimage.encode("utf-8")).hexdigest()

            if recomputed_hash != event.current_event_hash:
                return (
                    False,
                    len(events),
                    f"Hash computation tampering detected at event index {idx} ({event.id}): payload or properties altered",
                    None,
                )

            expected_previous_hash = event.current_event_hash

        return True, len(events), None, expected_previous_hash
