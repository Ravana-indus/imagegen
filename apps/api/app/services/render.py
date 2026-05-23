from dataclasses import dataclass
from io import BytesIO

from PIL import Image


@dataclass(frozen=True)
class Layer:
    x: float
    y: float
    width: float
    height: float
    visible: bool


def render_final_png(
    base_bytes: bytes,
    logo_bytes: bytes,
    flag_bytes: bytes,
    logo: Layer,
    flag: Layer,
) -> bytes:
    canvas = Image.open(BytesIO(base_bytes)).convert("RGBA")
    for content, layer in ((logo_bytes, logo), (flag_bytes, flag)):
        if not layer.visible:
            continue
        overlay = Image.open(BytesIO(content)).convert("RGBA")
        size = (
            max(1, round(canvas.width * layer.width)),
            max(1, round(canvas.height * layer.height)),
        )
        overlay = overlay.resize(size, Image.Resampling.LANCZOS)
        position = (round(canvas.width * layer.x), round(canvas.height * layer.y))
        canvas.alpha_composite(overlay, position)
    output = BytesIO()
    canvas.save(output, "PNG")
    return output.getvalue()
