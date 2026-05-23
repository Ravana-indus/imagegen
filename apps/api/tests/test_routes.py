from io import BytesIO
from types import SimpleNamespace
from uuid import UUID, uuid4

from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.db import Base, get_db
from app.main import app
from app.models import AdminUser, GenerationItem
from app.routes.projects import get_enqueue, get_flag_fetcher, get_storage
from app.security import require_admin


def png(color: tuple[int, int, int, int] = (80, 90, 100, 255)) -> bytes:
    stream = BytesIO()
    Image.new("RGBA", (384, 384), color).save(stream, "PNG")
    return stream.getvalue()


class MemoryStorage:
    def __init__(self) -> None:
        self.files: dict[str, bytes] = {}

    def upload(self, key: str, payload: bytes, content_type: str) -> str:
        self.files[key] = payload
        return key

    def download(self, key: str) -> bytes:
        return self.files[key]

    def signed_url(self, key: str, expires_in: int) -> str:
        return f"https://assets.test/signed/{key}?ttl={expires_in}"


def api_client() -> tuple[TestClient, object, MemoryStorage, list[str], UUID]:
    engine = create_engine(
        "sqlite+pysqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    admin_id = uuid4()
    with Session(engine) as db:
        db.add(
            AdminUser(
                id=admin_id, email="owner@example.com", password_hash="unused-for-test"
            )
        )
        db.commit()

    def override_db():
        with Session(engine) as db:
            yield db

    storage = MemoryStorage()
    jobs: list[str] = []
    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[require_admin] = lambda: {
        "sub": str(admin_id),
        "email": "owner@example.com",
    }
    app.dependency_overrides[get_storage] = lambda: storage
    app.dependency_overrides[get_enqueue] = lambda: jobs.append
    app.dependency_overrides[get_flag_fetcher] = lambda: lambda country_code: png(
        (0, 120, 40, 255)
    )
    return TestClient(app), engine, storage, jobs, admin_id


def create_batch(client: TestClient):
    return client.post(
        "/api/v1/projects",
        data={
            "name": "Summer range",
            "mode": "batch",
            "country_code": "LK",
            "optional_instruction": "Soft studio light",
        },
        files=[
            ("background", ("background.png", png(), "image/png")),
            ("logo", ("logo.png", png((255, 255, 255, 255)), "image/png")),
            ("products", ("one.png", png((20, 30, 40, 255)), "image/png")),
            ("products", ("two.png", png((50, 60, 70, 255)), "image/png")),
        ],
    )


def test_create_batch_uploads_sources_lists_items_and_enqueues_work(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        "app.routes.projects.get_settings",
        lambda: SimpleNamespace(signed_url_ttl_seconds=900),
    )
    client, _, storage, jobs, _ = api_client()

    response = create_batch(client)

    assert response.status_code == 201
    project = response.json()
    assert project["country_code"] == "LK"
    assert len(project["items"]) == 2
    assert len(jobs) == 2
    assert any(key.endswith("/flag.png") for key in storage.files)
    assert client.get("/api/v1/projects").json()[0]["name"] == "Summer range"
    app.dependency_overrides.clear()


def test_layout_export_and_batch_zip_return_signed_downloads(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.routes.projects.get_settings",
        lambda: SimpleNamespace(signed_url_ttl_seconds=900),
    )
    client, engine, storage, _, _ = api_client()
    project = create_batch(client).json()
    item_id = project["items"][0]["id"]
    with Session(engine) as db:
        item = db.get(GenerationItem, UUID(item_id))
        item.status = "generated"
        item.base_composite_asset_key = f"generated/{item.id}.png"
        storage.upload(item.base_composite_asset_key, png(), "image/png")
        db.commit()

    updated = client.put(
        f"/api/v1/items/{item_id}/layout",
        json={"logo_x": 0.12, "flag_visible": False},
    )
    exported = client.post(f"/api/v1/items/{item_id}/export")
    archive = client.post(f"/api/v1/projects/{project['id']}/exports/zip")

    assert updated.status_code == 200
    assert updated.json()["revision"] == 2
    assert exported.json()["download_url"].startswith("https://assets.test/signed/")
    assert archive.json()["asset_type"] == "batch_zip"
    app.dependency_overrides.clear()


def test_failed_item_can_be_retried(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.routes.projects.get_settings",
        lambda: SimpleNamespace(signed_url_ttl_seconds=900),
    )
    client, engine, _, jobs, _ = api_client()
    project = create_batch(client).json()
    item_id = project["items"][0]["id"]
    with Session(engine) as db:
        item = db.get(GenerationItem, UUID(item_id))
        item.status = "failed"
        db.commit()

    response = client.post(f"/api/v1/items/{item_id}/retry")

    assert response.status_code == 202
    assert response.json()["status"] == "queued"
    assert jobs[-1] == item_id
    app.dependency_overrides.clear()
