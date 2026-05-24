from contextlib import nullcontext

from app.jobs import wait_for_provider_slot
import app.jobs as jobs


class MemoryRedis:
    def __init__(self, value: bytes | None = None) -> None:
        self.value = value

    def lock(self, *args, **kwargs):
        return nullcontext()

    def get(self, key: str) -> bytes | None:
        return self.value

    def set(self, key: str, value: str, ex: int) -> None:
        self.value = value.encode()


def test_provider_slot_waits_until_the_configured_interval_has_elapsed() -> None:
    redis = MemoryRedis(b"100.0")
    times = iter([101.0, 131.0])
    delays: list[float] = []

    wait_for_provider_slot(
        redis,
        interval_seconds=31,
        clock=lambda: next(times),
        sleep=delays.append,
    )

    assert delays == [30.0]
    assert redis.value == b"131.0"


def test_inline_generation_uses_local_rate_limit_without_redis(monkeypatch) -> None:
    captured: dict[str, str] = {}
    monkeypatch.setattr(
        jobs,
        "run_generation_job",
        lambda item_id, rate_limit_backend="redis": captured.update(
            {"item_id": item_id, "rate_limit_backend": rate_limit_backend}
        ),
    )

    jobs.run_generation_inline("item-1")

    assert captured == {"item_id": "item-1", "rate_limit_backend": "local"}


def test_local_generation_enqueue_starts_background_thread(monkeypatch) -> None:
    started: list[tuple[object, tuple[str], bool]] = []

    class FakeThread:
        def __init__(self, target, args, daemon):
            started.append((target, args, daemon))

        def start(self) -> None:
            pass

    monkeypatch.setattr(jobs, "Thread", FakeThread)

    jobs.enqueue_local_generation("item-1")

    assert started == [(jobs.run_generation_inline, ("item-1",), True)]
