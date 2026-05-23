from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "sqlite:///./product_creative.db"
    supabase_url: str = ""
    supabase_secret_key: str = ""
    storage_bucket: str = "editimage"
    session_secret: str = "replace-in-production-with-a-long-secret"
    session_cookie_secure: bool = True
    redis_url: str = "redis://localhost:6379/0"
    dashscope_api_key: str = ""
    dashscope_base_url: str = "https://dashscope-intl.aliyuncs.com/api/v1"
    dashscope_model: str = "qwen-image-2.0-pro"
    signed_url_ttl_seconds: int = 900


@lru_cache
def get_settings() -> Settings:
    return Settings()
