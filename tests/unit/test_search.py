from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from core.search.search_manager import SearchManager


@pytest.mark.asyncio
async def test_search_returns_answer():
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = {
        "choices": [{"message": {"content": "The score is 245 for 3."}}]
    }

    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        manager = SearchManager("key", "https://base", "qwen-turbo")
        result = await manager.search("cricket score")

    assert result == "The score is 245 for 3."


@pytest.mark.asyncio
async def test_search_returns_fallback_on_http_error():
    request = httpx.Request("POST", "https://base/chat/completions")
    response = httpx.Response(500, request=request)

    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(
            side_effect=httpx.HTTPStatusError(
                "boom",
                request=request,
                response=response,
            )
        )
        mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        manager = SearchManager("key", "https://base", "qwen-turbo")
        result = await manager.search("cricket score")

    assert result == "I was unable to search for that right now."


@pytest.mark.asyncio
async def test_search_returns_fallback_on_timeout():
    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(side_effect=httpx.TimeoutException("timeout"))
        mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        manager = SearchManager("key", "https://base", "qwen-turbo")
        result = await manager.search("cricket score")

    assert result == "I was unable to search for that right now."


@pytest.mark.asyncio
async def test_search_sends_enable_search_flag():
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = {
        "choices": [{"message": {"content": "The score is 245 for 3."}}]
    }

    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        manager = SearchManager("key", "https://base", "qwen-turbo")
        await manager.search("test query")

    payload = mock_client.post.await_args.kwargs["json"]
    assert payload["enable_search"] is True
    assert payload["search_options"] == {"forced_search": True}
    assert "tools" not in payload


def test_search_from_settings_uses_correct_model():
    with patch("shared.config.settings.QWEN_TURBO_MODEL", "qwen-turbo"):
        manager = SearchManager.from_settings()

    assert manager.model == "qwen-turbo"
