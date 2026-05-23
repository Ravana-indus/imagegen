from collections.abc import Callable
from time import sleep as system_sleep
from time import time as wall_time
from typing import Any, ContextManager, Protocol

import httpx
from redis import Redis
from rq import Queue
from sqlalchemy.orm import sessionmaker

from app.config import get_settings
from app.db import get_engine
from app.services.qwen import QwenImageEditor
from app.services.worker_runtime import execute_generation
from app.storage import PrivateStorage

RATE_LIMIT_KEY = "dashscope:qwen-image:last-submission"
RATE_LIMIT_LOCK = "dashscope:qwen-image:submission-lock"


class RateLimitRedis(Protocol):
    def lock(
        self, name: str, timeout: int, blocking_timeout: int
    ) -> ContextManager[Any]: ...

    def get(self, key: str) -> bytes | str | None: ...

    def set(self, key: str, value: str, ex: int) -> Any: ...


def wait_for_provider_slot(
    redis: RateLimitRedis,
    interval_seconds: float,
    clock: Callable[[], float] = wall_time,
    sleep: Callable[[float], None] = system_sleep,
) -> None:
    if interval_seconds <= 0:
        return
    lock_timeout = max(60, int(interval_seconds * 2) + 1)
    while True:
        with redis.lock(
            RATE_LIMIT_LOCK,
            timeout=lock_timeout,
            blocking_timeout=lock_timeout,
        ):
            now = clock()
            last_submission = redis.get(RATE_LIMIT_KEY)
            last_time = float(last_submission) if last_submission else 0
            delay = last_time + interval_seconds - now
            if delay <= 0:
                redis.set(RATE_LIMIT_KEY, str(now), ex=lock_timeout)
                return
        sleep(delay)


def get_generation_queue() -> Queue:
    settings = get_settings()
    return Queue("image-generation", connection=Redis.from_url(settings.redis_url))


def enqueue_generation(item_id: str) -> None:
    get_generation_queue().enqueue(run_generation_job, item_id, job_timeout=1200)


def run_generation_job(item_id: str) -> None:
    settings = get_settings()
    wait_for_provider_slot(
        Redis.from_url(settings.redis_url), settings.dashscope_min_interval_seconds
    )
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
