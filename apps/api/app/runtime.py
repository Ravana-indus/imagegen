from typing import Any

from sqlalchemy.engine import make_url


def is_sqlite_database_url(database_url: str) -> bool:
    return make_url(database_url).get_backend_name() == "sqlite"


def _setting(settings: Any, name: str, default: Any = None) -> Any:
    return getattr(settings, name, default)


def _mode(settings: Any, name: str, default: str = "auto") -> str:
    return str(_setting(settings, name, default)).strip().lower()


def use_local_storage(settings: Any) -> bool:
    storage_backend = _mode(settings, "storage_backend")
    if storage_backend == "local":
        return True
    if storage_backend == "supabase":
        return False
    return is_sqlite_database_url(_setting(settings, "database_url", ""))


def use_inline_generation(settings: Any) -> bool:
    generation_execution = _mode(settings, "generation_execution")
    if generation_execution == "inline":
        return True
    if generation_execution == "queue":
        return False
    return is_sqlite_database_url(_setting(settings, "database_url", ""))


def use_dev_auth(settings: Any) -> bool:
    auth_mode = _mode(settings, "auth_mode", "session")
    if auth_mode == "dev":
        return True
    if auth_mode == "session":
        return False
    return is_sqlite_database_url(_setting(settings, "database_url", ""))
