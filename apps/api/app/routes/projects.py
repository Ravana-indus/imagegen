import re
from collections.abc import Callable
from uuid import UUID

import httpx
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.jobs import enqueue_generation
from app.models import GenerationItem, OverlayLayout, Project
from app.schemas import ItemResponse, LayoutResponse, ProjectResponse, ProjectSummary
from app.security import require_admin
from app.services.assets import MAX_INPUT_BYTES, normalized_png
from app.services.projects import ProjectRequest, SourceUpload, create_project_records
from app.storage import PrivateStorage

router = APIRouter(prefix="/api/v1/projects", tags=["projects"])
COUNTRY_CODE = re.compile(r"^[A-Za-z]{2}$")


def get_storage() -> PrivateStorage:
    return PrivateStorage()


def get_enqueue() -> Callable[[str], None]:
    return enqueue_generation


def fetch_country_flag(country_code: str) -> bytes:
    if not COUNTRY_CODE.fullmatch(country_code):
        raise ValueError("Country code must contain two letters")
    response = httpx.get(f"https://flagcdn.com/w640/{country_code.lower()}.png", timeout=15)
    response.raise_for_status()
    return normalized_png(response.content, "image/png")


def get_flag_fetcher() -> Callable[[str], bytes]:
    return fetch_country_flag


def _layout_response(layout: OverlayLayout) -> LayoutResponse:
    return LayoutResponse.model_validate(layout)


def item_response(
    db: Session, storage: PrivateStorage, item: GenerationItem
) -> ItemResponse:
    layout = db.get(OverlayLayout, item.id)
    if layout is None:
        raise HTTPException(status_code=500, detail="Item layout is missing")
    preview_url = None
    if item.base_composite_asset_key:
        preview_url = storage.signed_url(
            item.base_composite_asset_key, get_settings().signed_url_ttl_seconds
        )
    return ItemResponse(
        id=item.id,
        status=item.status,
        attempt_count=item.attempt_count,
        preview_url=preview_url,
        error_message=item.provider_error_message,
        layout=_layout_response(layout),
    )


def project_response(
    db: Session, storage: PrivateStorage, project: Project
) -> ProjectResponse:
    ttl = get_settings().signed_url_ttl_seconds
    items = list(
        db.scalars(
            select(GenerationItem)
            .where(GenerationItem.project_id == project.id)
            .order_by(GenerationItem.created_at)
        )
    )
    return ProjectResponse(
        id=project.id,
        name=project.name,
        mode=project.mode,
        status=project.status,
        country_code=project.country_code,
        created_at=project.created_at,
        background_url=storage.signed_url(project.background_asset_key, ttl),
        logo_url=storage.signed_url(project.logo_asset_key, ttl),
        flag_url=storage.signed_url(project.flag_asset_key, ttl),
        items=[item_response(db, storage, item) for item in items],
    )


async def _source_file(upload: UploadFile) -> SourceUpload:
    return SourceUpload(
        filename=upload.filename or "upload",
        content_type=upload.content_type or "application/octet-stream",
        content=await upload.read(MAX_INPUT_BYTES + 1),
    )


@router.get("", response_model=list[ProjectSummary])
def list_projects(
    _: dict[str, str] = Depends(require_admin), db: Session = Depends(get_db)
) -> list[Project]:
    return list(db.scalars(select(Project).order_by(Project.created_at.desc())))


@router.get("/{project_id}", response_model=ProjectResponse)
def get_project(
    project_id: UUID,
    _: dict[str, str] = Depends(require_admin),
    db: Session = Depends(get_db),
    storage: PrivateStorage = Depends(get_storage),
) -> ProjectResponse:
    project = db.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return project_response(db, storage, project)


@router.post("", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
async def create_project(
    name: str = Form(min_length=1, max_length=120),
    mode: str = Form(),
    country_code: str = Form(min_length=2, max_length=2),
    optional_instruction: str | None = Form(default=None, max_length=1000),
    background: UploadFile = File(),
    logo: UploadFile = File(),
    products: list[UploadFile] = File(),
    admin: dict[str, str] = Depends(require_admin),
    db: Session = Depends(get_db),
    storage: PrivateStorage = Depends(get_storage),
    enqueue: Callable[[str], None] = Depends(get_enqueue),
    flag_fetcher: Callable[[str], bytes] = Depends(get_flag_fetcher),
) -> ProjectResponse:
    try:
        project = create_project_records(
            db,
            storage,
            enqueue,
            UUID(admin["sub"]),
            ProjectRequest(name, mode, country_code, optional_instruction),
            await _source_file(background),
            await _source_file(logo),
            [await _source_file(product) for product in products],
            flag_fetcher(country_code),
        )
    except (ValueError, httpx.HTTPError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return project_response(db, storage, project)
