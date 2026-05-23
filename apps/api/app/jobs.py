from collections.abc import Callable

import httpx
from redis import Redis
from rq import Queue
from sqlalchemy.orm import sessionmaker

from app.config import get_settings
from app.db import get_engine
from app.services.qwen import QwenImageEditor
from app.services.worker_runtime import execute_generation
from app.storage import PrivateStorage


def get_generation_queue() -> Queue:
    settings = get_settings()
    return Queue("image-generation", connection=Redis.from_url(settings.redis_url))


def enqueue_generation(item_id: str) -> None:
    get_generation_queue().enqueue(run_generation_job, item_id, job_timeout=300)


def run_generation_job(item_id: str) -> None:
    settings = get_settings()
    storage = PrivateStorage()
    editor = QwenImageEditor(
        api_key=settings.dashscope_api_key,
        base_url=settings.dashscope_base_url,
        model=settings.dashscope_model,
    )
    session_factory = sessionmaker(bind=get_engine(), expire_on_commit=False)

    def fetch_output(url: str) -> bytes:
        response = httpx.get(url, timeout=45)
        response.raise_for_status()
        return response.content

    execute_generation(item_id, session_factory, storage, editor, fetch_output)
