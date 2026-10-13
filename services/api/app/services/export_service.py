import os
import json
import zipfile
import hashlib
from datetime import datetime, timezone
from typing import List, Tuple, Optional, Union
from sqlalchemy.orm import Session
from app.models.entities import (
    Case,
    CaseEvent,
    Report,
    ResolutionClaim,
    VerificationObservation,
    EvidenceAsset,
    ReportModerationStatus,
)
from app.core.security import canonical_json
from app.core.config import settings
from app.services.crypto_signer import SignerService

from enum import Enum


class VerificationMode(str, Enum):
    FILE_INTEGRITY = "file_integrity"
    TRUSTED_AUTHENTICITY = "trusted_authenticity"


class ExportService:
    @staticmethod
    def generate_case_export_package(db: Session, case_id: str) -> str:
        """
        Creates a portable, tamper-verifiable ZIP export for a public case:
        - case_summary.json
        - event_ledger.json
        - observations.json
        - resolution_history.json
        - evidence/ (authorized/approved evidence files with preserved digests)
        - manifest.json (contains SHA-256 digests and Ed25519 digital signature)
        Returns the absolute path to the generated zip file.
        """
        case = db.query(Case).filter(Case.id == case_id).first()
        if not case:
            raise ValueError(f"Case {case_id} not found")

        events = (
            db.query(CaseEvent)
            .filter(CaseEvent.case_id == case.id)
            .order_by(CaseEvent.event_index.asc())
            .all()
        )
        reports = (
            db.query(Report)
            .filter(
                Report.case_id == case.id,
                Report.moderation_status == ReportModerationStatus.APPROVED,
            )
            .all()
        )
        claims = db.query(ResolutionClaim).filter(ResolutionClaim.case_id == case.id).all()
        verifications = (
            db.query(VerificationObservation)
            .filter(VerificationObservation.case_id == case.id)
            .all()
        )

        # Build documents
        summary_doc = {
            "public_id": case.public_id,
            "title": case.title,
            "description": case.description,
            "category": case.category.name if case.category else "Uncategorized",
            "state": case.state.value,
            "priority_band": case.priority_band.value,
            "priority_score": case.priority_score,
            "coordinates": {"latitude": case.latitude, "longitude": case.longitude},
            "created_at": case.created_at.isoformat(),
            "updated_at": case.updated_at.isoformat() if case.updated_at else None,
            "verified_at": case.verified_at.isoformat() if case.verified_at else None,
            "resolved_at": case.resolved_at.isoformat() if case.resolved_at else None,
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "export_schema_version": "1.1",
        }

        from app.services.ledger import LedgerService

        events_doc = [
            {
                "case_id": e.case_id,
                "event_index": e.event_index,
                "event_type": e.event_type,
                "actor_id": e.actor_id,
                "public_actor_label": e.public_actor_label,
                "payload": json.loads(e.payload_json),
                "payload_json": e.payload_json,
                "schema_version": e.schema_version,
                "previous_event_hash": e.previous_event_hash,
                "current_event_hash": e.current_event_hash,
                "timestamp": LedgerService.canonical_iso_timestamp(e.created_at),
            }
            for e in events
        ]

        # Observations with privacy preservation (no email or user IDs)
        observations_doc = [
            {
                "public_id": r.public_id,
                "title": r.title,
                "description": r.description,
                "submitted_at": r.created_at.isoformat(),
                "reporter_pseudonym": r.guest_pseudonym or "Anonymous Citizen",
                "coordinates": {"latitude": r.latitude, "longitude": r.longitude},
            }
            for r in reports
        ]

        resolutions_doc = {
            "claims": [
                {
                    "work_summary": c.work_summary,
                    "actions_taken": c.actions_taken,
                    "claimed_at": c.claimed_at.isoformat(),
                    "status": c.status,
                }
                for c in claims
            ],
            "verifications": [
                {
                    "outcome": v.outcome.value,
                    "notes": v.notes,
                    "is_dispute": v.is_dispute,
                    "submitted_at": v.submitted_at.isoformat(),
                    "verifier_pseudonym": v.guest_pseudonym or "Independent Citizen Observer",
                }
                for v in verifications
            ],
        }

        # Render files to disk in a temp packaging folder
        export_filename = (
            f"civictrace_case_{case.public_id}_{int(datetime.now(timezone.utc).timestamp())}.zip"
        )
        zip_path = os.path.join(settings.EXPORT_DIR, export_filename)

        files_to_pack = {
            "case_summary.json": canonical_json(summary_doc).encode("utf-8"),
            "event_ledger.json": canonical_json(events_doc).encode("utf-8"),
            "observations.json": canonical_json(observations_doc).encode("utf-8"),
            "resolution_history.json": canonical_json(resolutions_doc).encode("utf-8"),
        }

        # Include authorized evidence assets (approved or public)
        report_ids = [r.id for r in reports]
        if report_ids:
            evidence_assets = (
                db.query(EvidenceAsset)
                .join(Report, EvidenceAsset.report_id == Report.id)
                .filter(
                    EvidenceAsset.report_id.in_(report_ids),
                    Report.moderation_status == ReportModerationStatus.APPROVED,
                )
                .all()
            )
            for asset in evidence_assets:
                if os.path.exists(asset.file_path):
                    safe_name = os.path.basename(asset.file_path)
                    with open(asset.file_path, "rb") as ef:
                        files_to_pack[f"evidence/{safe_name}"] = ef.read()

        # Calculate digests for manifest
        manifest_files = {}
        for fname, data_bytes in files_to_pack.items():
            digest = hashlib.sha256(data_bytes).hexdigest()
            manifest_files[fname] = {
                "sha256": digest,
                "byte_size": len(data_bytes),
            }

        # Sign canonical payload of manifest
        payload_to_sign = {
            "case_id": case.public_id,
            "format": "CivicTrace Public Evidence Package",
            "version": "1.1",
            "files": manifest_files,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }
        signature_b64 = SignerService.sign_bytes(canonical_json(payload_to_sign).encode("utf-8"))
        public_key_b64 = SignerService.get_public_key_base64()

        manifest_doc = {
            **payload_to_sign,
            "signature": signature_b64,
            "signer_algorithm": "Ed25519",
            "signer_public_key": public_key_b64,
        }
        manifest_bytes = canonical_json(manifest_doc).encode("utf-8")
        files_to_pack["manifest.json"] = manifest_bytes

        # Create zip archive
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for fname, data_bytes in files_to_pack.items():
                zf.writestr(fname, data_bytes)

        return zip_path

    @staticmethod
    def verify_export_package(
        zip_path: str,
        mode: Union[VerificationMode, str] = VerificationMode.FILE_INTEGRITY,
        expected_public_key: Optional[str] = None,
        trusted_checkpoint_root: Optional[str] = None,
    ) -> Tuple[bool, List[str]]:
        """
        Standalone integrity and authenticity verifier for CivicTrace export packages.

        Modes:
        - FILE_INTEGRITY: Validates internal zip structure and SHA-256 manifest digests.
          Does NOT claim independent external authenticity.
        - TRUSTED_AUTHENTICITY: Requires an explicit external expected_public_key or trusted_checkpoint_root.
          Fails closed immediately if external trusted material is missing. Never silently downgrades to hash-only.
        """
        logs = []
        if not os.path.exists(zip_path):
            return False, [f"Export file not found: {zip_path}"]

        # Normalize mode
        if isinstance(mode, str):
            try:
                ver_mode = VerificationMode(mode.lower())
            except ValueError:
                return False, [
                    f"Invalid verification mode '{mode}'. Use 'file_integrity' or 'trusted_authenticity'."
                ]
        else:
            ver_mode = mode

        # Fail closed check: Trusted authenticity mode strictly requires trusted external anchor
        if ver_mode == VerificationMode.TRUSTED_AUTHENTICITY:
            if not expected_public_key and not trusted_checkpoint_root:
                return False, [
                    "TRUST ANCHOR ERROR: Trusted authenticity mode requires an explicit external expected_public_key or trusted_checkpoint_root. "
                    "Refusing to downgrade to unauthenticated verification."
                ]

        try:
            with zipfile.ZipFile(zip_path, "r") as zf:
                file_list = zf.namelist()
                # Security: Duplicate zip entry rejection (prevent archive ambiguity attacks)
                if len(file_list) != len(set(file_list)):
                    return False, [
                        "TAMPER DETECTED: Duplicate file entries detected in export package."
                    ]

                # Security: Decompression bomb limit guard (maximum 50MB uncompressed)
                MAX_UNCOMPRESSED_BYTES = 50 * 1024 * 1024
                total_uncompressed = sum(info.file_size for info in zf.infolist())
                if total_uncompressed > MAX_UNCOMPRESSED_BYTES:
                    return False, [
                        "SECURITY VULNERABILITY: Archive exceeds maximum uncompressed size limit."
                    ]

                # Security: Zip Slip / Path Traversal Guard
                for member in file_list:
                    if ".." in member or member.startswith("/") or member.startswith("\\"):
                        return False, [
                            f"SECURITY VULNERABILITY: Malicious path traversal detected in member name '{member}'"
                        ]

                if "manifest.json" not in file_list:
                    return False, ["Corrupt export package: manifest.json missing from root."]

                manifest_data = json.loads(zf.read("manifest.json").decode("utf-8"))
                expected_files = manifest_data.get("files", {})

                # Security: Digital Signature and Authenticity Verification
                sig = manifest_data.get("signature")
                archive_pub_key = manifest_data.get("signer_public_key")

                if ver_mode == VerificationMode.TRUSTED_AUTHENTICITY:
                    if not sig:
                        return False, [
                            "TRUST ANCHOR VIOLATION: Digital signature missing from manifest in trusted authenticity mode."
                        ]

                    if expected_public_key:
                        # Reject key replacement attack (attacker swapping manifest's public key with their own)
                        if archive_pub_key != expected_public_key:
                            return False, [
                                "TRUST ANCHOR VIOLATION: Manifest signer public key does not match trusted public key anchor. "
                                "Key replacement attack rejected."
                            ]

                        manifest_content_to_verify = {
                            "case_id": manifest_data.get("case_id"),
                            "format": manifest_data.get("format"),
                            "version": manifest_data.get("version"),
                            "files": expected_files,
                            "generated_at": manifest_data.get("generated_at"),
                        }
                        sig_valid = SignerService.verify_signature(
                            data=canonical_json(manifest_content_to_verify).encode("utf-8"),
                            signature_b64=sig,
                            public_key_b64=expected_public_key,
                        )
                        if not sig_valid:
                            return False, [
                                "TAMPER DETECTED: Ed25519 manifest digital signature verification failed against trusted public key."
                            ]
                        logs.append(
                            "VERIFIED AUTHENTIC: Ed25519 digital signature authentic against external trust anchor."
                        )
                else:
                    logs.append(
                        "INTEGRITY CHECK ONLY: Manifest hashes verified; independent authenticity NOT established "
                        "(trusted public key not evaluated in file integrity mode)."
                    )

                # Security: Reject undeclared extra files in export package
                declared_set = set(expected_files.keys()) | {"manifest.json"}
                extra_files = set(file_list) - declared_set
                if extra_files:
                    return False, [
                        f"TAMPER DETECTED: Undeclared file(s) found in archive: {', '.join(sorted(extra_files))}"
                    ]

                # Digest validation for all declared package artifacts
                for fname, meta in expected_files.items():
                    if ".." in fname or fname.startswith("/") or fname.startswith("\\"):
                        return False, [
                            f"SECURITY VULNERABILITY: Malicious path traversal declared in manifest entry '{fname}'"
                        ]

                    if fname not in file_list:
                        logs.append(f"MISSING: Declared file {fname} not found in package")
                        return False, logs

                    file_bytes = zf.read(fname)
                    actual_digest = hashlib.sha256(file_bytes).hexdigest()
                    expected_digest = meta["sha256"]

                    if actual_digest != expected_digest:
                        logs.append(
                            f"TAMPER DETECTED in {fname}: expected sha256={expected_digest[:16]}..., got {actual_digest[:16]}..."
                        )
                        return False, logs
                    else:
                        logs.append(f"VERIFIED: {fname} matches digest {actual_digest[:16]}...")

                # Internal ledger integrity & timeline continuity validation
                if "event_ledger.json" in file_list:
                    events_raw = json.loads(zf.read("event_ledger.json").decode("utf-8"))
                    if not isinstance(events_raw, list):
                        return False, [
                            "TAMPER DETECTED: event_ledger.json format invalid; expected array of events."
                        ]

                    expected_prev_hash = "0" * 64
                    case_ref = manifest_data.get("case_id")
                    for idx, ev in enumerate(events_raw, start=1):
                        if ev.get("event_index") != idx:
                            return False, [
                                f"TAMPER DETECTED: Event ledger sequence broken at index {idx} "
                                f"(expected {idx}, got {ev.get('event_index')}). Missing or reordered events detected."
                            ]
                        if ev.get("previous_event_hash") != expected_prev_hash:
                            return False, [
                                f"TAMPER DETECTED: Event ledger hash chain broken at event {idx}."
                            ]

                        # Verify hash preimage integrity via versioned canonicalization
                        from app.services.ledger import LedgerService

                        case_id_val = ev.get("case_id") or case_ref
                        payload_val = (
                            ev.get("payload_json")
                            if "payload_json" in ev
                            else canonical_json(ev["payload"])
                        )
                        calculated_hash = LedgerService.compute_event_hash(
                            schema_version=ev.get("schema_version", 1),
                            previous_event_hash=ev["previous_event_hash"],
                            case_id=case_id_val,
                            event_index=ev["event_index"],
                            event_type=ev["event_type"],
                            actor_id=ev.get("actor_id"),
                            public_actor_label=ev.get("public_actor_label", ""),
                            created_at=ev.get("timestamp"),
                            payload_json=payload_val,
                        )
                        if ev.get("current_event_hash") != calculated_hash:
                            return False, [
                                f"TAMPER DETECTED: Event {idx} current hash mismatch. Event actor, timestamp, or payload was tampered."
                            ]
                        expected_prev_hash = ev["current_event_hash"]

                    logs.append(
                        f"VERIFIED: Event ledger hash chaining verified intact across all {len(events_raw)} events."
                    )

                    # Independent checkpoint verification if checkpoint root was provided
                    if trusted_checkpoint_root:
                        if not events_raw:
                            return False, [
                                "CHECKPOINT VIOLATION: Empty event ledger cannot verify trusted checkpoint root."
                            ]
                        latest_hash = events_raw[-1]["current_event_hash"]
                        if latest_hash != trusted_checkpoint_root:
                            return False, [
                                f"CHECKPOINT VIOLATION: Ledger latest hash {latest_hash} does not match trusted checkpoint root {trusted_checkpoint_root}."
                            ]
                        logs.append("VERIFIED: Ledger latest hash matches trusted checkpoint root.")

            logs.append("SUCCESS: All package artifacts verified against cryptographic manifest.")
            return True, logs
        except Exception as e:
            return False, [f"Corrupt archive or error reading package: {str(e)}"]
