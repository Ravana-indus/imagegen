from io import BytesIO
from types import SimpleNamespace
from uuid import UUID, uuid4
from zipfile import ZipFile

from PIL import Image
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.db import Base
from app.models import AdminUser, GenerationItem, OverlayLayout, Project
from app.services.exports import create_batch_zip, export_final_image
from app.services.projects import ProjectRequest, SourceUpload, create_project_records
from app.services.worker_runtime import execute_generation


def png(color: tuple[int, int, int, int] = (255, 255, 255, 255)) -> bytes:
    output = BytesIO()
    Image.new("RGBA", (384, 384), color).save(output, "PNG")
    return output.getvalue()


class MemoryStorage:
    def __init__(self) -> None:
        self.files: dict[str, bytes] = {}

    def upload(self, key: str, payload: bytes, content_type: str) -> str:
        self.files[key] = payload
        return key

    def download(self, key: str) -> bytes:
        return self.files[key]


def database() -> tuple[object, object]:
    engine = create_engine(
        "sqlite+pysqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    factory = lambda: Session(engine)
    with factory() as db:
        admin = AdminUser(
            id=uuid4(), email="owner@example.com", password_hash="not-used-in-test"
        )
        db.add(admin)
        db.commit()
        return factory, admin.id


def create_batch(factory, admin_id, storage: MemoryStorage) -> tuple[Project, list[str]]:
    jobs: list[str] = []
    with factory() as db:
        project = create_project_records(
            db=db,
            storage=storage,
            enqueue=jobs.append,
            admin_id=admin_id,
            request=ProjectRequest("Campaign", "batch", "LK", "Soft daylight"),
            background=SourceUpload("background.png", "image/png", png()),
            logo=SourceUpload("logo.png", "image/png", png((255, 0, 0, 255))),
            products=[
                SourceUpload("one.png", "image/png", png()),
                SourceUpload("two.png", "image/png", png()),
            ],
            flag_bytes=png((0, 0, 255, 255)),
        )
        project_id = project.id
    with factory() as db:
        return db.get(Project, project_id), jobs


def test_batch_project_stores_shared_sources_and_enqueues_each_product() -> None:
    factory, admin_id = database()
    storage = MemoryStorage()

    project, jobs = create_batch(factory, admin_id, storage)

    assert project.mode == "batch"
    assert project.background_asset_key.startswith("sources/projects/")
    assert len(jobs) == 2
    with factory() as db:
        assert len(list(db.scalars(select(GenerationItem)))) == 2
        assert len(list(db.scalars(select(OverlayLayout)))) == 2


def test_generation_stores_temporary_qwen_result_as_a_permanent_base_image() -> None:
    factory, admin_id = database()
    storage = MemoryStorage()
    project, jobs = create_batch(factory, admin_id, storage)
    editor = SimpleNamespace(
        edit=lambda product, background, instruction: SimpleNamespace(
            request_id="req-1", image_url="https://temporary.example/base.png"
        )
    )

    execute_generation(
        jobs[0],
        session_factory=factory,
        storage=storage,
        editor=editor,
        fetch_output=lambda url: png((20, 20, 20, 255)),
    )

    with factory() as db:
        item = db.get(GenerationItem, UUID(jobs[0]))
        assert item.status == "generated"
        assert item.base_composite_asset_key.startswith("generated/projects/")
        assert storage.download(item.base_composite_asset_key).startswith(b"\x89PNG")


def test_export_renders_final_png_and_batch_zip_from_saved_results() -> None:
    factory, admin_id = database()
    storage = MemoryStorage()
    project, jobs = create_batch(factory, admin_id, storage)
    with factory() as db:
        for item_id in jobs:
            item = db.get(GenerationItem, UUID(item_id))
            item.status = "generated"
            item.base_composite_asset_key = f"generated/projects/{project.id}/{item.id}.png"
            storage.upload(item.base_composite_asset_key, png(), "image/png")
        db.commit()
        exports = [export_final_image(db, storage, item_id) for item_id in jobs]
        archive = create_batch_zip(db, storage, project.id)

    assert len(exports) == 2
    with ZipFile(BytesIO(storage.download(archive.storage_key))) as zipped:
        assert len(zipped.namelist()) == 2
