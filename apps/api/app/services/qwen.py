from dataclasses import dataclass

import httpx

BASE_PROMPT = (
    "Keep the product identity, label, shape, and colors faithful to Image 1. "
    "Place that product naturally into the setting from Image 2. "
    "Harmonize lighting, reflections, contact shadows, and perspective for a "
    "premium product advertisement. Do not add logos, flags, badges, "
    "promotional text, or unrelated objects."
)


@dataclass(frozen=True)
class QwenResult:
    request_id: str
    image_url: str


class QwenImageEditor:
    def __init__(
        self,
        api_key: str,
        base_url: str,
        model: str,
        client: httpx.Client | None = None,
    ) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.client = client or httpx.Client(timeout=120)

    def edit(
        self,
        product_image: str,
        background_image: str,
        optional_instruction: str | None,
    ) -> QwenResult:
        prompt = BASE_PROMPT
        if optional_instruction:
            prompt = f"{prompt} Additional direction: {optional_instruction}"
        response = self.client.post(
            f"{self.base_url}/services/aigc/multimodal-generation/generation",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": self.model,
                "input": {
                    "messages": [
                        {
                            "role": "user",
                            "content": [
                                {"image": product_image},
                                {"image": background_image},
                                {"text": prompt},
                            ],
                        }
                    ]
                },
                "parameters": {"n": 1, "prompt_extend": True, "watermark": False},
            },
        )
        response.raise_for_status()
        payload = response.json()
        return QwenResult(
            request_id=payload["request_id"],
            image_url=payload["output"]["choices"][0]["message"]["content"][0][
                "image"
            ],
        )
