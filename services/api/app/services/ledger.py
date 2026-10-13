import hashlib
from typing import Optional, Dict, Any, Tuple
from sqlalchemy.orm import Session
from app.models.entities import Case, CaseEvent, User, IntegrityCheckpoint
from app.core.security import canonical_json
from app.services.crypto_signer import SignerService

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
        from app.core.sequences import allocate_case_event_index

        next_index = allocate_case_event_index(db, case.id)

        # Find latest event for this case to link previous hash
        last_event = (
            db.query(CaseEvent)
            .filter(CaseEvent.case_id == case.id)
            .order_by(CaseEvent.event_index.desc())
            .first()
        )
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

    @staticmethod
    def create_checkpoint(db: Session) -> IntegrityCheckpoint:
        """
        Creates an independently verifiable cryptographic checkpoint for all recorded events.
        Roots all events across the database, signs the state root with Ed25519, and stores
        the checkpoint.
        """
        total_events = db.query(CaseEvent).count()
        last_event = db.query(CaseEvent).order_by(CaseEvent.id.desc()).first()
        latest_event_hash = last_event.current_event_hash if last_event else GENESIS_PREVIOUS_HASH

        last_checkpoint = (
            db.query(IntegrityCheckpoint)
            .order_by(IntegrityCheckpoint.checkpoint_index.desc())
            .first()
        )
        next_checkpoint_index = 1 if not last_checkpoint else last_checkpoint.checkpoint_index + 1

        checkpoint_data = {
            "checkpoint_index": next_checkpoint_index,
            "total_events": total_events,
            "latest_event_hash": latest_event_hash,
        }
        canonical_checkpoint = canonical_json(checkpoint_data).encode("utf-8")
        root_hash = hashlib.sha256(canonical_checkpoint).hexdigest()

        # Digital signature via Ed25519
        sig_b64 = SignerService.sign_bytes(root_hash.encode("utf-8"))
        pub_key_b64 = SignerService.get_public_key_base64()

        checkpoint = IntegrityCheckpoint(
            checkpoint_index=next_checkpoint_index,
            total_events_covered=total_events,
            root_hash=root_hash,
            signature=sig_b64,
            signer_public_key=pub_key_b64,
            signature_algorithm="Ed25519",
        )
        db.add(checkpoint)
        db.flush()
        return checkpoint

    @staticmethod
    def verify_checkpoint(checkpoint: IntegrityCheckpoint) -> bool:
        """
        Verifies the Ed25519 digital signature of an integrity checkpoint.
        """
        if not checkpoint.signature or not checkpoint.signer_public_key:
            return False
        return SignerService.verify_signature(
            data=checkpoint.root_hash.encode("utf-8"),
            signature_b64=checkpoint.signature,
            public_key_b64=checkpoint.signer_public_key,
        )
