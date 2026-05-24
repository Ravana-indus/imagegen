from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.models import ExportAsset, GenerationItem, OverlayLayout
from app.routes.projects import get_storage
from app.schemas import ExportResponse
from app.security import require_admin
from app.services.exports import create_batch_zip, export_final_image
from app.storage import DevStorage, PrivateStorage

router = APIRouter(prefix="/api/v1/projects", tags=["exports"])


@router.post("/{project_id}/exports/zip", response_model=ExportResponse)
def export_project_zip(
    project_id: UUID,
    _: dict[str, str] = Depends(require_admin),
    db: Session = Depends(get_db),
    storage: DevStorage | PrivateStorage = Depends(get_storage),
) -> ExportResponse:
    items = list(
        db.scalars(
            select(GenerationItem).where(GenerationItem.project_id == project_id)
        )
    )
    if not items or any(item.base_composite_asset_key is None for item in items):
        raise HTTPException(
            status_code=409, detail="All batch images must finish generation first"
        )
    try:
        for item in items:
            layout = db.get(OverlayLayout, item.id)
            existing = None
            if layout is not None:
                existing = db.scalar(
                    select(ExportAsset).where(
                        ExportAsset.generation_item_id == item.id,
                        ExportAsset.asset_type == "final_png",
                        ExportAsset.layout_revision == layout.revision,
                    )
                )
            if existing is None:
                export_final_image(db, storage, item.id)
        asset = create_batch_zip(db, storage, project_id)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return ExportResponse(
        id=asset.id,
        asset_type=asset.asset_type,
        download_url=storage.signed_url(
            asset.storage_key, get_settings().signed_url_ttl_seconds
        ),
    )
