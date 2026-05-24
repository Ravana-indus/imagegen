import os
from pathlib import Path

from supabase import Client, create_client

from app.config import get_settings
from app.runtime import use_local_storage

DEV_STORAGE_ROOT = Path(__file__).resolve().parents[2] / "dev-storage"


class DevStorage:
    def __init__(self) -> None:
        self.root = DEV_STORAGE_ROOT
        self.root.mkdir(parents=True, exist_ok=True)

    def upload(self, key: str, payload: bytes, content_type: str) -> str:
        target = self.root / key
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(payload)
        return key

    def download(self, key: str) -> bytes:
        return (self.root / key).read_bytes()

    def signed_url(self, key: str, expires_in: int) -> str:
        return f"/storage/{key}"


class PrivateStorage:
    def __init__(self, client: Client | None = None, bucket: str | None = None) -> None:
        settings = get_settings()
        if client is None:
            if not settings.supabase_url or not settings.supabase_secret_key:
                raise RuntimeError("Supabase server storage credentials are not configured")
            client = create_client(settings.supabase_url, settings.supabase_secret_key)
        self.client = client
        self.bucket = bucket or settings.storage_bucket

    def upload(self, key: str, payload: bytes, content_type: str) -> str:
        self.client.storage.from_(self.bucket).upload(
            key,
            payload,
            file_options={"content-type": content_type, "upsert": "true"},
        )
        return key

    def download(self, key: str) -> bytes:
        return self.client.storage.from_(self.bucket).download(key)

    def signed_url(self, key: str, expires_in: int) -> str:
        response = self.client.storage.from_(self.bucket).create_signed_url(
            key, expires_in
        )
        return response["signedURL"]


def create_storage() -> DevStorage | PrivateStorage:
    if use_local_storage(get_settings()):
        return DevStorage()
    try:
        return PrivateStorage()
    except RuntimeError:
        return DevStorage()
