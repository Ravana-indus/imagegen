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
        box_width = max(1, round(canvas.width * layer.width))
        box_height = max(1, round(canvas.height * layer.height))
        
        orig_width, orig_height = overlay.size
        overlay_aspect = orig_width / orig_height
        box_aspect = box_width / box_height
        
        if overlay_aspect > box_aspect:
            new_width = box_width
            new_height = max(1, round(new_width / overlay_aspect))
        else:
            new_height = box_height
            new_width = max(1, round(new_height * overlay_aspect))
            
        overlay = overlay.resize((new_width, new_height), Image.Resampling.LANCZOS)
        
        offset_x = (box_width - new_width) / 2
        offset_y = (box_height - new_height) / 2
        
        position = (
            round(canvas.width * layer.x + offset_x),
            round(canvas.height * layer.y + offset_y),
        )
        canvas.alpha_composite(overlay, position)
    output = BytesIO()
    canvas.save(output, "PNG")
    return output.getvalue()
