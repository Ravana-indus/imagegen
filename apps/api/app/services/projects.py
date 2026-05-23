from dataclasses import dataclass
from typing import Callable, Protocol
from uuid import UUID, uuid4

from sqlalchemy.orm import Session

from app.models import GenerationItem, OverlayLayout, Project
from app.services.assets import normalized_png


class WritableStorage(Protocol):
    def upload(self, key: str, payload: bytes, content_type: str) -> str: ...


@dataclass(frozen=True)
class ProjectRequest:
    name: str
    mode: str
    country_code: str
    optional_instruction: str | None = None


@dataclass(frozen=True)
class SourceUpload:
    filename: str
    content_type: str
    content: bytes


def validate_product_count(mode: str, count: int) -> None:
    if mode == "single" and count != 1:
        raise ValueError("Single projects require one product image")
    if mode == "batch" and not 1 <= count <= 25:
        raise ValueError("Batch projects require between 1 and 25 product images")
    if mode not in {"single", "batch"}:
        raise ValueError("Unsupported project mode")


def create_project_records(
    db: Session,
    storage: WritableStorage,
    enqueue: Callable[[str], None],
    admin_id: UUID,
    request: ProjectRequest,
    background: SourceUpload,
    logo: SourceUpload,
    products: list[SourceUpload],
    flag_bytes: bytes,
) -> Project:
    validate_product_count(request.mode, len(products))
    project_id = uuid4()
    prefix = f"sources/projects/{project_id}"
    project = Project(
        id=project_id,
        name=request.name,
        mode=request.mode,
        status="queued",
        background_asset_key=storage.upload(
            f"{prefix}/background.png",
            normalized_png(background.content, background.content_type),
            "image/png",
        ),
        logo_asset_key=storage.upload(
            f"{prefix}/logo.png",
            normalized_png(logo.content, logo.content_type),
            "image/png",
        ),
        country_code=request.country_code.upper(),
        flag_asset_key=storage.upload(f"{prefix}/flag.png", flag_bytes, "image/png"),
        optional_instruction=request.optional_instruction,
        created_by=admin_id,
    )
    db.add(project)
    item_ids: list[str] = []
    for product in products:
        item = GenerationItem(
            id=uuid4(),
            project_id=project_id,
            source_product_asset_key="",
            status="queued",
        )
        item.source_product_asset_key = storage.upload(
            f"{prefix}/products/{item.id}.png",
            normalized_png(product.content, product.content_type),
            "image/png",
        )
        db.add(item)
        db.add(OverlayLayout(generation_item_id=item.id))
        item_ids.append(str(item.id))
    db.commit()
    for item_id in item_ids:
        enqueue(item_id)
    return project


def aggregate_project_status(statuses: list[str]) -> str:
    if statuses and all(status in {"generated", "exported"} for status in statuses):
        return "completed"
    if statuses and all(status == "failed" for status in statuses):
        return "failed"
    if "failed" in statuses and any(
        status in {"generated", "exported"} for status in statuses
    ):
        return "partially_failed"
    if "processing" in statuses:
        return "processing"
    return "queued"


def retryable_status(status: str) -> bool:
    if status == "failed":
        return True
    if status in {"queued", "processing"}:
        raise ValueError("Only failed items may be retried")
    return False
