import pytest

from app.services.projects import aggregate_project_status, validate_product_count


def test_status_is_partial_when_a_batch_contains_success_and_failure() -> None:
    assert aggregate_project_status(["generated", "failed"]) == "partially_failed"


def test_single_project_requires_one_product() -> None:
    with pytest.raises(ValueError, match="one product"):
        validate_product_count("single", 2)


def test_batch_accepts_multiple_products() -> None:
    validate_product_count("batch", 3)
