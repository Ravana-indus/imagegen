import base64
from collections.abc import Callable
from typing import Protocol
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import GenerationItem, Project
from app.services.projects import aggregate_project_status


class WorkerStorage(Protocol):
    def download(self, key: str) -> bytes: ...

    def upload(self, key: str, payload: bytes, content_type: str) -> str: ...


class Editor(Protocol):
    def edit(
        self, product_image: str, background_image: str, instruction: str | None
    ): ...


def data_url(payload: bytes) -> str:
    encoded = base64.b64encode(payload).decode("ascii")
    return f"data:image/png;base64,{encoded}"


def execute_generation(
    item_id: str,
    session_factory: Callable[[], Session],
    storage: WorkerStorage,
    editor: Editor,
    fetch_output: Callable[[str], bytes],
) -> None:
    with session_factory() as db:
        item = db.get(GenerationItem, UUID(item_id))
        if item is None:
            raise ValueError("Unknown generation item")
        project = db.get(Project, item.project_id)
        if project is None:
            raise ValueError("Unknown project")
        item.status = "processing"
        item.attempt_count += 1
        db.commit()
        try:
            result = editor.edit(
                data_url(storage.download(item.source_product_asset_key)),
                data_url(storage.download(project.background_asset_key)),
                project.optional_instruction,
            )
            output = fetch_output(result.image_url)
            key = f"generated/projects/{project.id}/items/{item.id}/base.png"
            storage.upload(key, output, "image/png")
            item.status = "generated"
            item.provider_request_id = result.request_id
            item.base_composite_asset_key = key
            item.provider_error_code = None
            item.provider_error_message = None
        except Exception as exc:
            item.status = "failed"
            item.provider_error_code = exc.__class__.__name__
            item.provider_error_message = str(exc)[:500]
        statuses = list(
            db.scalars(
                select(GenerationItem.status).where(
                    GenerationItem.project_id == project.id
                )
            )
        )
        project.status = aggregate_project_status(statuses)
        db.commit()
