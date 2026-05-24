from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class LoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=1, max_length=256)


class AdminResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    email: str


class LayoutUpdate(BaseModel):
    logo_x: float | None = Field(default=None, ge=0, le=1)
    logo_y: float | None = Field(default=None, ge=0, le=1)
    logo_width: float | None = Field(default=None, gt=0, le=1)
    logo_height: float | None = Field(default=None, gt=0, le=1)
    logo_visible: bool | None = None
    flag_x: float | None = Field(default=None, ge=0, le=1)
    flag_y: float | None = Field(default=None, ge=0, le=1)
    flag_width: float | None = Field(default=None, gt=0, le=1)
    flag_height: float | None = Field(default=None, gt=0, le=1)
    flag_visible: bool | None = None


class LayoutResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    revision: int
    logo_x: float
    logo_y: float
    logo_width: float
    logo_height: float
    logo_visible: bool
    flag_x: float
    flag_y: float
    flag_width: float
    flag_height: float
    flag_visible: bool


class ItemResponse(BaseModel):
    id: UUID
    status: str
    attempt_count: int
    preview_url: str | None = None
    error_message: str | None = None
    layout: LayoutResponse


class ProjectSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    mode: str
    status: str
    created_at: datetime


class ProjectResponse(ProjectSummary):
    background_url: str
    logo_url: str
    flag_url: str
    items: list[ItemResponse]


class ExportResponse(BaseModel):
    id: UUID
    asset_type: str
    download_url: str


class RetryResponse(BaseModel):
    id: UUID
    status: str


class SupabaseUploadResponse(BaseModel):
    asset_type: str
    source_key: str
    supabase_key: str


class StagedSourceUpload(BaseModel):
    asset_type: str
    filename: str
    storage_key: str
    signed_url: str


class StagedSourceUploadResponse(BaseModel):
    uploads: list[StagedSourceUpload]


class AssetOption(BaseModel):
    key: str
    url: str


class ProjectAssetsResponse(BaseModel):
    backgrounds: list[AssetOption]
    logos: list[AssetOption]
    flags: list[AssetOption]
