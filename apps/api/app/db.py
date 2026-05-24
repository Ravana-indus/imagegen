from collections.abc import Iterator
from functools import lru_cache
from pathlib import Path

from sqlalchemy import Engine, create_engine, inspect
from sqlalchemy.engine import make_url
from sqlalchemy import select
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import get_settings
from app.runtime import is_sqlite_database_url, use_dev_auth


class Base(DeclarativeBase):
    pass


@lru_cache
def get_engine() -> Engine:
    settings = get_settings()
    kwargs = {}
    if is_sqlite_database_url(settings.database_url):
        url = make_url(settings.database_url)
        if url.database and url.database != ":memory:":
            Path(url.database).expanduser().parent.mkdir(parents=True, exist_ok=True)
        kwargs["connect_args"] = {"check_same_thread": False}
    return create_engine(settings.database_url, pool_pre_ping=True, **kwargs)


def initialize_database() -> None:
    settings = get_settings()
    if not settings.initialize_database:
        return
    if not is_sqlite_database_url(settings.database_url):
        return

    from app.models import AdminUser  # Imported here so all model tables are registered.

    engine = get_engine()
    if _sqlite_schema_has_drift(engine):
        Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    if not use_dev_auth(settings):
        return

    with Session(engine) as session:
        existing = session.scalar(
            select(AdminUser).where(AdminUser.id == settings.dev_admin_id)
        )
        if existing is None:
            session.add(
                AdminUser(
                    id=settings.dev_admin_id,
                    email=settings.dev_admin_email,
                    password_hash="dev-auth-bypass",
                )
            )
            session.commit()


def _sqlite_schema_has_drift(engine: Engine) -> bool:
    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())
    for table_name, table in Base.metadata.tables.items():
        if table_name not in existing_tables:
            continue
        model_columns = {column.name for column in table.columns}
        existing_columns = inspector.get_columns(table_name)
        existing_names = {column["name"] for column in existing_columns}
        if not model_columns.issubset(existing_names):
            return True
        for column in existing_columns:
            if column["name"] in model_columns:
                continue
            if column.get("primary_key"):
                continue
            if not column.get("nullable", True) and column.get("default") is None:
                return True
    return False


def get_db() -> Iterator[Session]:
    factory = sessionmaker(get_engine(), expire_on_commit=False)
    with factory() as session:
        yield session
