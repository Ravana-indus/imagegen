import httpx

from app.services.qwen import QwenImageEditor


def test_edit_sends_product_background_and_protected_prompt() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        body = request.read().decode()
        assert "Keep the product identity" in body
        assert "Do not add logos, flags" in body
        assert "Warm afternoon lighting" in body
        return httpx.Response(
            200,
            json={
                "output": {
                    "choices": [
                        {
                            "message": {
                                "content": [
                                    {"image": "https://result.example/base.png"}
                                ]
                            }
                        }
                    ]
                },
                "request_id": "request-123",
            },
        )

    editor = QwenImageEditor(
        "key",
        "https://dashscope.example/api/v1",
        "qwen-image-2.0-pro",
        httpx.Client(transport=httpx.MockTransport(handler)),
    )

    result = editor.edit(
        "data:image/png;base64,product",
        "data:image/png;base64,background",
        "Warm afternoon lighting",
    )

    assert result.image_url == "https://result.example/base.png"
    assert result.request_id == "request-123"
