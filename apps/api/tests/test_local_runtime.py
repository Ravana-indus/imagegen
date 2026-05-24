from pathlib import Path

from sqlalchemy import create_engine, inspect, select
from sqlalchemy.orm import Session

import app.config as config
import app.db as db_module
import app.jobs as jobs
from app.db import Base
from app.models import AdminUser
from app.security import require_admin
from app.storage import DevStorage, create_storage


def reset_settings() -> None:
    config.get_settings.cache_clear()
    db_module.get_engine.cache_clear()


def test_sqlite_database_schema_is_created_for_local_runtime(
    tmp_path: Path, monkeypatch
) -> None:
    database_path = tmp_path / "local.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{database_path}")
    reset_settings()

    try:
        db_module.initialize_database()

        table_names = inspect(db_module.get_engine()).get_table_names()
        assert sorted(table_names) == sorted(Base.metadata.tables)
    finally:
        reset_settings()


def test_local_runtime_seeds_dev_admin_when_auth_is_auto(
    tmp_path: Path, monkeypatch
) -> None:
    database_path = tmp_path / "local.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{database_path}")
    monkeypatch.setenv("AUTH_MODE", "auto")
    reset_settings()

    try:
        db_module.initialize_database()

        with Session(db_module.get_engine()) as session:
            admin = session.scalar(select(AdminUser))
        assert admin is not None
        assert require_admin() == {"sub": str(admin.id), "email": admin.email}
    finally:
        reset_settings()


def test_sqlite_schema_drift_is_reset_for_local_runtime(
    tmp_path: Path, monkeypatch
) -> None:
    database_path = tmp_path / "local.db"
    stale_engine = create_engine(f"sqlite:///{database_path}")
    with stale_engine.begin() as connection:
        connection.exec_driver_sql(
            "CREATE TABLE projects ("
            "id CHAR(32) PRIMARY KEY, "
            "country_code VARCHAR(2) NOT NULL"
            ")"
        )

    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{database_path}")
    reset_settings()

    try:
        db_module.initialize_database()

        columns = {
            column["name"]
            for column in inspect(db_module.get_engine()).get_columns("projects")
        }
        assert "country_code" not in columns
        assert "background_asset_key" in columns
    finally:
        reset_settings()


def test_auto_storage_uses_dev_storage_for_sqlite_even_with_supabase_credentials(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setattr("app.storage.DEV_STORAGE_ROOT", tmp_path)
    monkeypatch.setattr(
        "app.storage.get_settings",
        lambda: type(
            "Settings",
            (),
            {
                "database_url": "sqlite:///local.db",
                "storage_backend": "auto",
                "supabase_url": "https://example.supabase.co",
                "supabase_secret_key": "secret",
                "storage_bucket": "editimage",
            },
        )(),
    )

    storage = create_storage()

    assert isinstance(storage, DevStorage)


def test_auto_generation_dispatches_background_local_generation_for_sqlite(
    monkeypatch,
) -> None:
    calls: list[str] = []
    monkeypatch.setattr(
        "app.jobs.get_settings",
        lambda: type(
            "Settings",
            (),
            {
                "database_url": "sqlite:///local.db",
                "generation_execution": "auto",
            },
        )(),
    )
    monkeypatch.setattr(jobs, "enqueue_local_generation", calls.append)

    handler = jobs.resolve_generation_handler()
    handler("item-1")

    assert calls == ["item-1"]
