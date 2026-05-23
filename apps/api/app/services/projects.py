def validate_product_count(mode: str, count: int) -> None:
    if mode == "single" and count != 1:
        raise ValueError("Single projects require one product image")
    if mode == "batch" and not 1 <= count <= 25:
        raise ValueError("Batch projects require between 1 and 25 product images")
    if mode not in {"single", "batch"}:
        raise ValueError("Unsupported project mode")


def aggregate_project_status(statuses: list[str]) -> str:
    if statuses and all(status in {"generated", "exported"} for status in statuses):
        return "completed"
    if statuses and all(status == "failed" for status in statuses):
        return "failed"
    if "failed" in statuses and any(
        status in {"generated", "exported"} for status in statuses
    ):
        return "partially_failed"
    if "processing" in statuses:
        return "processing"
    return "queued"
