from collections.abc import Callable
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.jobs import resolve_generation_handler
from app.models import GenerationItem, OverlayLayout, Project
from app.schemas import (
    AssetOption,
    GeneratedImageResponse,
    ItemResponse,
    LayoutResponse,
    ProjectAssetsResponse,
    ProjectResponse,
    ProjectSummary,
    StagedSourceUpload,
    StagedSourceUploadResponse,
    SupabaseUploadResponse,
)
from app.security import require_admin
from app.services.assets import MAX_INPUT_BYTES, normalize_png
from app.services.projects import ProjectRequest, SourceUpload, create_project_records
from app.storage import DevStorage, PrivateStorage, create_storage

router = APIRouter(prefix="/api/v1/projects", tags=["projects"])
STAGED_ASSET_TYPES = {"background", "product", "logo", "flag"}


def get_storage() -> DevStorage | PrivateStorage:
    return create_storage()


def get_supabase_storage() -> PrivateStorage:
    try:
        return PrivateStorage()
    except RuntimeError as exc:
        raise HTTPException(
            status_code=409,
            detail="Supabase server storage credentials are not configured",
        ) from exc


def get_enqueue() -> Callable[[str], None]:
    return resolve_generation_handler()


def _safe_signed_url(
    storage: DevStorage | PrivateStorage, key: str, ttl: int
) -> str | None:
    if isinstance(storage, DevStorage) and not (storage.root / key).is_file():
        return None
    try:
        return storage.signed_url(key, ttl)
    except Exception:
        return None


def _layout_response(layout: OverlayLayout) -> LayoutResponse:
    return LayoutResponse.model_validate(layout)


def item_response(
    db: Session, storage: DevStorage | PrivateStorage, item: GenerationItem
) -> ItemResponse:
    layout = db.get(OverlayLayout, item.id)
    if layout is None:
        raise HTTPException(status_code=500, detail="Item layout is missing")
    preview_url = None
    if item.base_composite_asset_key:
        preview_url = _safe_signed_url(
            storage,
            item.base_composite_asset_key,
            get_settings().signed_url_ttl_seconds,
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
    db: Session, storage: DevStorage | PrivateStorage, project: Project
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


def _staged_prefix(project_name: str) -> str:
    normalized = "".join(
        character.lower() if character.isalnum() else "-"
        for character in project_name.strip()
    ).strip("-")
    return normalized[:48] or "untitled"


@router.get("", response_model=list[ProjectSummary])
def list_projects(
    _: dict[str, str] = Depends(require_admin), db: Session = Depends(get_db)
) -> list[Project]:
    return list(db.scalars(select(Project).order_by(Project.created_at.desc())))


@router.get("/assets", response_model=ProjectAssetsResponse)
def get_existing_assets(
    _: dict[str, str] = Depends(require_admin),
    db: Session = Depends(get_db),
    storage: DevStorage | PrivateStorage = Depends(get_storage),
) -> ProjectAssetsResponse:
    projects = list(db.scalars(select(Project)).all())

    backgrounds_set = set()
    logos_set = set()
    flags_set = set()

    for project in projects:
        if project.background_asset_key:
            backgrounds_set.add(project.background_asset_key)
        if project.logo_asset_key:
            logos_set.add(project.logo_asset_key)
        if project.flag_asset_key:
            flags_set.add(project.flag_asset_key)

    ttl = get_settings().signed_url_ttl_seconds

    backgrounds = [
        AssetOption(key=key, url=url)
        for key in sorted(backgrounds_set)
        if (url := _safe_signed_url(storage, key, ttl)) is not None
    ]
    logos = [
        AssetOption(key=key, url=url)
        for key in sorted(logos_set)
        if (url := _safe_signed_url(storage, key, ttl)) is not None
    ]
    flags = [
        AssetOption(key=key, url=url)
        for key in sorted(flags_set)
        if (url := _safe_signed_url(storage, key, ttl)) is not None
    ]

    return ProjectAssetsResponse(
        backgrounds=backgrounds,
        logos=logos,
        flags=flags,
    )


@router.get("/generated-images", response_model=list[GeneratedImageResponse])
def list_generated_images(
    _: dict[str, str] = Depends(require_admin),
    db: Session = Depends(get_db),
    storage: DevStorage | PrivateStorage = Depends(get_storage),
) -> list[GeneratedImageResponse]:
    ttl = get_settings().signed_url_ttl_seconds
    responses: list[GeneratedImageResponse] = []
    projects = list(db.scalars(select(Project).order_by(Project.created_at.desc())))
    for project in projects:
        items = list(
            db.scalars(
                select(GenerationItem)
                .where(GenerationItem.project_id == project.id)
                .order_by(GenerationItem.created_at)
            )
        )
        for index, item in enumerate(items, start=1):
            if item.base_composite_asset_key is None:
                continue
            responses.append(
                GeneratedImageResponse(
                    id=item.id,
                    project_id=project.id,
                    project_name=project.name,
                    name=f"{project.name} - Product {index}",
                    status=item.status,
                    item_index=index,
                    attempt_count=item.attempt_count,
                    created_at=item.created_at,
                    preview_url=_safe_signed_url(
                        storage, item.base_composite_asset_key, ttl
                    ),
                    source_product_asset_key=item.source_product_asset_key,
                )
            )
    return responses


@router.post("/source-uploads", response_model=StagedSourceUploadResponse)
async def upload_source_files(
    project_name: str = Form(min_length=1, max_length=120),
    asset_type: str = Form(),
    files: list[UploadFile] = File(),
    _: dict[str, str] = Depends(require_admin),
    storage: DevStorage | PrivateStorage = Depends(get_storage),
) -> StagedSourceUploadResponse:
    if asset_type not in STAGED_ASSET_TYPES:
        raise HTTPException(status_code=422, detail="Unsupported upload asset type")
    if not files:
        raise HTTPException(status_code=422, detail="Select at least one image")

    prefix = f"sources/staged/{_staged_prefix(project_name)}-{uuid4()}/{asset_type}"
    uploads: list[StagedSourceUpload] = []
    ttl = get_settings().signed_url_ttl_seconds
    for index, upload in enumerate(files, start=1):
        source = await _source_file(upload)
        key = f"{prefix}/{index}-{uuid4()}.png"
        storage.upload(
            key,
            normalize_png(source.content, source.content_type, source.filename),
            "image/png",
        )
        uploads.append(
            StagedSourceUpload(
                asset_type=asset_type,
                filename=source.filename,
                storage_key=key,
                signed_url=storage.signed_url(key, ttl),
            )
        )
    return StagedSourceUploadResponse(uploads=uploads)


@router.get("/{project_id}", response_model=ProjectResponse)
def get_project(
    project_id: UUID,
    _: dict[str, str] = Depends(require_admin),
    db: Session = Depends(get_db),
    storage: DevStorage | PrivateStorage = Depends(get_storage),
) -> ProjectResponse:
    project = db.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return project_response(db, storage, project)


@router.post("/{project_id}/upload-background", response_model=SupabaseUploadResponse)
def upload_background_to_supabase(
    project_id: UUID,
    _: dict[str, str] = Depends(require_admin),
    db: Session = Depends(get_db),
    storage: DevStorage | PrivateStorage = Depends(get_storage),
    supabase_storage: PrivateStorage = Depends(get_supabase_storage),
) -> SupabaseUploadResponse:
    project = db.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    payload = storage.download(project.background_asset_key)
    key = f"supabase-sync/projects/{project.id}/background.png"
    supabase_storage.upload(key, payload, "image/png")
    return SupabaseUploadResponse(
        asset_type="background",
        source_key=project.background_asset_key,
        supabase_key=key,
    )


@router.post("", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
async def create_project(
    name: str = Form(min_length=1, max_length=120),
    mode: str = Form(),
    optional_instruction: str | None = Form(default=None, max_length=450),
    background: UploadFile | None = File(default=None),
    logo: UploadFile | None = File(default=None),
    flag: UploadFile | None = File(default=None),
    products: list[UploadFile] | None = File(default=None),
    background_asset_key: str | None = Form(default=None),
    logo_asset_key: str | None = Form(default=None),
    flag_asset_key: str | None = Form(default=None),
    product_asset_keys: list[str] | None = Form(default=None),
    admin: dict[str, str] = Depends(require_admin),
    db: Session = Depends(get_db),
    storage: DevStorage | PrivateStorage = Depends(get_storage),
    enqueue: Callable[[str], None] = Depends(get_enqueue),
) -> ProjectResponse:
    try:
        staged_keys = product_asset_keys or []
        active_storage = storage
        project = create_project_records(
            db,
            active_storage,
            enqueue,
            UUID(admin["sub"]),
            ProjectRequest(name, mode, optional_instruction),
            await _source_file(background) if background else None,
            await _source_file(logo) if logo else None,
            await _source_file(flag) if flag else None,
            [await _source_file(product) for product in products or []],
            background_asset_key=background_asset_key,
            logo_asset_key=logo_asset_key,
            flag_asset_key=flag_asset_key,
            product_asset_keys=staged_keys,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    db.refresh(project)
    return project_response(db, active_storage, project)
