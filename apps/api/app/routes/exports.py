from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.routes.projects import get_storage
from app.schemas import ExportResponse
from app.security import require_admin
from app.services.exports import create_batch_zip
from app.storage import PrivateStorage

router = APIRouter(prefix="/api/v1/projects", tags=["exports"])


@router.post("/{project_id}/exports/zip", response_model=ExportResponse)
def export_project_zip(
    project_id: UUID,
    _: dict[str, str] = Depends(require_admin),
    db: Session = Depends(get_db),
    storage: PrivateStorage = Depends(get_storage),
) -> ExportResponse:
    try:
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
