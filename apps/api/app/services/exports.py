from io import BytesIO
from typing import Protocol
from uuid import UUID
from zipfile import ZIP_DEFLATED, ZipFile

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import ExportAsset, GenerationItem, OverlayLayout, Project
from app.services.render import Layer, render_final_png


class ExportStorage(Protocol):
    def download(self, key: str) -> bytes: ...

    def upload(self, key: str, payload: bytes, content_type: str) -> str: ...


def _uuid(value: UUID | str) -> UUID:
    return value if isinstance(value, UUID) else UUID(value)


def export_final_image(
    db: Session, storage: ExportStorage, item_id: UUID | str
) -> ExportAsset:
    item = db.get(GenerationItem, _uuid(item_id))
    if item is None or item.base_composite_asset_key is None:
        raise ValueError("Generated image is not available")
    project = db.get(Project, item.project_id)
    layout = db.get(OverlayLayout, item.id)
    if project is None or layout is None:
        raise ValueError("Export inputs are not available")
    output = render_final_png(
        storage.download(item.base_composite_asset_key),
        storage.download(project.logo_asset_key),
        storage.download(project.flag_asset_key),
        Layer(
            float(layout.logo_x),
            float(layout.logo_y),
            float(layout.logo_width),
            float(layout.logo_height),
            layout.logo_visible,
        ),
        Layer(
            float(layout.flag_x),
            float(layout.flag_y),
            float(layout.flag_width),
            float(layout.flag_height),
            layout.flag_visible,
        ),
    )
    key = f"exports/projects/{project.id}/items/{item.id}/final-r{layout.revision}.png"
    storage.upload(key, output, "image/png")
    asset = ExportAsset(
        project_id=project.id,
        generation_item_id=item.id,
        asset_type="final_png",
        storage_key=key,
        layout_revision=layout.revision,
    )
    item.status = "exported"
    db.add(asset)
    db.commit()
    db.refresh(asset)
    return asset


def create_batch_zip(
    db: Session, storage: ExportStorage, project_id: UUID | str
) -> ExportAsset:
    project_uuid = _uuid(project_id)
    outputs = list(
        db.scalars(
            select(ExportAsset).where(
                ExportAsset.project_id == project_uuid,
                ExportAsset.asset_type == "final_png",
            )
        )
    )
    if not outputs:
        raise ValueError("No final images are available")
    archive_bytes = BytesIO()
    with ZipFile(archive_bytes, "w", ZIP_DEFLATED) as archive:
        for output in outputs:
            archive.writestr(
                f"{output.generation_item_id}-final.png",
                storage.download(output.storage_key),
            )
    key = f"exports/projects/{project_uuid}/batch.zip"
    storage.upload(key, archive_bytes.getvalue(), "application/zip")
    asset = ExportAsset(
        project_id=project_uuid,
        asset_type="batch_zip",
        storage_key=key,
    )
    db.add(asset)
    db.commit()
    db.refresh(asset)
    return asset
