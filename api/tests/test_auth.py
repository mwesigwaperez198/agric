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
