from io import BytesIO

from PIL import Image, UnidentifiedImageError

MAX_INPUT_BYTES = 10 * 1024 * 1024
MIN_DIMENSION = 384
MAX_DIMENSION = 3072
ALLOWED_MIME_TYPES = {"image/png", "image/jpeg", "image/webp"}


def validate_raster_upload(payload: bytes, content_type: str) -> tuple[int, int]:
    if content_type not in ALLOWED_MIME_TYPES or len(payload) > MAX_INPUT_BYTES:
        raise ValueError("Unsupported image upload")
    try:
        with Image.open(BytesIO(payload)) as image:
            image.verify()
        with Image.open(BytesIO(payload)) as image:
            width, height = image.size
    except (UnidentifiedImageError, OSError) as exc:
        raise ValueError("Invalid image") from exc
    return width, height


def normalize_png(payload: bytes, content_type: str, label: str = "image") -> bytes:
    width, height = validate_raster_upload(payload, content_type)
    if not (
        MIN_DIMENSION <= width <= MAX_DIMENSION
        and MIN_DIMENSION <= height <= MAX_DIMENSION
    ):
        raise ValueError(
            f"{label} dimensions {width}×{height} "
            f"are outside the allowed range of "
            f"{MIN_DIMENSION}–{MAX_DIMENSION} pixels"
        )
    with Image.open(BytesIO(payload)) as image:
        output = BytesIO()
        image.convert("RGBA").save(output, "PNG")
    return output.getvalue()
