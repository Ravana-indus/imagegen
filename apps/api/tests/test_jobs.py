from contextlib import nullcontext

from app.jobs import wait_for_provider_slot


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
