"""Tests for Plan 05: IntentClassifier. No real API calls."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


def _mock_response(label: str):
    """Build a mock httpx response returning label."""
    resp = MagicMock()
    resp.raise_for_status = MagicMock()
    resp.json.return_value = {"choices": [{"message": {"content": label}}]}
    return resp


@pytest.mark.asyncio
async def test_classify_returns_scene_describe():
    from core.orchestrator.intent_classifier import (
        IntentCategory,
        IntentClassifier,
    )

    clf = IntentClassifier(api_key="test-key")
    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(return_value=_mock_response("SCENE_DESCRIBE"))
        result = await clf.classify("what is in front of me")
    assert result.intent == IntentCategory.SCENE_DESCRIBE
    assert result.confidence == "high"
    assert result.error is None


@pytest.mark.asyncio
async def test_classify_returns_read_text():
    from core.orchestrator.intent_classifier import (
        IntentCategory,
        IntentClassifier,
    )

    clf = IntentClassifier(api_key="test-key")
    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(return_value=_mock_response("READ_TEXT"))
        result = await clf.classify("read this label")
    assert result.intent == IntentCategory.READ_TEXT
    assert result.confidence == "high"


@pytest.mark.asyncio
async def test_classify_returns_translate():
    from core.orchestrator.intent_classifier import (
        IntentCategory,
        IntentClassifier,
    )

    clf = IntentClassifier(api_key="test-key")
    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(return_value=_mock_response("TRANSLATE"))
        result = await clf.classify("translate this to Hindi")
    assert result.intent == IntentCategory.TRANSLATE
    assert result.confidence == "high"


@pytest.mark.asyncio
async def test_classify_returns_general_chat_on_empty():
    from core.orchestrator.intent_classifier import (
        IntentCategory,
        IntentClassifier,
    )

    clf = IntentClassifier(api_key="test-key")
    # No patch needed — empty transcript must not call API
    result = await clf.classify("")
    assert result.intent == IntentCategory.GENERAL_CHAT
    assert result.confidence == "high"
    assert result.error is None


@pytest.mark.asyncio
async def test_classify_returns_general_chat_on_whitespace():
    from core.orchestrator.intent_classifier import (
        IntentCategory,
        IntentClassifier,
    )

    clf = IntentClassifier(api_key="test-key")
    result = await clf.classify("   ")
    assert result.intent == IntentCategory.GENERAL_CHAT
    assert result.confidence == "high"


@pytest.mark.asyncio
async def test_classify_returns_general_chat_on_unknown_label():
    from core.orchestrator.intent_classifier import (
        IntentCategory,
        IntentClassifier,
    )

    clf = IntentClassifier(api_key="test-key")
    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(return_value=_mock_response("TOTALLY_UNKNOWN"))
        result = await clf.classify("random request")
    assert result.intent == IntentCategory.GENERAL_CHAT
    assert result.confidence == "low"


@pytest.mark.asyncio
async def test_classify_returns_general_chat_on_api_error():
    from core.orchestrator.intent_classifier import (
        IntentCategory,
        IntentClassifier,
    )

    clf = IntentClassifier(api_key="test-key")
    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(side_effect=Exception("connection failed"))
        result = await clf.classify("what is in front")
    assert result.intent == IntentCategory.GENERAL_CHAT
    assert result.confidence == "low"
    assert result.error is not None


def test_from_settings_reads_api_key():
    from core.orchestrator.intent_classifier import IntentClassifier

    clf = IntentClassifier.from_settings()
    # conftest sets DASHSCOPE_API_KEY=test-key-for-unit-tests
    assert clf._api_key == "test-key-for-unit-tests"
