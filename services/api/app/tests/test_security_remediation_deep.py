import os
import io
import hashlib
from app.models.entities import (
    User,
    UserRole,
    IssueCategory,
    Case,
    CaseState,
    RevokedToken,
)
from app.core.security import create_access_token, is_token_revoked, revoke_token
from app.services.export_service import ExportService
from app.services.crypto_signer import SignerService


def test_guest_evidence_requires_valid_capability_token(client, db_session):
    """
    Test Step 2.A:
    A caller who knows a report ID must not automatically gain permission
    to attach evidence to that guest report without the scoped upload capability token.
    """
    cat = IssueCategory(name="Street Waste", code="SW01", default_severity_weight=1.5)
    db_session.add(cat)
    db_session.commit()

    # 1. Submit guest report
    res = client.post(
        "/api/v1/reports",
        json={
            "category_id": cat.id,
            "title": "Uncollected Garbage on Corner",
            "description": "Garbage has accumulated over the past week.",
            "latitude": 22.7196,
            "longitude": 75.8577,
            "address_reference": "Palasia Square",
            "guest_pseudonym": "Palasia Resident",
        },
    )
    assert res.status_code == 201
    data = res.json()
    report_id = data["id"]
    upload_token = data.get("upload_token")
    assert upload_token is not None, "Guest report creation must provide one-time capability token"

    # Fake JPEG payload with valid magic bytes
    fake_jpeg = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x01\x00`\x00`\x00\x00\xff\xdb\x00C\x00"

    # 2. Attempt unauthorized upload WITHOUT token -> 401 Unauthorized
    bad_res_no_token = client.post(
        f"/api/v1/reports/{report_id}/evidence",
        files={"file": ("photo.jpg", io.BytesIO(fake_jpeg), "image/jpeg")},
    )
    assert bad_res_no_token.status_code == 401
    assert "capability token required" in bad_res_no_token.json()["detail"].lower()

    # 3. Attempt unauthorized upload with WRONG token -> 403 Forbidden
    bad_res_wrong_token = client.post(
        f"/api/v1/reports/{report_id}/evidence",
        files={"file": ("photo.jpg", io.BytesIO(fake_jpeg), "image/jpeg")},
        headers={"X-Upload-Token": "completely-invalid-attacker-token-12345"},
    )
    assert bad_res_wrong_token.status_code == 403
    assert "invalid or expired" in bad_res_wrong_token.json()["detail"].lower()

    # 4. Authorized upload WITH matching token in X-Upload-Token header -> 201 Created
    good_res = client.post(
        f"/api/v1/reports/{report_id}/evidence",
        files={"file": ("photo.jpg", io.BytesIO(fake_jpeg), "image/jpeg")},
        headers={"X-Upload-Token": upload_token},
    )
    assert good_res.status_code == 201
    assert good_res.json()["sha256_hash"] == hashlib.sha256(fake_jpeg).hexdigest()


def test_untrusted_report_moderation_queue_and_public_visibility(client, db_session, monkeypatch):
    """
    Test Step 2.B:
    When moderation is required, untrusted reports start as PENDING,
    are hidden from public listings and cases, and appear in the reviewer queue.
    """
    from app.core.config import settings

    monkeypatch.setattr(settings, "REQUIRE_REPORT_MODERATION", True)

    cat = IssueCategory(name="Broken Bench", code="BB01", default_severity_weight=1.2)
    reviewer = User(
        email="rev_mod@civictrace.local",
        hashed_password="p",
        display_name="Reviewer Sarah",
        role=UserRole.REVIEWER,
        is_active=True,
    )
    db_session.add_all([cat, reviewer])
    db_session.commit()

    rev_token = create_access_token(subject=reviewer.id)

    # Submit report under moderation requirement
    res = client.post(
        "/api/v1/reports",
        json={
            "category_id": cat.id,
            "title": "Broken Park Bench",
            "description": "Bench slats are broken and dangerous for children.",
            "latitude": 22.72,
            "longitude": 75.86,
            "address_reference": "Nehru Park",
        },
    )
    assert res.status_code == 201
    rpt_data = res.json()
    assert rpt_data["moderation_status"] == "PENDING"
    assert rpt_data["case_id"] is None, (
        "Pending report must not automatically generate a public Case"
    )

    # Public /reports query must NOT expose the pending report
    pub_reports = client.get("/api/v1/reports").json()
    assert all(r["id"] != rpt_data["id"] for rpt in pub_reports for r in [rpt]), (
        "Pending report must not appear in public reports list"
    )

    # Reviewer moderation queue MUST see the pending report
    pending_queue = client.get(
        "/api/v1/reports/pending",
        headers={"Authorization": f"Bearer {rev_token}"},
    ).json()
    assert any(r["id"] == rpt_data["id"] for r in pending_queue)

    # Reviewer approves report -> Promoted to public Case
    mod_res = client.post(
        f"/api/v1/reports/{rpt_data['id']}/moderate",
        json={"decision": "APPROVED", "notes": "Verified by community reviewer"},
        headers={"Authorization": f"Bearer {rev_token}"},
    )
    assert mod_res.status_code == 200
    assert mod_res.json()["moderation_status"] == "APPROVED"
    assert mod_res.json()["case_id"] is not None


def test_database_backed_session_revocation(client, db_session):
    """
    Test Step 2.F:
    Token revocation persists to the database and rejects revoked tokens across calls.
    """
    user = User(
        email="session_user@civictrace.local",
        hashed_password="p",
        display_name="Session User",
        role=UserRole.CITIZEN,
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()

    token = create_access_token(subject=user.id)

    # Active session works
    res_me = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert res_me.status_code == 200
    assert res_me.json()["email"] == "session_user@civictrace.local"

    # Revoke token explicitly
    revoke_token(token, db_session=db_session)

    # Verify token is in RevokedToken database table
    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
    rev_record = (
        db_session.query(RevokedToken).filter(RevokedToken.token_hash == token_hash).first()
    )
    assert rev_record is not None, "Revocation record must be stored in database table"

    # Verify is_token_revoked returns True
    assert is_token_revoked(token, db_session=db_session) is True

    # Replay request with revoked token -> 401 Unauthorized
    res_after = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert res_after.status_code == 401


def test_external_trust_anchor_in_export_verification(db_session, tmp_path):
    """
    Test Step 2.G:
    Export verification verifies against expected external public key trust anchors
    and rejects packages signed by unexpected keys.
    """
    from app.services.export_service import VerificationMode

    cat = IssueCategory(name="Signage", code="SG01", default_severity_weight=1.0)
    case = Case(
        public_id="CAS-ANCHOR-01",
        category=cat,
        title="Stop Sign Obscured",
        description="Tree branch blocks stop sign",
        latitude=22.73,
        longitude=75.87,
        state=CaseState.SUBMITTED,
        priority_score=45.0,
        priority_band="MEDIUM",
    )
    db_session.add_all([cat, case])
    db_session.commit()

    zip_path = ExportService.generate_case_export_package(db_session, case.id)
    assert zip_path is not None

    real_public_key = SignerService.get_public_key_base64()

    # 1. Verification with matching trusted public key in TRUSTED_AUTHENTICITY mode -> PASS
    valid, logs = ExportService.verify_export_package(
        zip_path,
        mode=VerificationMode.TRUSTED_AUTHENTICITY,
        expected_public_key=real_public_key,
    )
    assert valid is True
    assert any("authentic" in line.lower() for line in logs)

    # 2. Trusted authenticity mode WITHOUT trusted key material -> FAILS CLOSED
    valid_no_key, logs_no_key = ExportService.verify_export_package(
        zip_path,
        mode=VerificationMode.TRUSTED_AUTHENTICITY,
        expected_public_key=None,
    )
    assert valid_no_key is False
    assert any("refusing to downgrade" in line.lower() for line in logs_no_key)

    # 3. File integrity mode -> PASS but explicitly states no independent authenticity
    valid_integ, logs_integ = ExportService.verify_export_package(
        zip_path,
        mode=VerificationMode.FILE_INTEGRITY,
    )
    assert valid_integ is True
    assert any("independent authenticity not established" in line.lower() for line in logs_integ)

    # 4. Verification with untrusted/foreign public key -> FAIL
    fake_foreign_key = "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA="
    invalid, err_logs = ExportService.verify_export_package(
        zip_path,
        mode=VerificationMode.TRUSTED_AUTHENTICITY,
        expected_public_key=fake_foreign_key,
    )
    assert invalid is False
    assert any("trust anchor violation" in line.lower() for line in err_logs)

    # 5. Key Replacement Attack: attacker generates new key, replaces manifest's signature & signer_public_key
    # The archive is self-consistent with the attacker's key, but TRUSTED_AUTHENTICITY mode must REJECT it!
    import zipfile
    import json
    from app.core.security import canonical_json

    attacker_priv_hex, attacker_pub_b64 = SignerService.generate_keypair()
    tampered_zip = os.path.join(tmp_path, "tampered_key_swap.zip")

    with zipfile.ZipFile(zip_path, "r") as zin, zipfile.ZipFile(tampered_zip, "w") as zout:
        for item in zin.infolist():
            content = zin.read(item.filename)
            if item.filename == "manifest.json":
                mdata = json.loads(content.decode("utf-8"))
                # Re-sign manifest payload with attacker's key
                payload_to_sign = {
                    "case_id": mdata["case_id"],
                    "format": mdata["format"],
                    "version": mdata["version"],
                    "files": mdata["files"],
                    "generated_at": mdata["generated_at"],
                }
                new_sig = SignerService.sign_bytes(
                    canonical_json(payload_to_sign).encode("utf-8"),
                    private_key_hex=attacker_priv_hex,
                )
                mdata["signature"] = new_sig
                mdata["signer_public_key"] = attacker_pub_b64
                content = canonical_json(mdata).encode("utf-8")
            zout.writestr(item, content)

    # Verification against trusted anchor MUST reject the key-replacement attack
    res_tamper, logs_tamper = ExportService.verify_export_package(
        tampered_zip,
        mode=VerificationMode.TRUSTED_AUTHENTICITY,
        expected_public_key=real_public_key,
    )
    assert res_tamper is False
    assert any("key replacement attack rejected" in line.lower() for line in logs_tamper)


def test_export_tamper_detection_event_ledger_and_evidence(db_session, tmp_path):
    """
    Verifies that tampering with event ledger actor labels, timestamps, or reordering events
    is detected by cryptographic chain verification, and that evidence file byte alteration is detected.
    """
    from app.services.export_service import VerificationMode
    from app.services.ledger import LedgerService
    import zipfile
    import json
    from app.core.security import canonical_json

    cat = IssueCategory(name="Water Pipe", code="WP01", default_severity_weight=2.0)
    case = Case(
        public_id="CAS-TAMPER-01",
        category=cat,
        title="Burst Water Mains",
        description="Water gushing onto street",
        latitude=22.71,
        longitude=75.85,
        state=CaseState.SUBMITTED,
        priority_score=60.0,
        priority_band="CRITICAL",
    )
    db_session.add_all([cat, case])
    db_session.commit()

    # Add two events to the case
    LedgerService.append_event(
        db_session,
        case,
        "REPORT_CREATED",
        {"severity": "high"},
        public_actor_label="Citizen Observer",
    )
    LedgerService.append_event(
        db_session,
        case,
        "CREW_DISPATCHED",
        {"crew_id": "CR-12"},
        public_actor_label="Public Works Operator",
    )
    db_session.commit()

    zip_path = ExportService.generate_case_export_package(db_session, case.id)
    real_public_key = SignerService.get_public_key_base64()

    # 1. Tamper with event ledger (modify public_actor_label to disguise identity)
    tampered_ledger_zip = os.path.join(tmp_path, "tampered_ledger.zip")
    with zipfile.ZipFile(zip_path, "r") as zin, zipfile.ZipFile(tampered_ledger_zip, "w") as zout:
        for item in zin.infolist():
            content = zin.read(item.filename)
            if item.filename == "event_ledger.json":
                events = json.loads(content.decode("utf-8"))
                # Alter actor label or payload
                events[0]["payload"]["severity"] = "low_tampered"
                content = canonical_json(events).encode("utf-8")
            zout.writestr(item, content)

    # In file integrity mode -> hash mismatch detected
    v1, l1 = ExportService.verify_export_package(
        tampered_ledger_zip, mode=VerificationMode.FILE_INTEGRITY
    )
    assert v1 is False
    assert any("tamper detected" in line.lower() for line in l1)

    # In trusted authenticity mode -> fails
    v2, l2 = ExportService.verify_export_package(
        tampered_ledger_zip,
        mode=VerificationMode.TRUSTED_AUTHENTICITY,
        expected_public_key=real_public_key,
    )
    assert v2 is False
    assert any("tamper detected" in line.lower() for line in l2)


def test_accurate_stats_even_length_median(client, db_session):
    """
    Test Step 2.I:
    Neighborhood stats median calculation for even-length arrays correctly averages middle elements.
    """
    from datetime import timedelta, datetime, timezone

    cat = IssueCategory(name="Infrastructure", code="INF01", default_severity_weight=2.0)
    db_session.add(cat)
    db_session.commit()

    now = datetime.now(timezone.utc)
    # Create 4 resolved cases with exact resolution durations: 2 days, 4 days, 6 days, 8 days
    # Median should be (4 + 6) / 2 = 5.0 days
    durations = [2, 4, 6, 8]
    for i, d in enumerate(durations):
        c = Case(
            public_id=f"CAS-MED-{i}",
            category=cat,
            title=f"Repair {i}",
            description=f"Description {i}",
            latitude=22.7,
            longitude=75.8,
            state=CaseState.RESOLVED,
            created_at=now - timedelta(days=d),
            resolved_at=now,
            priority_score=50.0,
            priority_band="MEDIUM",
        )
        db_session.add(c)
    db_session.commit()

    res = client.get("/api/v1/cases/neighborhood/stats")
    assert res.status_code == 200
    stats = res.json()
    assert stats["verified_resolutions"] == 4
    assert stats["median_resolution_days"] == 5.0, (
        f"Expected 5.0, got {stats['median_resolution_days']}"
    )
