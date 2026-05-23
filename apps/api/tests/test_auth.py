from types import SimpleNamespace
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.db import Base, get_db
from app.main import app
from app.models import AdminUser
from app.security import password_hash


def app_client(monkeypatch) -> TestClient:
    engine = create_engine(
        "sqlite+pysqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        db.add(
            AdminUser(
                id=uuid4(),
                email="owner@example.com",
                password_hash=password_hash.hash("correct-password"),
            )
        )
        db.commit()

    def override_db():
        with Session(engine) as db:
            yield db

    monkeypatch.setattr(
        "app.security.get_settings",
        lambda: SimpleNamespace(session_secret="session-secret-for-tests"),
    )
    app.dependency_overrides[get_db] = override_db
    return TestClient(app, base_url="https://testserver")


def test_login_establishes_an_admin_session(monkeypatch) -> None:
    client = app_client(monkeypatch)

    response = client.post(
        "/api/v1/auth/login",
        json={"email": "owner@example.com", "password": "correct-password"},
    )

    assert response.status_code == 200
    assert "session=" in response.headers["set-cookie"]
    assert "HttpOnly" in response.headers["set-cookie"]
    assert client.get("/api/v1/auth/me").json() == {"email": "owner@example.com"}
    app.dependency_overrides.clear()


def test_login_rejects_invalid_credentials(monkeypatch) -> None:
    client = app_client(monkeypatch)

    response = client.post(
        "/api/v1/auth/login",
        json={"email": "owner@example.com", "password": "incorrect"},
    )

    assert response.status_code == 401
    app.dependency_overrides.clear()


def test_login_can_disable_secure_cookie_for_local_http(monkeypatch) -> None:
    client = app_client(monkeypatch)
    monkeypatch.setattr(
        "app.routes.auth.get_settings",
        lambda: SimpleNamespace(session_cookie_secure=False),
    )

    response = client.post(
        "/api/v1/auth/login",
        json={"email": "owner@example.com", "password": "correct-password"},
    )

    assert response.status_code == 200
    assert "Secure" not in response.headers["set-cookie"]
    app.dependency_overrides.clear()
