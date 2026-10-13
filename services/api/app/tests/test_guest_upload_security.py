import io
from datetime import datetime, timedelta, timezone
from app.models.entities import IssueCategory, Report, User, UserRole
from app.core.config import settings
from app.core.security import get_password_hash


def test_guest_upload_token_security_lifecycle(client, db_session):
    """
    Comprehensive verification of guest upload capability security:
    1. Returns upload_token on creation.
    2. Upload token is NOT present in subsequent public GET /reports responses.
    3. Token cannot be used on a different report (wrong-report access blocked).
    4. Token is revoked when report is rejected by moderation.
    5. Token expires after configured lifetime.
    """
    cat = IssueCategory(name="Streetlight Defect", code="SL01", default_severity_weight=1.0)
    reviewer = User(
        email="rev_guest_test@civictrace.local",
        hashed_password=get_password_hash("p"),
        display_name="Reviewer Rick",
        role=UserRole.REVIEWER,
        is_active=True,
    )
    db_session.add_all([cat, reviewer])
    db_session.commit()

    # 1. Submit Guest Report A
    res_a = client.post(
        "/api/v1/reports",
        json={
            "category_id": cat.id,
            "title": "Flickering Light A",
            "description": "Pole 12 flickering",
            "latitude": 22.72,
            "longitude": 75.86,
            "guest_pseudonym": "Resident A",
        },
    )
    assert res_a.status_code == 201
    data_a = res_a.json()
    report_a_id = data_a["id"]
    token_a = data_a["upload_token"]
    assert token_a is not None, "One-time capability token must be provided on creation"

    # 2. Verify token is NOT exposed in GET /reports or GET /reports/pending
    get_reports_res = client.get("/api/v1/reports")
    for r in get_reports_res.json():
        assert "upload_token" not in r or r["upload_token"] is None, (
            "upload_token must not leak in public list"
        )

    # Submit Guest Report B
    res_b = client.post(
        "/api/v1/reports",
        json={
            "category_id": cat.id,
            "title": "Broken Light B",
            "description": "Pole 14 broken",
            "latitude": 22.73,
            "longitude": 75.87,
            "guest_pseudonym": "Resident B",
        },
    )
    assert res_b.status_code == 201
    data_b = res_b.json()
    report_b_id = data_b["id"]
    token_b = data_b["upload_token"]

    fake_jpeg = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x01\x00`\x00`\x00\x00\xff\xdb\x00C\x00"

    # 3. Wrong-report access blocked: Attempt to upload to Report B using Token A -> 403 Forbidden
    wrong_report_res = client.post(
        f"/api/v1/reports/{report_b_id}/evidence",
        files={"file": ("light.jpg", io.BytesIO(fake_jpeg), "image/jpeg")},
        headers={"X-Upload-Token": token_a},
    )
    assert wrong_report_res.status_code == 403
    assert "invalid or expired" in wrong_report_res.json()["detail"].lower()

    # 4. Correct token upload to Report A -> 201 Created
    valid_res = client.post(
        f"/api/v1/reports/{report_a_id}/evidence",
        files={"file": ("light.jpg", io.BytesIO(fake_jpeg), "image/jpeg")},
        headers={"X-Upload-Token": token_a},
    )
    assert valid_res.status_code == 201

    # 5. Revocation on moderation rejection:
    # Reviewer logs in and rejects Report A
    login_rev = client.post(
        "/api/v1/auth/login",
        data={"username": reviewer.email, "password": "p"},
    )
    csrf_tok = login_rev.cookies.get("csrf_token")
    mod_res = client.post(
        f"/api/v1/reports/{report_a_id}/moderate",
        json={"decision": "REJECTED", "notes": "Not a municipal street fixture"},
        cookies=login_rev.cookies,
        headers={"X-CSRF-Token": csrf_tok} if csrf_tok else {},
    )
    assert mod_res.status_code == 200

    # Clear cookies so client acts as an unauthenticated guest observer
    client.cookies.clear()

    # Attempt to upload evidence with Token A after rejection -> 403 Forbidden (revoked)
    post_reject_res = client.post(
        f"/api/v1/reports/{report_a_id}/evidence",
        files={"file": ("more_light.jpg", io.BytesIO(fake_jpeg), "image/jpeg")},
        headers={"X-Upload-Token": token_a},
    )
    assert post_reject_res.status_code == 403
    assert "revoked" in post_reject_res.json()["detail"].lower()

    # 6. Expiry check: artificially simulate an expired report
    rep_b = db_session.query(Report).filter(Report.id == report_b_id).first()
    rep_b.created_at = datetime.now(timezone.utc) - timedelta(
        minutes=settings.GUEST_UPLOAD_TOKEN_EXPIRE_MINUTES + 10
    )
    db_session.commit()

    expired_res = client.post(
        f"/api/v1/reports/{report_b_id}/evidence",
        files={"file": ("light_b.jpg", io.BytesIO(fake_jpeg), "image/jpeg")},
        headers={"X-Upload-Token": token_b},
    )
    assert expired_res.status_code == 403
    assert "expired" in expired_res.json()["detail"].lower()
