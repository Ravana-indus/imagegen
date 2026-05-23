from io import BytesIO

from PIL import Image

from app.services.render import Layer, render_final_png


def png(color: tuple[int, int, int, int], size: tuple[int, int]) -> bytes:
    output = BytesIO()
    Image.new("RGBA", size, color).save(output, "PNG")
    return output.getvalue()


def test_render_places_logo_and_flag_using_normalized_positions() -> None:
    result = render_final_png(
        png((255, 255, 255, 255), (100, 100)),
        png((255, 0, 0, 255), (20, 20)),
        png((0, 0, 255, 255), (20, 20)),
        Layer(0.1, 0.1, 0.2, 0.2, True),
        Layer(0.7, 0.1, 0.2, 0.2, True),
    )
    image = Image.open(BytesIO(result))

    assert image.getpixel((15, 15)) == (255, 0, 0, 255)
    assert image.getpixel((75, 15)) == (0, 0, 255, 255)
