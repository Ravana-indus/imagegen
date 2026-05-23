from io import BytesIO

from PIL import Image
import pytest

from app.services.assets import normalized_png, validate_raster_upload


def image_bytes(width: int = 384, height: int = 384, format_name: str = "PNG") -> bytes:
    output = BytesIO()
    Image.new("RGBA", (width, height), (20, 40, 60, 255)).save(
        output, format=format_name
    )
    return output.getvalue()


def test_valid_png_returns_dimensions_and_normalizes_to_png() -> None:
    payload = image_bytes()

    assert validate_raster_upload(payload, "image/png") == (384, 384)
    assert normalized_png(payload, "image/png").startswith(b"\x89PNG")


def test_image_below_qwen_quality_gate_is_rejected() -> None:
    with pytest.raises(ValueError, match="dimensions"):
        validate_raster_upload(image_bytes(200, 200), "image/png")


def test_non_image_payload_is_rejected() -> None:
    with pytest.raises(ValueError, match="Invalid image"):
        validate_raster_upload(b"not-an-image", "image/png")
