import os

os.environ["DATABASE_URL"] = "sqlite:///./data/test.db"
os.environ["SECRET_KEY"] = "test-secret-key-for-pytest-only"
os.environ["WEBHOOK_LOG_PATH"] = "data/test_webhooks.jsonl"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from api.app.database import Base, engine  # noqa: E402
from api.app.main import app  # noqa: E402
from api.app.security import reset_rate_limits  # noqa: E402


@pytest.fixture()
def client():
    reset_rate_limits()
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    with TestClient(app) as c:
        yield c
    Base.metadata.drop_all(bind=engine)


@pytest.fixture()
def auth_headers(client):
    resp = client.post(
        "/api/v1/auth/register",
        json={
            "email": "farmer@test.ug",
            "full_name": "Test Farmer",
            "password": "Strong!Pass1",
            "phone": "+256700111222",
            "role": "farmer",
        },
    )
    assert resp.status_code == 201, resp.text
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture()
def consumer_headers(client):
    resp = client.post(
        "/api/v1/auth/register",
        json={
            "email": "buyer@test.ug",
            "full_name": "Test Buyer",
            "password": "Strong!Pass1",
            "phone": "+256700333444",
            "role": "consumer",
        },
    )
    assert resp.status_code == 201, resp.text
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture()
def admin_headers(client):
    resp = client.post(
        "/api/v1/auth/register",
        json={
            "email": "admin@test.ug",
            "full_name": "Test Admin",
            "password": "Strong!Pass1",
            "role": "consumer",
        },
    )
    assert resp.status_code == 201, resp.text
    from api.app.database import SessionLocal
    from api.app.models import User

    db = SessionLocal()
    db.query(User).filter(User.email == "admin@test.ug").update({"role": "admin"})
    db.commit()
    db.close()
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}
