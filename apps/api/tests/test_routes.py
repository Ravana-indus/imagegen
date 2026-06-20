from io import BytesIO
from types import SimpleNamespace
from uuid import UUID, uuid4

from fastapi import HTTPException
from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.db import Base, get_db
from app.main import app
from app.models import AdminUser, GenerationItem, Project
from app.routes.projects import (
    get_enqueue,
    get_storage,
    get_supabase_storage,
)
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
    return TestClient(app), engine, storage, jobs, admin_id


def create_batch(client: TestClient):
    return client.post(
        "/api/v1/projects",
        data={
            "name": "Summer range",
            "mode": "batch",
            "optional_instruction": "Soft studio light",
        },
        files=[
            ("background", ("background.png", png(), "image/png")),
            ("logo", ("logo.png", png((255, 255, 255, 255)), "image/png")),
            ("flag", ("flag.png", png((0, 120, 40, 255)), "image/png")),
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
    assert project["mode"] == "batch"
    assert len(project["items"]) == 2
    assert len(jobs) == 2
    assert any(key.endswith("/flag.png") for key in storage.files)
    assert client.get("/api/v1/projects").json()[0]["name"] == "Summer range"
    app.dependency_overrides.clear()


def test_create_response_refreshes_project_after_inline_generation(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.routes.projects.get_settings",
        lambda: SimpleNamespace(signed_url_ttl_seconds=900),
    )
    client, engine, _, _, _ = api_client()

    def mark_generated(item_id: str) -> None:
        with Session(engine) as db:
            item = db.get(GenerationItem, UUID(item_id))
            item.status = "generated"
            project = db.get(Project, item.project_id)
            project.status = "completed"
            db.commit()

    app.dependency_overrides[get_enqueue] = lambda: mark_generated

    response = client.post(
        "/api/v1/projects",
        data={"name": "Inline", "mode": "single"},
        files=[
            ("background", ("background.png", png(), "image/png")),
            ("logo", ("logo.png", png(), "image/png")),
            ("flag", ("flag.png", png(), "image/png")),
            ("products", ("product.png", png(), "image/png")),
        ],
    )

    assert response.status_code == 201
    assert response.json()["status"] == "completed"
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
    incomplete_archive = client.post(f"/api/v1/projects/{project['id']}/exports/zip")
    second_item_id = project["items"][1]["id"]
    with Session(engine) as db:
        item = db.get(GenerationItem, UUID(second_item_id))
        item.status = "generated"
        item.base_composite_asset_key = f"generated/{item.id}.png"
        storage.upload(item.base_composite_asset_key, png(), "image/png")
        db.commit()
    archive = client.post(f"/api/v1/projects/{project['id']}/exports/zip")

    assert updated.status_code == 200
    assert updated.json()["revision"] == 2
    assert exported.json()["download_url"].startswith("https://assets.test/signed/")
    assert incomplete_archive.status_code == 409
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


def test_creative_direction_reserves_space_for_the_protected_qwen_prompt(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        "app.routes.projects.get_settings",
        lambda: SimpleNamespace(signed_url_ttl_seconds=900),
    )
    client, _, _, _, _ = api_client()

    response = client.post(
        "/api/v1/projects",
        data={
            "name": "Long direction",
            "mode": "single",
            "optional_instruction": "x" * 451,
        },
        files=[
            ("background", ("background.png", png(), "image/png")),
            ("logo", ("logo.png", png(), "image/png")),
            ("flag", ("flag.png", png(), "image/png")),
            ("products", ("product.png", png(), "image/png")),
        ],
    )

    assert response.status_code == 422
    app.dependency_overrides.clear()


def test_background_and_product_can_be_uploaded_to_supabase(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.routes.projects.get_settings",
        lambda: SimpleNamespace(signed_url_ttl_seconds=900),
    )
    client, _, storage, _, _ = api_client()
    project = create_batch(client).json()
    item_id = project["items"][0]["id"]

    uploads: dict[str, bytes] = {}

    class SupabaseSink:
        def upload(self, key: str, payload: bytes, content_type: str) -> str:
            uploads[key] = payload
            return key

    app.dependency_overrides[get_supabase_storage] = lambda: SupabaseSink()

    background = client.post(f"/api/v1/projects/{project['id']}/upload-background")
    product = client.post(f"/api/v1/items/{item_id}/upload-product")

    assert background.status_code == 200
    assert product.status_code == 200
    background_key = background.json()["supabase_key"]
    product_key = product.json()["supabase_key"]
    assert background_key in uploads
    assert product_key in uploads
    assert background.json()["source_key"] in storage.files
    assert product.json()["source_key"] in storage.files
    app.dependency_overrides.clear()


def test_upload_to_supabase_requires_credentials(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.routes.projects.get_settings",
        lambda: SimpleNamespace(signed_url_ttl_seconds=900),
    )
    client, _, _, _, _ = api_client()
    project = create_batch(client).json()
    item_id = project["items"][0]["id"]
    app.dependency_overrides[get_supabase_storage] = lambda: (_ for _ in ()).throw(
        HTTPException(
            status_code=409,
            detail="Supabase server storage credentials are not configured",
        )
    )

    background = client.post(f"/api/v1/projects/{project['id']}/upload-background")
    product = client.post(f"/api/v1/items/{item_id}/upload-product")

    assert background.status_code == 409
    assert product.status_code == 409
    app.dependency_overrides.clear()


def test_source_upload_stages_new_project_images_in_configured_storage(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.routes.projects.get_settings",
        lambda: SimpleNamespace(signed_url_ttl_seconds=900),
    )
    client, _, storage, _, _ = api_client()

    response = client.post(
        "/api/v1/projects/source-uploads",
        data={"project_name": "Launch", "asset_type": "background"},
        files=[("files", ("background.png", png(), "image/png"))],
    )

    assert response.status_code == 200
    upload = response.json()["uploads"][0]
    assert upload["asset_type"] == "background"
    assert upload["storage_key"] in storage.files
    assert upload["signed_url"].startswith("https://assets.test/signed/")
    app.dependency_overrides.clear()


def test_create_project_uses_staged_sources_from_configured_storage(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.routes.projects.get_settings",
        lambda: SimpleNamespace(signed_url_ttl_seconds=900),
    )
    client, engine, storage, jobs, _ = api_client()

    response = client.post(
        "/api/v1/projects",
        files=[
            ("name", (None, "Staged")),
            ("mode", (None, "single")),
            (
                "background_asset_key",
                (None, "sources/staged/staged/background/1.png"),
            ),
            (
                "product_asset_keys",
                (None, "sources/staged/staged/product/1.png"),
            ),
            ("logo", ("logo.png", png(), "image/png")),
            ("flag", ("flag.png", png(), "image/png")),
        ],
    )

    assert response.status_code == 201
    project = response.json()
    assert project["background_url"].startswith("https://assets.test/signed/")
    assert len(project["items"]) == 1
    assert len(jobs) == 1
    with Session(engine) as db:
        item = db.get(GenerationItem, UUID(project["items"][0]["id"]))
    assert item.source_product_asset_key == "sources/staged/staged/product/1.png"
    assert project["background_url"].startswith("https://assets.test/signed/")
    app.dependency_overrides.clear()


def test_existing_assets_route_returns_reusable_project_images(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.routes.projects.get_settings",
        lambda: SimpleNamespace(signed_url_ttl_seconds=900),
    )
    client, _, _, _, _ = api_client()
    create_batch(client)

    response = client.get("/api/v1/projects/assets")

    assert response.status_code == 200
    body = response.json()
    assert len(body["backgrounds"]) == 1
    assert len(body["logos"]) == 1
    assert len(body["flags"]) == 1
    assert body["backgrounds"][0]["url"].startswith("https://assets.test/signed/")
    app.dependency_overrides.clear()


def test_generated_images_route_lists_names_details_and_preview_urls(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.routes.projects.get_settings",
        lambda: SimpleNamespace(signed_url_ttl_seconds=900),
    )
    client, engine, storage, _, _ = api_client()
    project = create_batch(client).json()
    first_item_id = project["items"][0]["id"]
    with Session(engine) as db:
        item = db.get(GenerationItem, UUID(first_item_id))
        item.status = "generated"
        item.base_composite_asset_key = f"generated/{item.id}.png"
        storage.upload(item.base_composite_asset_key, png(), "image/png")
        db.commit()

    response = client.get("/api/v1/projects/generated-images")

    assert response.status_code == 200
    images = response.json()
    assert len(images) == 1
    assert images[0]["name"] == "Summer range - Product 1"
    assert images[0]["project_name"] == "Summer range"
    assert images[0]["item_index"] == 1
    assert images[0]["status"] == "generated"
    assert images[0]["preview_url"].startswith("https://assets.test/signed/")
    app.dependency_overrides.clear()


def test_generated_images_route_survives_missing_storage_objects(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.routes.projects.get_settings",
        lambda: SimpleNamespace(signed_url_ttl_seconds=900),
    )
    client, engine, storage, _, _ = api_client()
    project = create_batch(client).json()
    first_item_id = project["items"][0]["id"]
    with Session(engine) as db:
        item = db.get(GenerationItem, UUID(first_item_id))
        item.status = "generated"
        item.base_composite_asset_key = f"generated/{item.id}.png"
        db.commit()

    def missing_signed_url(key: str, expires_in: int) -> str:
        raise RuntimeError("Object not found")

    storage.signed_url = missing_signed_url

    response = client.get("/api/v1/projects/generated-images")

    assert response.status_code == 200
    images = response.json()
    assert images[0]["name"] == "Summer range - Product 1"
    assert images[0]["preview_url"] is None
    app.dependency_overrides.clear()


def test_project_response_omits_missing_generated_previews(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.routes.projects.get_settings",
        lambda: SimpleNamespace(signed_url_ttl_seconds=900),
    )
    client, engine, storage, _, _ = api_client()
    project = create_batch(client).json()
    first_item_id = project["items"][0]["id"]
    with Session(engine) as db:
        item = db.get(GenerationItem, UUID(first_item_id))
        item.status = "generated"
        item.base_composite_asset_key = f"generated/{item.id}.png"
        db.commit()

    def signed_url(key: str, expires_in: int) -> str:
        if key.startswith("generated/"):
            raise RuntimeError("Object not found")
        return f"https://assets.test/signed/{key}?ttl={expires_in}"

    storage.signed_url = signed_url

    response = client.get(f"/api/v1/projects/{project['id']}")

    assert response.status_code == 200
    assert response.json()["items"][0]["preview_url"] is None
    app.dependency_overrides.clear()


def test_missing_dev_storage_asset_returns_not_found() -> None:
    response = TestClient(app).get("/storage/does-not-exist.png")

    assert response.status_code == 404
