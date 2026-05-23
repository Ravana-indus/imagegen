from collections.abc import Callable
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.models import GenerationItem, OverlayLayout, Project
from app.routes.projects import get_enqueue, get_storage, item_response
from app.schemas import ExportResponse, ItemResponse, LayoutResponse, LayoutUpdate, RetryResponse
from app.security import require_admin
from app.services.exports import export_final_image
from app.services.projects import retryable_status
from app.storage import PrivateStorage

router = APIRouter(prefix="/api/v1/items", tags=["items"])


@router.get("/{item_id}", response_model=ItemResponse)
def get_item(
    item_id: UUID,
    _: dict[str, str] = Depends(require_admin),
    db: Session = Depends(get_db),
    storage: PrivateStorage = Depends(get_storage),
) -> ItemResponse:
    item = db.get(GenerationItem, item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Generation item not found")
    return item_response(db, storage, item)


@router.put("/{item_id}/layout", response_model=LayoutResponse)
def update_layout(
    item_id: UUID,
    payload: LayoutUpdate,
    _: dict[str, str] = Depends(require_admin),
    db: Session = Depends(get_db),
) -> LayoutResponse:
    layout = db.get(OverlayLayout, item_id)
    if layout is None:
        raise HTTPException(status_code=404, detail="Generation item not found")
    changes = payload.model_dump(exclude_unset=True, exclude_none=True)
    if changes:
        for field, value in changes.items():
            setattr(layout, field, value)
        layout.revision += 1
        db.commit()
        db.refresh(layout)
    return LayoutResponse.model_validate(layout)


@router.post("/{item_id}/retry", response_model=RetryResponse, status_code=status.HTTP_202_ACCEPTED)
def retry_item(
    item_id: UUID,
    _: dict[str, str] = Depends(require_admin),
    db: Session = Depends(get_db),
    enqueue: Callable[[str], None] = Depends(get_enqueue),
) -> RetryResponse:
    item = db.get(GenerationItem, item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Generation item not found")
    try:
        allowed = retryable_status(item.status)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if not allowed:
        raise HTTPException(status_code=409, detail="Completed items cannot be retried")
    item.status = "queued"
    item.provider_error_code = None
    item.provider_error_message = None
    project = db.get(Project, item.project_id)
    if project is not None:
        project.status = "queued"
    db.commit()
    enqueue(str(item.id))
    return RetryResponse(id=item.id, status=item.status)


@router.post("/{item_id}/export", response_model=ExportResponse)
def export_item(
    item_id: UUID,
    _: dict[str, str] = Depends(require_admin),
    db: Session = Depends(get_db),
    storage: PrivateStorage = Depends(get_storage),
) -> ExportResponse:
    try:
        asset = export_final_image(db, storage, item_id)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return ExportResponse(
        id=asset.id,
        asset_type=asset.asset_type,
        download_url=storage.signed_url(
            asset.storage_key, get_settings().signed_url_ttl_seconds
        ),
    )
