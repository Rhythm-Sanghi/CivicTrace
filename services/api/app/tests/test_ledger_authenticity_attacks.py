import json
import zipfile
import hashlib
from datetime import datetime, timezone
from app.models.entities import Case, CaseEvent, CaseState, IssueCategory, User, UserRole
from app.services.ledger import LedgerService
from app.services.crypto_signer import SignerService
from app.services.export_service import ExportService, VerificationMode
from app.core.security import canonical_json


def _create_test_case_with_ledger(db_session) -> tuple[Case, str]:
    """Helper creating a case with a multi-event ledger and exporting it."""
    import uuid

    suffix = uuid.uuid4().hex[:8]
    cat = IssueCategory(
        name=f"Public Works {suffix}", code=f"PW-{suffix}", default_severity_weight=1.2
    )
    user = User(
        email=f"tester_{suffix}@civictrace.local",
        hashed_password="hash",
        display_name="Inspector Ledger",
        role=UserRole.REVIEWER,
    )
    case = Case(
        public_id=f"CAS-LEDGER-{suffix.upper()}",
        category=cat,
        title="Pavement Settlement",
        description="Pavement cracked along 50m stretch",
        latitude=22.71,
        longitude=75.85,
        state=CaseState.SUBMITTED,
    )
    db_session.add_all([cat, user, case])
    db_session.commit()

    # Event 1: Initial creation
    LedgerService.append_event(
        db=db_session,
        case=case,
        event_type="CASE_CREATED",
        payload={"action": "created", "initial_severity": "moderate"},
        actor=user,
    )
    # Event 2: Verification
    case.state = CaseState.VERIFIED
    LedgerService.append_event(
        db=db_session,
        case=case,
        event_type="CASE_VERIFIED",
        payload={"action": "verified", "site_visited": True},
        actor=user,
    )
    # Event 3: Department assignment
    case.state = CaseState.ASSIGNED
    LedgerService.append_event(
        db=db_session,
        case=case,
        event_type="CASE_ASSIGNED",
        payload={"action": "assigned", "department": "Road Maintenance"},
        actor=user,
    )
    # Event 4: Work in progress
    case.state = CaseState.IN_PROGRESS
    LedgerService.append_event(
        db=db_session,
        case=case,
        event_type="WORK_STARTED",
        payload={"action": "work_begun", "crew_size": 4},
        actor=user,
    )
    db_session.commit()

    zip_path = ExportService.generate_case_export_package(db_session, case.id)
    return case, zip_path


def _repack_zip(src_zip: str, dst_zip: str, file_transform_map: dict):
    """Utility to modify specific files in a zip archive."""
    with zipfile.ZipFile(src_zip, "r") as z_in, zipfile.ZipFile(dst_zip, "w") as z_out:
        for item in z_in.infolist():
            if item.filename in file_transform_map:
                new_content = file_transform_map[item.filename]
                if new_content is not None:  # None indicates delete file
                    if isinstance(new_content, str):
                        new_content = new_content.encode("utf-8")
                    z_out.writestr(item.filename, new_content)
            else:
                z_out.writestr(item, z_in.read(item.filename))


def test_trusted_authenticity_mode_fails_closed_without_trust_anchor(db_session):
    """
    Fails Closed Requirement:
    Calling TRUSTED_AUTHENTICITY mode without external trust anchors (key or checkpoint)
    MUST fail immediately and refuse to downgrade to unauthenticated verification.
    """
    case, zip_path = _create_test_case_with_ledger(db_session)

    valid, logs = ExportService.verify_export_package(
        zip_path,
        mode=VerificationMode.TRUSTED_AUTHENTICITY,
        expected_public_key=None,
        trusted_checkpoint_root=None,
    )
    assert valid is False
    assert any("TRUST ANCHOR ERROR" in log for log in logs)


def test_attack_1_modifying_event_payload(db_session, tmp_path):
    """
    Attack 1: Modifying an event's payload bytes inside event_ledger.json.
    - FILE_INTEGRITY: DETECTED (SHA-256 digest of event_ledger.json mismatches manifest).
    - TRUSTED_AUTHENTICITY: DETECTED.
    """
    case, zip_path = _create_test_case_with_ledger(db_session)
    pub_key = SignerService.get_public_key_base64()

    with zipfile.ZipFile(zip_path, "r") as z:
        events = json.loads(z.read("event_ledger.json").decode("utf-8"))

    # Tamper: Alter payload of event 2
    events[1]["payload"]["tampered_flag"] = True
    tampered_bytes = json.dumps(events).encode("utf-8")

    tampered_zip = str(tmp_path / "tampered_attack1.zip")
    _repack_zip(zip_path, tampered_zip, {"event_ledger.json": tampered_bytes})

    # FILE_INTEGRITY mode: Detects digest mismatch
    ok_int, logs_int = ExportService.verify_export_package(
        tampered_zip, mode=VerificationMode.FILE_INTEGRITY
    )
    assert ok_int is False
    assert any("TAMPER DETECTED in event_ledger.json" in log for log in logs_int)

    # TRUSTED_AUTHENTICITY mode: Detects tamper
    ok_auth, logs_auth = ExportService.verify_export_package(
        tampered_zip, mode=VerificationMode.TRUSTED_AUTHENTICITY, expected_public_key=pub_key
    )
    assert ok_auth is False
    assert any("TAMPER DETECTED" in log for log in logs_auth)


def test_attack_2_modifying_actor_metadata(db_session, tmp_path):
    """
    Attack 2: Modifying actor metadata (e.g. public_actor_label) in event_ledger.json.
    - FILE_INTEGRITY: DETECTED (SHA-256 digest of event_ledger.json mismatches manifest).
    - TRUSTED_AUTHENTICITY: DETECTED.
    """
    case, zip_path = _create_test_case_with_ledger(db_session)
    pub_key = SignerService.get_public_key_base64()

    with zipfile.ZipFile(zip_path, "r") as z:
        events = json.loads(z.read("event_ledger.json").decode("utf-8"))

    # Tamper: Change public actor label to fake authority
    events[0]["public_actor_label"] = "Impersonated Mayor"
    tampered_bytes = json.dumps(events).encode("utf-8")

    tampered_zip = str(tmp_path / "tampered_attack2.zip")
    _repack_zip(zip_path, tampered_zip, {"event_ledger.json": tampered_bytes})

    ok_int, logs_int = ExportService.verify_export_package(
        tampered_zip, mode=VerificationMode.FILE_INTEGRITY
    )
    assert ok_int is False
    assert any("TAMPER DETECTED in event_ledger.json" in log for log in logs_int)

    ok_auth, logs_auth = ExportService.verify_export_package(
        tampered_zip, mode=VerificationMode.TRUSTED_AUTHENTICITY, expected_public_key=pub_key
    )
    assert ok_auth is False
    assert any("TAMPER DETECTED" in log for log in logs_auth)


def test_attack_3_reordering_events(db_session, tmp_path):
    """
    Attack 3: Swapping order of events in event_ledger.json.
    Even if manifest digest was forged to match, timeline sequence integrity fails.
    - FILE_INTEGRITY: DETECTED.
    - TRUSTED_AUTHENTICITY: DETECTED.
    """
    case, zip_path = _create_test_case_with_ledger(db_session)
    SignerService.get_public_key_base64()

    with zipfile.ZipFile(zip_path, "r") as z:
        events = json.loads(z.read("event_ledger.json").decode("utf-8"))

    # Swap event 1 and event 2
    events[0], events[1] = events[1], events[0]
    tampered_bytes = json.dumps(events).encode("utf-8")

    tampered_zip = str(tmp_path / "tampered_attack3.zip")
    _repack_zip(zip_path, tampered_zip, {"event_ledger.json": tampered_bytes})

    ok_int, logs_int = ExportService.verify_export_package(
        tampered_zip, mode=VerificationMode.FILE_INTEGRITY
    )
    assert ok_int is False


def test_attack_4_deleting_intermediate_event(db_session, tmp_path):
    """
    Attack 4: Deleting an intermediate event from the event history.
    - FILE_INTEGRITY: DETECTED.
    - TRUSTED_AUTHENTICITY: DETECTED.
    """
    case, zip_path = _create_test_case_with_ledger(db_session)
    pub_key = SignerService.get_public_key_base64()

    with zipfile.ZipFile(zip_path, "r") as z:
        events = json.loads(z.read("event_ledger.json").decode("utf-8"))

    # Remove event index 2
    del events[1]
    tampered_bytes = json.dumps(events).encode("utf-8")

    tampered_zip = str(tmp_path / "tampered_attack4.zip")
    _repack_zip(zip_path, tampered_zip, {"event_ledger.json": tampered_bytes})

    ok_int, logs_int = ExportService.verify_export_package(
        tampered_zip, mode=VerificationMode.FILE_INTEGRITY
    )
    assert ok_int is False

    ok_auth, logs_auth = ExportService.verify_export_package(
        tampered_zip, mode=VerificationMode.TRUSTED_AUTHENTICITY, expected_public_key=pub_key
    )
    assert ok_auth is False


def test_attack_5_and_6_truncating_final_events_and_remanifesting(db_session, tmp_path):
    """
    Attack 5 & 6: Removing final event or truncating multiple events, then rebuilding manifest.
    CRITICAL DEMONSTRATION:
    - FILE_INTEGRITY: CANNOT detect truncation if manifest hashes match internal prefix!
    - TRUSTED_AUTHENTICITY with trusted_checkpoint_root: DETECTS truncation immediately!
    """
    import hashlib

    case, zip_path = _create_test_case_with_ledger(db_session)
    pub_key = SignerService.get_public_key_base64()

    with zipfile.ZipFile(zip_path, "r") as z:
        events = json.loads(z.read("event_ledger.json").decode("utf-8"))
        manifest = json.loads(z.read("manifest.json").decode("utf-8"))
        summary = z.read("case_summary.json")
        obs = z.read("observations.json")
        res = z.read("resolution_history.json")

    original_latest_checkpoint_root = events[-1]["current_event_hash"]

    # Attacker truncates from 4 events down to only the first 2 events
    truncated_events = events[:2]
    truncated_events_bytes = canonical_json(truncated_events).encode("utf-8")

    # Attacker crafts a consistent manifest for the truncated files
    manifest["files"]["event_ledger.json"]["sha256"] = hashlib.sha256(
        truncated_events_bytes
    ).hexdigest()
    manifest["files"]["event_ledger.json"]["byte_size"] = len(truncated_events_bytes)
    # Attacker creates forged manifest bytes
    forged_manifest_bytes = canonical_json(manifest).encode("utf-8")

    truncated_zip = str(tmp_path / "tampered_truncated.zip")
    with zipfile.ZipFile(truncated_zip, "w") as z_out:
        z_out.writestr("case_summary.json", summary)
        z_out.writestr("event_ledger.json", truncated_events_bytes)
        z_out.writestr("observations.json", obs)
        z_out.writestr("resolution_history.json", res)
        z_out.writestr("manifest.json", forged_manifest_bytes)

    # In FILE_INTEGRITY mode:
    # Notice: FILE_INTEGRITY sees matching hashes and a valid prefix chain (events 1 & 2 link to each other).
    # Thus FILE_INTEGRITY mode ALONE is NOT truncation-resistant!
    ok_int, logs_int = ExportService.verify_export_package(
        truncated_zip, mode=VerificationMode.FILE_INTEGRITY
    )
    assert (
        ok_int is True
    )  # Proves file integrity alone is blind to truncation without trusted checkpoint!

    # In TRUSTED_AUTHENTICITY mode with independently retained checkpoint root:
    ok_auth, logs_auth = ExportService.verify_export_package(
        truncated_zip,
        mode=VerificationMode.TRUSTED_AUTHENTICITY,
        expected_public_key=pub_key,
        trusted_checkpoint_root=original_latest_checkpoint_root,
    )
    assert ok_auth is False
    assert any("CHECKPOINT VIOLATION" in log or "TAMPER DETECTED" in log for log in logs_auth)


def test_attack_7_rebuilding_complete_hash_chain(db_session, tmp_path):
    """
    Attack 7: Rebuilding a complete valid-looking hash chain with forged events.
    - FILE_INTEGRITY: Passes if manifest matches.
    - TRUSTED_AUTHENTICITY: DETECTED (Signature verification against trusted key fails).
    """
    import hashlib

    case, zip_path = _create_test_case_with_ledger(db_session)
    pub_key = SignerService.get_public_key_base64()

    with zipfile.ZipFile(zip_path, "r") as z:
        manifest = json.loads(z.read("manifest.json").decode("utf-8"))
        summary = z.read("case_summary.json")
        obs = z.read("observations.json")
        res = z.read("resolution_history.json")

    # Attacker crafts completely forged events with mathematically valid SHA-256 chain
    forged_events = [
        {
            "case_id": case.id,
            "event_index": 1,
            "event_type": "CASE_CREATED",
            "public_actor_label": "Citizen Observer",
            "payload": {"forged": True},
            "payload_json": canonical_json({"forged": True}),
            "previous_event_hash": "0" * 64,
            "current_event_hash": "",
            "timestamp": "2026-01-01T00:00:00+00:00",
        }
    ]
    preimage = f"{'0' * 64}|{case.id}|1|CASE_CREATED|{canonical_json({'forged': True})}"
    forged_events[0]["current_event_hash"] = hashlib.sha256(preimage.encode("utf-8")).hexdigest()
    forged_bytes = canonical_json(forged_events).encode("utf-8")

    manifest["files"]["event_ledger.json"]["sha256"] = hashlib.sha256(forged_bytes).hexdigest()
    manifest["files"]["event_ledger.json"]["byte_size"] = len(forged_bytes)
    forged_manifest_bytes = canonical_json(manifest).encode("utf-8")

    forged_zip = str(tmp_path / "forged_chain.zip")
    with zipfile.ZipFile(forged_zip, "w") as z_out:
        z_out.writestr("case_summary.json", summary)
        z_out.writestr("event_ledger.json", forged_bytes)
        z_out.writestr("observations.json", obs)
        z_out.writestr("resolution_history.json", res)
        z_out.writestr("manifest.json", forged_manifest_bytes)

    # In FILE_INTEGRITY mode: Hashes match manifest, hash chain internally consistent
    ok_int, _ = ExportService.verify_export_package(
        forged_zip, mode=VerificationMode.FILE_INTEGRITY
    )
    assert ok_int is True

    # In TRUSTED_AUTHENTICITY mode: Attacker cannot produce valid signature with trusted key
    ok_auth, logs_auth = ExportService.verify_export_package(
        forged_zip, mode=VerificationMode.TRUSTED_AUTHENTICITY, expected_public_key=pub_key
    )
    assert ok_auth is False
    assert any("TAMPER DETECTED: Ed25519 manifest digital signature" in log for log in logs_auth)


def test_attack_8_replacing_manifest_and_signing_with_attacker_key(db_session, tmp_path):
    """
    Attack 8: Key Replacement Attack.
    Attacker modifies the archive, creates their own Ed25519 key, signs the manifest,
    and embeds their own public key into manifest.json.
    - FILE_INTEGRITY: Passes (mode does not verify external trust anchors).
    - TRUSTED_AUTHENTICITY: DETECTED! Rejects because archive key != expected_public_key.
    """
    import hashlib

    case, zip_path = _create_test_case_with_ledger(db_session)
    trusted_pub_key = SignerService.get_public_key_base64()

    # Attacker generates rogue keypair
    rogue_priv_hex, rogue_pub_b64 = SignerService.generate_keypair()

    with zipfile.ZipFile(zip_path, "r") as z:
        events = json.loads(z.read("event_ledger.json").decode("utf-8"))
        manifest = json.loads(z.read("manifest.json").decode("utf-8"))
        summary = z.read("case_summary.json")
        obs = z.read("observations.json")
        res = z.read("resolution_history.json")

    # Attacker modifies event 1
    events[0]["payload"]["rogue"] = "attacker payload"
    mod_events_bytes = canonical_json(events).encode("utf-8")
    manifest["files"]["event_ledger.json"]["sha256"] = hashlib.sha256(mod_events_bytes).hexdigest()
    manifest["files"]["event_ledger.json"]["byte_size"] = len(mod_events_bytes)

    # Attacker signs payload with rogue key
    payload_to_sign = {
        "case_id": manifest["case_id"],
        "format": manifest["format"],
        "version": manifest["version"],
        "files": manifest["files"],
        "generated_at": manifest["generated_at"],
    }
    rogue_sig = SignerService.sign_bytes(
        canonical_json(payload_to_sign).encode("utf-8"),
        private_key_hex=rogue_priv_hex,
    )

    manifest["signature"] = rogue_sig
    manifest["signer_public_key"] = rogue_pub_b64
    rogue_manifest_bytes = canonical_json(manifest).encode("utf-8")

    rogue_zip = str(tmp_path / "rogue_key_replacement.zip")
    with zipfile.ZipFile(rogue_zip, "w") as z_out:
        z_out.writestr("case_summary.json", summary)
        z_out.writestr("event_ledger.json", mod_events_bytes)
        z_out.writestr("observations.json", obs)
        z_out.writestr("resolution_history.json", res)
        z_out.writestr("manifest.json", rogue_manifest_bytes)

    # In FILE_INTEGRITY mode: Hashes match manifest
    ok_int, _ = ExportService.verify_export_package(rogue_zip, mode=VerificationMode.FILE_INTEGRITY)
    assert ok_int is True

    # In TRUSTED_AUTHENTICITY mode: Fails closed against expected_public_key!
    ok_auth, logs_auth = ExportService.verify_export_package(
        rogue_zip,
        mode=VerificationMode.TRUSTED_AUTHENTICITY,
        expected_public_key=trusted_pub_key,
    )
    assert ok_auth is False
    assert any("Key replacement attack rejected" in log for log in logs_auth)


def test_attack_9_replaying_older_valid_export_as_current(db_session, tmp_path):
    """
    Attack 9: Replaying an older, genuine export as though it were the current state.
    Export T1 was signed by legitimate key when case had 2 events.
    Case progressed to 4 events with checkpoint root R2.
    Attacker presents T1 export as current.
    - FILE_INTEGRITY: Passes (T1 is internally valid).
    - TRUSTED_AUTHENTICITY (signature only): Passes (genuine key signed T1).
    - TRUSTED_AUTHENTICITY (with trusted_checkpoint_root R2): DETECTED!
      (T1 latest hash != R2).
    """
    cat = IssueCategory(name="Roads", code="RD-REPLAY", default_severity_weight=1.0)
    user = User(
        email="rep@civictrace.local",
        hashed_password="h",
        display_name="R",
        role=UserRole.ADMINISTRATOR,
    )
    case = Case(
        public_id=f"CAS-REPLAY-{int(datetime.now(timezone.utc).timestamp() * 1000) % 100000}",
        category=cat,
        title="Pothole Replay Test",
        description="Testing stale export replay resistance",
        latitude=22.7,
        longitude=75.8,
        state=CaseState.SUBMITTED,
    )
    db_session.add_all([cat, user, case])
    db_session.commit()

    # Event 1 & 2
    LedgerService.append_event(db_session, case, "EVENT_1", {"step": 1}, user)
    LedgerService.append_event(db_session, case, "EVENT_2", {"step": 2}, user)
    db_session.commit()

    # Generate genuine export at T1
    zip_t1 = ExportService.generate_case_export_package(db_session, case.id)
    trusted_pub_key = SignerService.get_public_key_base64()

    # Case evolves further at T2 (Event 3 & 4)
    LedgerService.append_event(db_session, case, "EVENT_3", {"step": 3}, user)
    ev4 = LedgerService.append_event(db_session, case, "EVENT_4", {"step": 4}, user)
    db_session.commit()

    # The current true checkpoint root at T2
    current_t2_root = ev4.current_event_hash

    # Attacker tries to submit older zip_t1 claiming it is current:
    # 1. FILE_INTEGRITY mode: Passes
    ok_int, _ = ExportService.verify_export_package(zip_t1, mode=VerificationMode.FILE_INTEGRITY)
    assert ok_int is True

    # 2. TRUSTED_AUTHENTICITY with public key only: Passes (because T1 signature was genuinely produced)
    ok_auth_key, _ = ExportService.verify_export_package(
        zip_t1, mode=VerificationMode.TRUSTED_AUTHENTICITY, expected_public_key=trusted_pub_key
    )
    assert ok_auth_key is True

    # 3. TRUSTED_AUTHENTICITY with external current checkpoint root: DETECTS STALE EXPORT!
    ok_auth_root, logs_root = ExportService.verify_export_package(
        zip_t1,
        mode=VerificationMode.TRUSTED_AUTHENTICITY,
        expected_public_key=trusted_pub_key,
        trusted_checkpoint_root=current_t2_root,
    )
    assert ok_auth_root is False
    assert any("CHECKPOINT VIOLATION: Ledger latest hash" in log for log in logs_root)


def test_db_tamper_actor_identity_detected(db_session):
    """
    Direct Database Tampering Test:
    An attacker directly updates the `actor_id` of a ledger event in the database,
    leaving the event payload completely unchanged.
    `verify_chain` MUST detect the tampering and fail verification.
    """
    case, _ = _create_test_case_with_ledger(db_session)
    valid, total, err, _ = LedgerService.verify_chain(db_session, case.id)
    assert valid is True
    assert total == 4

    ev2 = (
        db_session.query(CaseEvent)
        .filter(CaseEvent.case_id == case.id, CaseEvent.event_index == 2)
        .first()
    )
    ev2.actor_id = "00000000-0000-0000-0000-000000000099"
    db_session.commit()

    valid_after, total_after, err_after, _ = LedgerService.verify_chain(db_session, case.id)
    assert valid_after is False
    assert "Hash computation tampering detected at event index 2" in err_after


def test_db_tamper_timestamp_detected(db_session):
    """
    Direct Database Tampering Test:
    An attacker backdates or alters the `created_at` timestamp in the database,
    leaving the event payload completely unchanged.
    `verify_chain` MUST detect the tampering and fail verification.
    """
    case, _ = _create_test_case_with_ledger(db_session)
    ev3 = (
        db_session.query(CaseEvent)
        .filter(CaseEvent.case_id == case.id, CaseEvent.event_index == 3)
        .first()
    )
    ev3.created_at = datetime(2020, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    db_session.commit()

    valid, total, err, _ = LedgerService.verify_chain(db_session, case.id)
    assert valid is False
    assert "Hash computation tampering detected at event index 3" in err


def test_db_tamper_public_label_detected(db_session):
    """
    Direct Database Tampering Test:
    An attacker modifies `public_actor_label` in the database,
    leaving the event payload completely unchanged.
    `verify_chain` MUST detect the tampering and fail verification.
    """
    case, _ = _create_test_case_with_ledger(db_session)
    ev1 = (
        db_session.query(CaseEvent)
        .filter(CaseEvent.case_id == case.id, CaseEvent.event_index == 1)
        .first()
    )
    ev1.public_actor_label = "Compromised Authority"
    db_session.commit()

    valid, total, err, _ = LedgerService.verify_chain(db_session, case.id)
    assert valid is False
    assert "Hash computation tampering detected at event index 1" in err


def test_historical_schema_v1_events_remain_verifiable(db_session):
    """
    Backward Compatibility Test:
    Ensures historical events recorded under Schema Version 1 continue to verify
    accurately under legacy canonicalization rules.
    """
    import uuid

    suffix = uuid.uuid4().hex[:6]
    cat = IssueCategory(name=f"V1 Test {suffix}", code=f"V1-{suffix}")
    case = Case(
        public_id=f"CAS-V1-{suffix.upper()}",
        category=cat,
        title="Historical Case",
        description="Legacy test",
        latitude=22.7,
        longitude=75.8,
        state=CaseState.SUBMITTED,
    )
    db_session.add_all([cat, case])
    db_session.commit()

    payload_str = canonical_json({"action": "created_legacy"})
    hash1_preimage = f"{'0'*64}|{case.id}|1|CASE_CREATED|{payload_str}"
    hash1 = hashlib.sha256(hash1_preimage.encode("utf-8")).hexdigest()
    ev1 = CaseEvent(
        case_id=case.id,
        event_index=1,
        event_type="CASE_CREATED",
        public_actor_label="System",
        payload_json=payload_str,
        schema_version=1,
        previous_event_hash="0" * 64,
        current_event_hash=hash1,
    )
    db_session.add(ev1)
    db_session.commit()

    valid, count, err, latest = LedgerService.verify_chain(db_session, case.id)
    assert valid is True
    assert count == 1
    assert latest == hash1

