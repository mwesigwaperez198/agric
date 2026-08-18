def test_register_and_login(client):
    r = client.post(
        "/api/v1/auth/register",
        json={
            "email": "new@user.ug",
            "full_name": "New User",
            "password": "Secure!Pass1",
            "role": "consumer",
        },
    )
    assert r.status_code == 201
    body = r.json()
    assert "access_token" in body and "refresh_token" in body

    r = client.post(
        "/api/v1/auth/login",
        json={"email": "new@user.ug", "password": "Secure!Pass1"},
    )
    assert r.status_code == 200
    assert r.json()["totp_required"] is False


def test_login_bad_password(client):
    client.post(
        "/api/v1/auth/register",
        json={"email": "a@b.ug", "full_name": "A", "password": "Secure!Pass1"},
    )
    r = client.post("/api/v1/auth/login", json={"email": "a@b.ug", "password": "wrong"})
    assert r.status_code == 401


def test_me_requires_token(client):
    assert client.get("/api/v1/auth/me").status_code == 401


def test_totp_setup_and_enable(client, auth_headers):
    r = client.post("/api/v1/auth/totp/setup", headers=auth_headers)
    assert r.status_code == 200
    secret = r.json()["secret"]
    assert len(secret) == 32

    import pyotp

    code = pyotp.TOTP(secret).now()
    r = client.post("/api/v1/auth/totp/enable", json={"code": code}, headers=auth_headers)
    assert r.status_code == 200
    assert r.json()["totp_enabled"] is True

    r = client.post("/api/v1/auth/login", json={"email": "farmer@test.ug", "password": "Strong!Pass1"})
    assert r.status_code == 200
    assert r.json()["totp_required"] is True

    r = client.post(
        "/api/v1/auth/totp/login",
        json={"email": "farmer@test.ug", "password": "Strong!Pass1", "code": code},
    )
    assert r.status_code == 200
    assert "access_token" in r.json()


# ---------------------------------------------------------------------------
# OTP 2FA tests
# ---------------------------------------------------------------------------


def _get_latest_otp_code(db, user_id: int) -> str:
    """Extract the plain OTP code from the latest OtpCode row for a user.

    In tests the OTP service stores a _plain_code attribute on the ORM object
    before committing.  Because the commit flushes to the DB, we re-query the
    latest row and retrieve the code from the in-memory object cache.
    """
    from api.app.models.otp import OtpCode

    otp = db.query(OtpCode).filter(OtpCode.user_id == user_id).order_by(OtpCode.id.desc()).first()
    assert otp is not None, "No OTP code found in database"
    return otp._plain_code  # type: ignore[attr-defined]


def test_otp_send_and_verify(client, auth_headers):
    """Send an OTP via the /otp/send endpoint and verify it with /otp/verify."""
    from api.app.database import SessionLocal
    from api.app.models import User

    r = client.post("/api/v1/auth/otp/send", json={"delivery": "email"}, headers=auth_headers)
    assert r.status_code == 200
    body = r.json()
    assert body["delivery"] == "email"
    assert "****" in body["target"]

    db = SessionLocal()
    user = db.query(User).filter(User.email == "farmer@test.ug").first()
    code = _get_latest_otp_code(db, user.id)
    assert len(code) == 6
    db.close()

    r = client.post(
        "/api/v1/auth/otp/verify",
        json={"email": "farmer@test.ug", "password": "Strong!Pass1", "code": code},
    )
    assert r.status_code == 200
    assert "access_token" in r.json()
    assert "refresh_token" in r.json()


def test_otp_login_flow(client, auth_headers):
    """Enable OTP 2FA, then login should require OTP second factor."""
    from api.app.database import SessionLocal
    from api.app.models import User

    # Send + setup OTP 2FA
    r = client.post("/api/v1/auth/otp/send", json={"delivery": "email"}, headers=auth_headers)
    assert r.status_code == 200

    db = SessionLocal()
    user = db.query(User).filter(User.email == "farmer@test.ug").first()
    code = _get_latest_otp_code(db, user.id)
    db.close()

    r = client.post(
        "/api/v1/auth/otp/setup",
        json={"delivery": "email", "target": "farmer@test.ug", "code": code},
        headers=auth_headers,
    )
    assert r.status_code == 200
    assert r.json()["otp_enabled"] is True
    assert r.json()["otp_method"] == "email"

    # Login should now return otp_required
    r = client.post("/api/v1/auth/login", json={"email": "farmer@test.ug", "password": "Strong!Pass1"})
    assert r.status_code == 200
    assert r.json()["otp_required"] is True
    assert r.json()["otp_target"] is not None

    # Complete login with OTP
    db = SessionLocal()
    user = db.query(User).filter(User.email == "farmer@test.ug").first()
    code = _get_latest_otp_code(db, user.id)
    db.close()

    r = client.post(
        "/api/v1/auth/otp/verify",
        json={"email": "farmer@test.ug", "password": "Strong!Pass1", "code": code},
    )
    assert r.status_code == 200
    assert "access_token" in r.json()


def test_otp_invalid_code(client, auth_headers):
    """Wrong OTP code should be rejected."""
    r = client.post("/api/v1/auth/otp/send", json={"delivery": "email"}, headers=auth_headers)
    assert r.status_code == 200

    r = client.post(
        "/api/v1/auth/otp/verify",
        json={"email": "farmer@test.ug", "password": "Strong!Pass1", "code": "000000"},
    )
    assert r.status_code == 401


def test_otp_max_attempts(client, auth_headers):
    """After max failed attempts, OTP should be locked out."""
    from api.app.config import settings
    from api.app.database import SessionLocal
    from api.app.models import User

    r = client.post("/api/v1/auth/otp/send", json={"delivery": "email"}, headers=auth_headers)
    assert r.status_code == 200

    for _ in range(settings.otp_max_attempts):
        r = client.post(
            "/api/v1/auth/otp/verify",
            json={"email": "farmer@test.ug", "password": "Strong!Pass1", "code": "111111"},
        )
        assert r.status_code == 401

    # Even correct code should now fail
    db = SessionLocal()
    user = db.query(User).filter(User.email == "farmer@test.ug").first()
    code = _get_latest_otp_code(db, user.id)
    db.close()

    r = client.post(
        "/api/v1/auth/otp/verify",
        json={"email": "farmer@test.ug", "password": "Strong!Pass1", "code": code},
    )
    assert r.status_code == 401


def test_otp_disable(client, auth_headers):
    """Disable OTP 2FA and confirm login no longer requires it."""
    from api.app.database import SessionLocal
    from api.app.models import User

    # Enable OTP
    r = client.post("/api/v1/auth/otp/send", json={"delivery": "email"}, headers=auth_headers)
    db = SessionLocal()
    user = db.query(User).filter(User.email == "farmer@test.ug").first()
    code = _get_latest_otp_code(db, user.id)
    db.close()

    r = client.post(
        "/api/v1/auth/otp/setup",
        json={"delivery": "email", "target": "farmer@test.ug", "code": code},
        headers=auth_headers,
    )
    assert r.json()["otp_enabled"] is True

    # Disable
    r = client.post("/api/v1/auth/otp/disable", headers=auth_headers)
    assert r.status_code == 200
    assert r.json()["otp_enabled"] is False
    assert r.json()["otp_method"] is None

    # Login should work without OTP
    r = client.post("/api/v1/auth/login", json={"email": "farmer@test.ug", "password": "Strong!Pass1"})
    assert r.status_code == 200
    assert r.json()["otp_required"] is False
    assert "access_token" in r.json()


def test_otp_setup_requires_correct_code(client, auth_headers):
    """OTP setup should fail with wrong verification code."""
    r = client.post("/api/v1/auth/otp/send", json={"delivery": "email"}, headers=auth_headers)
    assert r.status_code == 200

    r = client.post(
        "/api/v1/auth/otp/setup",
        json={"delivery": "email", "target": "farmer@test.ug", "code": "999999"},
        headers=auth_headers,
    )
    assert r.status_code == 400
