"""
Ally Vision v2 — DashScope multimodal client.

Sends camera frame + text prompt to qwen3.6-plus
via the native DashScope multimodal HTTP endpoint.

Image size limit: base64 string must be <= 10MB.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

import httpx

logger = logging.getLogger("ally-multimodal-client")

_MAX_B64_BYTES = 10 * 1024 * 1024  # 10MB


@dataclass
class VisionRequest:
    image_jpeg_b64: str
    prompt: str
    model: str = ""  # set at runtime from settings
    max_tokens: int = 1024


@dataclass
class VisionResponse:
    text: str
    error: Optional[str] = None

    @property
    def success(self) -> bool:
        return self.error is None and bool(self.text)


class MultimodalClient:
    """
    Sends image + text to DashScope vision model.
    Uses the native DashScope multimodal generation endpoint.
    Falls back with VisionResponse.error on any failure.
    """

    def __init__(
        self,
        api_key: str,
        model: str,
        base_url: str,
    ) -> None:
        self._api_key = api_key
        self._model = model
        self._base_url = base_url.rstrip("/")

    @classmethod
    def from_settings(cls) -> "MultimodalClient":
        from shared.config.settings import (
            DASHSCOPE_HTTP_BASE,
            QWEN_VISION_MODEL,
            get_api_key,
        )

        return cls(
            api_key=get_api_key(),
            model=QWEN_VISION_MODEL,
            base_url=DASHSCOPE_HTTP_BASE,
        )

    async def analyze(self, request: VisionRequest) -> VisionResponse:
        """
        Analyze image with text prompt.
        Returns VisionResponse — never raises.
        """
        if not request.image_jpeg_b64:
            return VisionResponse(
                text="",
                error="No image provided for analysis.",
            )

        # Check base64 size before sending
        b64_size = len(request.image_jpeg_b64.encode("utf-8"))
        if b64_size > _MAX_B64_BYTES:
            return VisionResponse(
                text="",
                error=f"Image base64 too large: {b64_size} bytes > 10MB limit.",
            )

        model = request.model or self._model
        url = f"{self._base_url}/services/aigc/multimodal-generation/generation"

        payload = {
            "model": model,
            "input": {
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {
                                "image": f"data:image/jpeg;base64,{request.image_jpeg_b64}"
                            },
                            {"text": request.prompt},
                        ],
                    }
                ]
            },
        }

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(
                    url,
                    headers={
                        "Authorization": f"Bearer {self._api_key}",
                        "Content-Type": "application/json",
                    },
                    json=payload,
                )
                resp.raise_for_status()
                data = resp.json()
                text = data["output"]["choices"][0]["message"]["content"][0][
                    "text"
                ].strip()
                logger.info(
                    "Vision analysis complete: %d chars, model=%s",
                    len(text),
                    model,
                )
                return VisionResponse(text=text)

        except httpx.HTTPStatusError as exc:
            body = ""
            try:
                body = exc.response.text[:500]
            except Exception:
                pass
            error_msg = (
                f"HTTP {exc.response.status_code} from vision API. "
                f"Model={model}. Body: {body}"
            )
            logger.error("MultimodalClient HTTP error: %s", error_msg)
            return VisionResponse(text="", error=error_msg)

        except Exception as exc:
            logger.error("MultimodalClient error: %s", exc)
            return VisionResponse(text="", error=str(exc))
