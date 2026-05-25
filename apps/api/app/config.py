from functools import lru_cache
from pathlib import Path
from uuid import UUID

from pydantic_settings import BaseSettings, SettingsConfigDict

ENV_FILE = Path(__file__).resolve().parents[1] / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ENV_FILE, extra="ignore")

    database_url: str = "sqlite:///./product_creative.db"
    initialize_database: bool = True
    auth_mode: str = "dev"
    dev_admin_id: UUID = UUID("00000000-0000-4000-8000-000000000001")
    dev_admin_email: str = "local-dev@example.test"
    storage_backend: str = "auto"
    supabase_url: str = ""
    supabase_secret_key: str = ""
    storage_bucket: str = "editimage"
    session_secret: str = "replace-in-production-with-a-long-secret"
    session_cookie_secure: bool = True
    redis_url: str = "redis://localhost:6379/0"
    generation_execution: str = "auto"
    dashscope_api_key: str = ""
    dashscope_base_url: str = "https://dashscope-intl.aliyuncs.com/api/v1"
    dashscope_model: str = "qwen-image-2.0-pro"
    dashscope_min_interval_seconds: float = 31
    signed_url_ttl_seconds: int = 900


@lru_cache
def get_settings() -> Settings:
    return Settings()
