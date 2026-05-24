from dataclasses import dataclass
from typing import Callable, Protocol
from uuid import UUID, uuid4

from sqlalchemy.orm import Session

from app.models import GenerationItem, OverlayLayout, Project
from app.services.assets import normalize_png


class WritableStorage(Protocol):
    def upload(self, key: str, payload: bytes, content_type: str) -> str: ...


@dataclass(frozen=True)
class ProjectRequest:
    name: str
    mode: str
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
    background: SourceUpload | None,
    logo: SourceUpload | None,
    flag: SourceUpload | None,
    products: list[SourceUpload],
    background_asset_key: str | None = None,
    logo_asset_key: str | None = None,
    flag_asset_key: str | None = None,
    product_asset_keys: list[str] | None = None,
) -> Project:
    staged_product_keys = product_asset_keys or []
    product_count = len(staged_product_keys) if staged_product_keys else len(products)
    validate_product_count(request.mode, product_count)
    if background_asset_key is None and background is None:
        raise ValueError("Background image is required")
    if logo_asset_key is None and logo is None:
        raise ValueError("Logo image is required")
    if flag_asset_key is None and flag is None:
        raise ValueError("Flag image is required")
    if not staged_product_keys and not products:
        raise ValueError("At least one product image is required")

    project_id = uuid4()
    prefix = f"sources/projects/{project_id}"
    if background_asset_key is None:
        background_asset_key = storage.upload(
            f"{prefix}/background.png",
            normalize_png(
                background.content, background.content_type, "Background image"
            ),
            "image/png",
        )
    if logo_asset_key is None:
        logo_asset_key = storage.upload(
            f"{prefix}/logo.png",
            normalize_png(logo.content, logo.content_type, "Logo image"),
            "image/png",
        )
    if flag_asset_key is None:
        flag_asset_key = storage.upload(
            f"{prefix}/flag.png",
            normalize_png(
                flag.content, flag.content_type, "Flag image"
            ),
            "image/png",
        )
    project = Project(
        id=project_id,
        name=request.name,
        mode=request.mode,
        status="queued",
        background_asset_key=background_asset_key,
        logo_asset_key=logo_asset_key,
        flag_asset_key=flag_asset_key,
        optional_instruction=request.optional_instruction,
        created_by=admin_id,
    )
    db.add(project)
    item_ids: list[str] = []
    if staged_product_keys:
        product_keys = staged_product_keys
    else:
        product_keys = [
            storage.upload(
                f"{prefix}/products/{uuid4()}.png",
                normalize_png(
                    product.content,
                    product.content_type,
                    f"Product image '{product.filename}'",
                ),
                "image/png",
            )
            for product in products
        ]

    for product_key in product_keys:
        item = GenerationItem(
            id=uuid4(),
            project_id=project_id,
            source_product_asset_key=product_key,
            status="queued",
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
