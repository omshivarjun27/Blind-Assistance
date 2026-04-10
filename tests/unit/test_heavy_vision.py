"""Tests for Plan 06: MultimodalClient and vision core. No real API calls."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


def _make_httpx_response(text: str, status: int = 200):
    resp = MagicMock()
    resp.status_code = status
    resp.raise_for_status = MagicMock()
    resp.json.return_value = {
        "output": {
            "choices": [
                {
                    "message": {
                        "content": [
                            {
                                "text": text,
                            }
                        ]
                    }
                }
            ]
        }
    }
    return resp


@pytest.mark.asyncio
async def test_multimodal_client_analyze_success():
    from apps.backend.services.dashscope.multimodal_client import (
        MultimodalClient,
        VisionRequest,
    )

    client = MultimodalClient(
        api_key="test",
        model="qwen3.6-plus",
        base_url="https://dashscope-intl.aliyuncs.com/api/v1",
    )
    with patch("httpx.AsyncClient") as mock_cls:
        mock_http = MagicMock()
        mock_http.post = AsyncMock(return_value=_make_httpx_response("A red table"))
        mock_cls.return_value = mock_http
        req = VisionRequest(image_jpeg_b64="abc123", prompt="describe")
        result = await client.analyze(req)
    assert result.text == "A red table"
    assert result.success is True
    assert result.error is None


@pytest.mark.asyncio
async def test_multimodal_client_analyze_on_error():
    from apps.backend.services.dashscope.multimodal_client import (
        MultimodalClient,
        VisionRequest,
    )

    client = MultimodalClient(
        api_key="test",
        model="qwen3.6-plus",
        base_url="https://dashscope-intl.aliyuncs.com/api/v1",
    )
    with patch("httpx.AsyncClient") as mock_cls:
        mock_http = MagicMock()
        mock_http.post = AsyncMock(side_effect=Exception("network error"))
        mock_cls.return_value = mock_http
        req = VisionRequest(image_jpeg_b64="abc123", prompt="describe")
        result = await client.analyze(req)
    assert result.success is False
    assert result.error is not None


@pytest.mark.asyncio
async def test_multimodal_client_empty_image_returns_error():
    from apps.backend.services.dashscope.multimodal_client import (
        MultimodalClient,
        VisionRequest,
    )

    client = MultimodalClient(
        api_key="test",
        model="qwen3.6-plus",
        base_url="https://dashscope-intl.aliyuncs.com/api/v1",
    )
    req = VisionRequest(image_jpeg_b64="", prompt="describe")
    result = await client.analyze(req)
    assert result.success is False
    assert result.error is not None


@pytest.mark.asyncio
async def test_multimodal_client_image_in_request_body():
    from apps.backend.services.dashscope.multimodal_client import (
        MultimodalClient,
        VisionRequest,
    )

    client = MultimodalClient(
        api_key="test",
        model="qwen3.6-plus",
        base_url="https://dashscope-intl.aliyuncs.com/api/v1",
    )
    captured_body = {}
    captured_url = {"value": ""}

    async def capture_post(url, headers=None, json=None):
        captured_url["value"] = url
        captured_body.update(json or {})
        return _make_httpx_response("ok")

    with patch("httpx.AsyncClient") as mock_cls:
        mock_http = MagicMock()
        mock_http.post = AsyncMock(side_effect=capture_post)
        mock_cls.return_value = mock_http
        req = VisionRequest(image_jpeg_b64="TESTB64", prompt="what is this")
        await client.analyze(req)
    assert captured_url["value"].endswith(
        "/services/aigc/multimodal-generation/generation"
    )
    content = captured_body["input"]["messages"][0]["content"]
    image_part = next((p for p in content if "image" in p), None)
    text_part = next((p for p in content if "text" in p), None)
    assert image_part is not None
    assert text_part is not None
    assert image_part["image"].startswith("data:image/jpeg;base64,")
    assert "TESTB64" in image_part["image"]
    assert text_part["text"] == "what is this"


@pytest.mark.asyncio
async def test_read_scene_returns_description():
    from apps.backend.services.dashscope.multimodal_client import VisionResponse
    from core.vision.live_scene_reader import read_scene

    mock_client = MagicMock()
    mock_client.analyze = AsyncMock(
        return_value=VisionResponse(text="A table with a laptop")
    )
    result = await read_scene("abc123", mock_client)
    assert result == "A table with a laptop"


@pytest.mark.asyncio
async def test_read_text_from_image_returns_text():
    from apps.backend.services.dashscope.multimodal_client import VisionResponse
    from core.vision.page_reader import read_text_from_image

    mock_client = MagicMock()
    mock_client.analyze = AsyncMock(return_value=VisionResponse(text="STOP"))
    result = await read_text_from_image("abc123", mock_client)
    assert result == "STOP"


@pytest.mark.asyncio
async def test_summarize_page_includes_page_number():
    from apps.backend.services.dashscope.multimodal_client import (
        VisionRequest,
        VisionResponse,
    )
    from core.vision.page_reader import summarize_page

    captured_req = {}

    async def capture_analyze(req: VisionRequest) -> VisionResponse:
        captured_req["prompt"] = req.prompt
        return VisionResponse(text="Summary of page 2")

    mock_client = MagicMock()
    mock_client.analyze = capture_analyze
    await summarize_page("abc123", mock_client, page_number=2)
    assert "page 2" in captured_req["prompt"].lower() or "2" in captured_req["prompt"]


@pytest.mark.asyncio
async def test_framing_judge_yes_response():
    from apps.backend.services.dashscope.multimodal_client import VisionResponse
    from core.vision.framing_judge import get_framing_guidance

    mock_client = MagicMock()
    mock_client.analyze = AsyncMock(
        return_value=VisionResponse(text="YES the image is clear")
    )
    ok, msg = await get_framing_guidance("abc123", mock_client)
    assert ok is True
    assert msg == ""


@pytest.mark.asyncio
async def test_framing_judge_no_response():
    from apps.backend.services.dashscope.multimodal_client import VisionResponse
    from core.vision.framing_judge import get_framing_guidance

    mock_client = MagicMock()
    mock_client.analyze = AsyncMock(
        return_value=VisionResponse(text="NO - The image is too blurry")
    )
    ok, msg = await get_framing_guidance("abc123", mock_client)
    assert ok is False
    assert "blurry" in msg.lower() or msg != ""
