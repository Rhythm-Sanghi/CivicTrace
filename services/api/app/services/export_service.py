import os
import json
import zipfile
import hashlib
from datetime import datetime, timezone
from typing import Dict, Any, List, Tuple
from sqlalchemy.orm import Session
from app.models.entities import Case, CaseEvent, Report, ResolutionClaim, VerificationObservation
from app.core.security import canonical_json
from app.core.config import settings

class ExportService:
    @staticmethod
    def generate_case_export_package(db: Session, case_id: str) -> str:
        """
        Creates a portable, tamper-verifiable ZIP export for a public case:
        - case_summary.json
        - event_ledger.json
        - observations.json
        - resolution_history.json
        - manifest.json (contains SHA-256 digests of all package artifacts)
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
        reports = db.query(Report).filter(Report.case_id == case.id).all()
        claims = db.query(ResolutionClaim).filter(ResolutionClaim.case_id == case.id).all()
        verifications = db.query(VerificationObservation).filter(VerificationObservation.case_id == case.id).all()

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
            "export_schema_version": "1.0",
        }

        events_doc = [
            {
                "event_index": e.event_index,
                "event_type": e.event_type,
                "public_actor_label": e.public_actor_label,
                "payload": json.loads(e.payload_json),
                "previous_event_hash": e.previous_event_hash,
                "current_event_hash": e.current_event_hash,
                "timestamp": e.created_at.isoformat(),
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
        export_filename = f"civictrace_case_{case.public_id}_{int(datetime.now(timezone.utc).timestamp())}.zip"
        zip_path = os.path.join(settings.EXPORT_DIR, export_filename)

        files_to_pack = {
            "case_summary.json": canonical_json(summary_doc).encode("utf-8"),
            "event_ledger.json": canonical_json(events_doc).encode("utf-8"),
            "observations.json": canonical_json(observations_doc).encode("utf-8"),
            "resolution_history.json": canonical_json(resolutions_doc).encode("utf-8"),
        }

        # Calculate digests for manifest
        manifest_files = {}
        for fname, data_bytes in files_to_pack.items():
            digest = hashlib.sha256(data_bytes).hexdigest()
            manifest_files[fname] = {
                "sha256": digest,
                "byte_size": len(data_bytes),
            }

        manifest_doc = {
            "format": "CivicTrace Public Evidence Package",
            "version": "1.0",
            "case_id": case.public_id,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "files": manifest_files,
        }
        manifest_bytes = canonical_json(manifest_doc).encode("utf-8")
        files_to_pack["manifest.json"] = manifest_bytes

        # Create zip archive
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for fname, data_bytes in files_to_pack.items():
                zf.writestr(fname, data_bytes)

        return zip_path

    @staticmethod
    def verify_export_package(zip_path: str) -> Tuple[bool, List[str]]:
        """
        Standalone integrity verifier that parses a ZIP export and validates
        every artifact against the canonical manifest.json digests.
        """
        logs = []
        if not os.path.exists(zip_path):
            return False, [f"Export file not found: {zip_path}"]

        try:
            with zipfile.ZipFile(zip_path, "r") as zf:
                file_list = zf.namelist()
                # Security: Zip Slip / Path Traversal Guard
                for member in file_list:
                    if ".." in member or member.startswith("/") or member.startswith("\\"):
                        return False, [f"SECURITY VULNERABILITY: Malicious path traversal detected in member name '{member}'"]

                manifest_data = json.loads(zf.read("manifest.json").decode("utf-8"))
                expected_files = manifest_data.get("files", {})

                for fname, meta in expected_files.items():
                    if ".." in fname or fname.startswith("/") or fname.startswith("\\"):
                        return False, [f"SECURITY VULNERABILITY: Malicious path traversal declared in manifest entry '{fname}'"]

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

            logs.append("SUCCESS: All package artifacts verified against cryptographic manifest.")
            return True, logs
        except Exception as e:
            return False, [f"Corrupt archive or error reading package: {str(e)}"]
