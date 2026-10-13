import hashlib
from datetime import datetime, timezone
from typing import Optional, Dict, Any, Tuple, Union
from sqlalchemy.orm import Session
from app.models.entities import Case, CaseEvent, User, IntegrityCheckpoint, utc_now
from app.core.security import canonical_json
from app.services.crypto_signer import SignerService

GENESIS_PREVIOUS_HASH = "0" * 64


class LedgerService:
    """
    Cryptographic append-only ledger service for CivicTrace case audit trails.

    Integrity Schema Policy:
    - Schema Version 1 (Historical): Standard hash preimage:
        hash = SHA-256(previous_event_hash | case_id | event_index | event_type | payload_json)
      Legacy Guarantee: Preserves backward compatibility and mathematical verifiability for all
      historical records without mutating past hashes or invalidating existing external signatures.
      Limitation: Schema-v1 records do NOT acquire the stronger actor identity and ISO timestamp
      integrity guarantees introduced in Schema Version 2.
    - Schema Version 2 (Current Default): Enhanced canonical JSON preimage:
        hash = SHA-256(canonical_json({
          schema_version: 2,
          previous_event_hash,
          case_id,
          event_index,
          event_type,
          actor_id,
          public_actor_label,
          timestamp (canonical ISO 8601 UTC),
          payload_json
        }))
      Guarantee: Full cryptographic binding across actor identity, public actor label, exact UTC
      timestamp, sequence index, and event payload. Directly detects any modification to metadata.
    """
    @staticmethod
    def canonical_iso_timestamp(dt: Union[datetime, str]) -> str:
        if isinstance(dt, str):
            dt = datetime.fromisoformat(dt)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        else:
            dt = dt.astimezone(timezone.utc)
        return dt.isoformat()

    @staticmethod
    def compute_event_hash(
        schema_version: int,
        previous_event_hash: str,
        case_id: str,
        event_index: int,
        event_type: str,
        actor_id: Optional[str],
        public_actor_label: str,
        created_at: Union[datetime, str],
        payload_json: str,
    ) -> str:
        if schema_version == 1:
            # Historical Schema Version 1 (preserves backward compatibility and verification of existing records).
            # Note: Legacy schema-v1 records remain verifiable under their original hash chaining pre-image,
            # but do not acquire the stronger actor identity and ISO timestamp integrity guarantees introduced
            # by schema v2. Historical events retain their immutable v1 pre-image to avoid historical signature
            # invalidation and retroactive ledger rewriting.
            hash_preimage = f"{previous_event_hash}|{case_id}|{event_index}|{event_type}|{payload_json}"
            return hashlib.sha256(hash_preimage.encode("utf-8")).hexdigest()
        elif schema_version == 2:
            # Schema Version 2: Cryptographically binds actor identity, public actor label,
            # canonical ISO 8601 UTC timestamp, event type, case ID, event index, payload,
            # schema version, and previous event hash.
            ts_str = LedgerService.canonical_iso_timestamp(created_at)
            preimage_dict = {
                "schema_version": 2,
                "previous_event_hash": previous_event_hash,
                "case_id": case_id,
                "event_index": event_index,
                "event_type": event_type,
                "actor_id": actor_id or "",
                "public_actor_label": public_actor_label,
                "timestamp": ts_str,
                "payload_json": payload_json,
            }
            canonical_str = canonical_json(preimage_dict)
            return hashlib.sha256(canonical_str.encode("utf-8")).hexdigest()
        else:
            raise ValueError(f"Unsupported ledger event schema version: {schema_version}")

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
        Computes cryptographic SHA-256 hash chaining over versioned canonical pre-image.
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
        event_time = utc_now()
        actor_id_val = actor.id if actor else None

        current_hash = LedgerService.compute_event_hash(
            schema_version=2,
            previous_event_hash=previous_hash,
            case_id=case.id,
            event_index=next_index,
            event_type=event_type,
            actor_id=actor_id_val,
            public_actor_label=public_actor_label,
            created_at=event_time,
            payload_json=payload_serialized,
        )

        event = CaseEvent(
            case_id=case.id,
            event_index=next_index,
            event_type=event_type,
            actor_id=actor_id_val,
            public_actor_label=public_actor_label,
            payload_json=payload_serialized,
            schema_version=2,
            previous_event_hash=previous_hash,
            current_event_hash=current_hash,
            created_at=event_time,
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

            # Recompute current hash via versioned canonicalization
            recomputed_hash = LedgerService.compute_event_hash(
                schema_version=event.schema_version,
                previous_event_hash=event.previous_event_hash,
                case_id=event.case_id,
                event_index=event.event_index,
                event_type=event.event_type,
                actor_id=event.actor_id,
                public_actor_label=event.public_actor_label,
                created_at=event.created_at,
                payload_json=event.payload_json,
            )

            if recomputed_hash != event.current_event_hash:
                return (
                    False,
                    len(events),
                    f"Hash computation tampering detected at event index {idx} ({event.id}): actor, timestamp, payload, or metadata altered",
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
