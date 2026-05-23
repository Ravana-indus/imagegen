from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


def utcnow() -> datetime:
    return datetime.now(UTC)


class AdminUser(Base):
    __tablename__ = "admin_users"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    email: Mapped[str] = mapped_column(String(320), nullable=False, unique=True)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    mode: Mapped[str] = mapped_column(String(12), nullable=False)
    status: Mapped[str] = mapped_column(String(24), default="queued")
    background_asset_key: Mapped[str] = mapped_column(Text, nullable=False)
    logo_asset_key: Mapped[str] = mapped_column(Text, nullable=False)
    country_code: Mapped[str] = mapped_column(String(2), nullable=False)
    flag_asset_key: Mapped[str] = mapped_column(Text, nullable=False)
    optional_instruction: Mapped[str | None] = mapped_column(Text)
    prompt_version: Mapped[str] = mapped_column(
        String(40), default="product-composite-v1"
    )
    created_by: Mapped[UUID] = mapped_column(ForeignKey("admin_users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)


class GenerationItem(Base):
    __tablename__ = "generation_items"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    project_id: Mapped[UUID] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"))
    source_product_asset_key: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(24), default="queued")
    provider_model: Mapped[str] = mapped_column(
        String(80), default="qwen-image-2.0-pro"
    )
    provider_request_id: Mapped[str | None] = mapped_column(Text)
    provider_error_code: Mapped[str | None] = mapped_column(Text)
    provider_error_message: Mapped[str | None] = mapped_column(Text)
    attempt_count: Mapped[int] = mapped_column(Integer, default=0)
    base_composite_asset_key: Mapped[str | None] = mapped_column(Text)
    thumbnail_asset_key: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)


class OverlayLayout(Base):
    __tablename__ = "overlay_layouts"

    generation_item_id: Mapped[UUID] = mapped_column(
        ForeignKey("generation_items.id", ondelete="CASCADE"), primary_key=True
    )
    revision: Mapped[int] = mapped_column(Integer, default=1)
    logo_x: Mapped[Decimal] = mapped_column(Numeric(6, 5), default=Decimal("0.05"))
    logo_y: Mapped[Decimal] = mapped_column(Numeric(6, 5), default=Decimal("0.05"))
    logo_width: Mapped[Decimal] = mapped_column(
        Numeric(6, 5), default=Decimal("0.22")
    )
    logo_height: Mapped[Decimal] = mapped_column(
        Numeric(6, 5), default=Decimal("0.12")
    )
    logo_visible: Mapped[bool] = mapped_column(Boolean, default=True)
    flag_x: Mapped[Decimal] = mapped_column(Numeric(6, 5), default=Decimal("0.82"))
    flag_y: Mapped[Decimal] = mapped_column(Numeric(6, 5), default=Decimal("0.05"))
    flag_width: Mapped[Decimal] = mapped_column(
        Numeric(6, 5), default=Decimal("0.13")
    )
    flag_height: Mapped[Decimal] = mapped_column(
        Numeric(6, 5), default=Decimal("0.09")
    )
    flag_visible: Mapped[bool] = mapped_column(Boolean, default=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)


class ExportAsset(Base):
    __tablename__ = "export_assets"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    project_id: Mapped[UUID] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"))
    generation_item_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("generation_items.id", ondelete="CASCADE")
    )
    asset_type: Mapped[str] = mapped_column(String(20), nullable=False)
    storage_key: Mapped[str] = mapped_column(Text, nullable=False)
    layout_revision: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
