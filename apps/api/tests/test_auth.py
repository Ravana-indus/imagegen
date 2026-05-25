from types import SimpleNamespace
from uuid import uuid4

from fastapi.testclient import TestClient
from supabase_auth.errors import AuthInvalidCredentialsError
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.db import Base, get_db
from app.main import app
from app.models import AdminUser
from app.security import password_hash


def app_client(
    monkeypatch, *, seed_admin: bool = True, fake_auth: "FakeSupabaseAuth | None" = None
) -> tuple[TestClient, object]:
    engine = create_engine(
        "sqlite+pysqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    if seed_admin:
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

    settings = SimpleNamespace(
        auth_mode="session",
        database_url="postgresql+psycopg://user:password@db.example/postgres",
        session_secret="session-secret-for-tests",
        session_cookie_secure=True,
        supabase_url="https://example.supabase.co",
        supabase_secret_key="secret-key",
    )
    monkeypatch.setattr(
        "app.security.get_settings",
        lambda: settings,
    )
    monkeypatch.setattr(
        "app.routes.auth.get_settings",
        lambda: settings,
    )
    if fake_auth is None:
        fake_auth = FakeSupabaseAuth(str(uuid4()))
    monkeypatch.setattr(
        "app.routes.auth.create_supabase_auth_client",
        lambda: FakeSupabaseClient(fake_auth),
        raising=False,
    )
    app.dependency_overrides[get_db] = override_db
    return TestClient(app, base_url="https://testserver"), engine


class FakeSupabaseAuth:
    def __init__(
        self,
        user_id: str,
        *,
        role: str | None = "admin",
        accepted_password: str = "correct-password",
    ) -> None:
        self.user_id = user_id
        self.role = role
        self.accepted_password = accepted_password
        self.credentials: dict[str, str] | None = None

    def sign_in_with_password(self, credentials: dict[str, str]):
        self.credentials = credentials
        if credentials["password"] != self.accepted_password:
            raise AuthInvalidCredentialsError("invalid credentials")
        return SimpleNamespace(
            user=SimpleNamespace(
                id=self.user_id,
                email=credentials["email"],
                app_metadata={"role": self.role} if self.role else {},
            )
        )


class FakeSupabaseClient:
    def __init__(self, auth: FakeSupabaseAuth) -> None:
        self.auth = auth


def test_login_establishes_an_admin_session(monkeypatch) -> None:
    client, _ = app_client(monkeypatch)

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
    client, _ = app_client(monkeypatch)

    response = client.post(
        "/api/v1/auth/login",
        json={"email": "owner@example.com", "password": "incorrect"},
    )

    assert response.status_code == 401
    app.dependency_overrides.clear()


def test_login_can_disable_secure_cookie_for_local_http(monkeypatch) -> None:
    client, _ = app_client(monkeypatch)
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


def test_login_uses_supabase_auth_and_creates_admin_profile(monkeypatch) -> None:
    auth_user_id = uuid4()
    fake_auth = FakeSupabaseAuth(str(auth_user_id))
    client, engine = app_client(monkeypatch, seed_admin=False, fake_auth=fake_auth)

    response = client.post(
        "/api/v1/auth/login",
        json={"email": "Owner@Example.com", "password": "correct-password"},
    )

    assert response.status_code == 200
    assert fake_auth.credentials == {
        "email": "owner@example.com",
        "password": "correct-password",
    }
    assert client.get("/api/v1/auth/me").json() == {"email": "owner@example.com"}
    with Session(engine) as db:
        profile = db.get(AdminUser, auth_user_id)
    assert profile is not None
    assert profile.email == "owner@example.com"
    assert profile.password_hash == "supabase-auth"
    app.dependency_overrides.clear()


def test_login_rejects_supabase_users_without_admin_role(monkeypatch) -> None:
    fake_auth = FakeSupabaseAuth(str(uuid4()), role="viewer")
    client, _ = app_client(monkeypatch, seed_admin=False, fake_auth=fake_auth)

    response = client.post(
        "/api/v1/auth/login",
        json={"email": "owner@example.com", "password": "correct-password"},
    )

    assert response.status_code == 403
    app.dependency_overrides.clear()
