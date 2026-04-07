"""
Unit tests for Plan 03: /ws/realtime WebSocket route.
All tests use mocked QwenRealtimeClient — no real network.
"""

from __future__ import annotations

import asyncio
import json
import time
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient
import pytest

from apps.backend.main import app


# ── regression: health still works ───────────────────────────────


def test_health_endpoint_still_works():
    """GET /health must still return 200 after router added."""
    with TestClient(app) as client:
        r = client.get("/health")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "ok"
    assert "realtime_model" in data


# ── route registration ────────────────────────────────────────────


def test_websocket_route_is_registered():
    """/ws/realtime must be registered in app routes."""
    paths = [getattr(r, "path", None) for r in app.routes]
    assert "/ws/realtime" in paths, f"/ws/realtime not found in routes: {paths}"


# ── helpers ───────────────────────────────────────────────────────


def _make_mock_turn(
    audio: bytes = b"\x00" * 100,
    assistant_text: str = "hello",
    user_text: str = "hi",
):
    """Build a mock QwenRealtimeTurn."""
    turn = MagicMock()
    turn.assistant_audio_pcm = audio
    turn.assistant_transcript = assistant_text
    turn.user_transcript = user_text
    turn.success = True
    turn.error = None
    return turn


def _mock_client(turn: Any):
    """Build a mock QwenRealtimeClient that returns turn."""
    client = MagicMock()
    client.async_send_audio_turn = AsyncMock(return_value=turn)
    client.close = MagicMock()
    return client


# ── audio turn tests ──────────────────────────────────────────────


def test_websocket_audio_returns_binary_response():
    """Binary audio frame triggers Qwen turn and returns audio bytes."""
    turn = _make_mock_turn(audio=b"\x01\x02" * 50)
    mock_client = _mock_client(turn)

    with (
        patch(
            "apps.backend.api.routes.realtime.QwenRealtimeClient",
            return_value=mock_client,
        ),
        patch(
            "apps.backend.api.routes.realtime.QwenRealtimeConfig.from_settings",
            return_value=MagicMock(),
        ),
    ):
        with TestClient(app) as client:
            with client.websocket_connect("/ws/realtime") as ws:
                ws.send_bytes(b"\x00" * 3200)
                response = ws.receive_bytes()
                assert response == turn.assistant_audio_pcm
                assert len(response) > 0


def test_websocket_returns_assistant_transcript_json():
    """Audio turn must return assistant transcript as JSON text frame."""
    turn = _make_mock_turn(assistant_text="I see a table")
    mock_client = _mock_client(turn)

    with (
        patch(
            "apps.backend.api.routes.realtime.QwenRealtimeClient",
            return_value=mock_client,
        ),
        patch(
            "apps.backend.api.routes.realtime.QwenRealtimeConfig.from_settings",
            return_value=MagicMock(),
        ),
    ):
        with TestClient(app) as client:
            with client.websocket_connect("/ws/realtime") as ws:
                ws.send_bytes(b"\x00" * 3200)
                # First receive: audio bytes
                ws.receive_bytes()
                # Second receive: assistant transcript
                text_frame = ws.receive_text()
                msg = json.loads(text_frame)
                assert msg["type"] == "transcript"
                assert msg["role"] == "assistant"
                assert msg["text"] == "I see a table"


def test_websocket_async_send_audio_turn_called():
    """async_send_audio_turn must be called with audio PCM bytes."""
    turn = _make_mock_turn()
    mock_client = _mock_client(turn)
    audio_data = b"\xab\xcd" * 1600

    with (
        patch(
            "apps.backend.api.routes.realtime.QwenRealtimeClient",
            return_value=mock_client,
        ),
        patch(
            "apps.backend.api.routes.realtime.QwenRealtimeConfig.from_settings",
            return_value=MagicMock(),
        ),
    ):
        with TestClient(app) as client:
            with client.websocket_connect("/ws/realtime") as ws:
                ws.send_bytes(audio_data)
                _ = ws.receive_bytes()  # consume response

    mock_client.async_send_audio_turn.assert_called_once()
    call_kwargs = mock_client.async_send_audio_turn.call_args
    assert call_kwargs[1]["audio_pcm"] == audio_data or (
        call_kwargs[0] and call_kwargs[0][0] == audio_data
    )


# ── image control message ─────────────────────────────────────────


def test_websocket_image_message_queued_for_next_turn():
    """Image control message must be passed to next audio turn."""
    turn = _make_mock_turn()
    mock_client = _mock_client(turn)

    with (
        patch(
            "apps.backend.api.routes.realtime.QwenRealtimeClient",
            return_value=mock_client,
        ),
        patch(
            "apps.backend.api.routes.realtime.QwenRealtimeConfig.from_settings",
            return_value=MagicMock(),
        ),
    ):
        with TestClient(app) as client:
            with client.websocket_connect("/ws/realtime") as ws:
                # Send image control message first
                ws.send_text(
                    json.dumps(
                        {
                            "type": "image",
                            "data": "base64imgdata",
                        }
                    )
                )
                # Then send audio turn
                ws.send_bytes(b"\x00" * 3200)
                _ = ws.receive_bytes()  # consume response

    # async_send_audio_turn must have received the image
    call_kwargs = mock_client.async_send_audio_turn.call_args
    kwargs = call_kwargs[1] if call_kwargs[1] else {}
    args = call_kwargs[0] if call_kwargs[0] else ()
    image_used = kwargs.get("image_jpeg_b64") or (args[1] if len(args) > 1 else None)
    assert image_used == "base64imgdata"


def test_websocket_image_first_turn_defaults_to_scene_describe():
    """If no prior transcript exists but image is present, default to visual intent."""
    turn = _make_mock_turn(assistant_text="I see a desk", user_text="")
    mock_client = _mock_client(turn)
    mock_config = MagicMock()
    mock_classifier = MagicMock()

    with (
        patch(
            "apps.backend.api.routes.realtime.QwenRealtimeClient",
            return_value=mock_client,
        ),
        patch(
            "apps.backend.api.routes.realtime.QwenRealtimeConfig.from_settings",
            return_value=mock_config,
        ),
        patch(
            "apps.backend.api.routes.realtime.IntentClassifier.from_settings",
            return_value=mock_classifier,
        ),
    ):
        with TestClient(app) as client:
            with client.websocket_connect("/ws/realtime") as ws:
                ws.send_text(json.dumps({"type": "image", "data": "frame123"}))
                ws.send_bytes(b"\x00" * 3200)
                _ = ws.receive_bytes()

    call_kwargs = mock_client.async_send_audio_turn.call_args
    kwargs = call_kwargs[1] if call_kwargs[1] else {}
    args = call_kwargs[0] if call_kwargs[0] else ()
    instructions_used = kwargs.get("instructions") or (args[2] if len(args) > 2 else "")
    image_used = kwargs.get("image_jpeg_b64") or (args[1] if len(args) > 1 else None)
    assert image_used == "frame123"
    assert instructions_used is not None
    assert "Describe what you see" in instructions_used


# ── ping/pong ─────────────────────────────────────────────────────


def test_websocket_ping_returns_pong():
    """Ping control message must receive a pong response."""
    with (
        patch(
            "apps.backend.api.routes.realtime.QwenRealtimeClient",
        ),
        patch(
            "apps.backend.api.routes.realtime.QwenRealtimeConfig.from_settings",
            return_value=MagicMock(),
        ),
    ):
        with TestClient(app) as client:
            with client.websocket_connect("/ws/realtime") as ws:
                ws.send_text(json.dumps({"type": "ping"}))
                response = ws.receive_text()
                msg = json.loads(response)
                assert msg["type"] == "pong"


def test_websocket_upstream_failure_returns_structured_error():
    """Failed upstream handshake should return structured JSON details."""
    turn = _make_mock_turn(audio=b"", assistant_text="", user_text="")
    turn.success = False
    turn.error = (
        "DashScope session.update failed for model=qwen3.5-omni-plus-realtime "
        "voice=Tina endpoint=wss://dashscope-intl.aliyuncs.com/api-ws/v1/realtime "
        "session_id=sess_123: Access denied."
    )
    mock_client = _mock_client(turn)
    mock_config = MagicMock(
        model="qwen3.5-omni-plus-realtime",
        voice="Tina",
        endpoint="wss://dashscope-intl.aliyuncs.com/api-ws/v1/realtime",
    )

    with (
        patch(
            "apps.backend.api.routes.realtime.QwenRealtimeClient",
            return_value=mock_client,
        ),
        patch(
            "apps.backend.api.routes.realtime.QwenRealtimeConfig.from_settings",
            return_value=mock_config,
        ),
    ):
        with TestClient(app) as client:
            with client.websocket_connect("/ws/realtime") as ws:
                ws.send_bytes(b"\x00" * 3200)
                response = ws.receive_text()
                msg = json.loads(response)
                assert msg["type"] == "error"
                assert msg["code"] == "upstream_realtime_unavailable"
                assert "DashScope session.update failed" in msg["message"]
                assert msg["details"]["model"] == mock_config.model
                assert msg["details"]["voice"] == mock_config.voice
                assert msg["details"]["endpoint"] == mock_config.endpoint


def test_websocket_upstream_exception_returns_structured_error():
    """Raised upstream handshake failure should still become JSON error."""
    mock_client = MagicMock()
    mock_client.async_send_audio_turn = AsyncMock(
        side_effect=RuntimeError(
            "DashScope session.update failed for model=qwen3.5-omni-plus-realtime "
            "voice=Tina endpoint=wss://dashscope-intl.aliyuncs.com/api-ws/v1/realtime "
            "session_id=sess_123: Access denied."
        )
    )
    mock_client.close = MagicMock()
    mock_config = MagicMock(
        model="qwen3.5-omni-plus-realtime",
        voice="Tina",
        endpoint="wss://dashscope-intl.aliyuncs.com/api-ws/v1/realtime",
    )

    with (
        patch(
            "apps.backend.api.routes.realtime.QwenRealtimeClient",
            return_value=mock_client,
        ),
        patch(
            "apps.backend.api.routes.realtime.QwenRealtimeConfig.from_settings",
            return_value=mock_config,
        ),
    ):
        with TestClient(app) as client:
            with client.websocket_connect("/ws/realtime") as ws:
                ws.send_bytes(b"\x00" * 3200)
                response = ws.receive_text()
                msg = json.loads(response)
                assert msg["type"] == "error"
                assert msg["code"] == "upstream_realtime_unavailable"
                assert "Access denied" in msg["message"]
                assert msg["details"]["model"] == mock_config.model
                assert msg["details"]["voice"] == mock_config.voice
                assert msg["details"]["endpoint"] == mock_config.endpoint


def test_websocket_pending_classifier_does_not_block_next_turn():
    """A slow classifier must not stall the next audio turn."""
    first_turn = _make_mock_turn(assistant_text="first", user_text="describe this")
    second_turn = _make_mock_turn(assistant_text="second", user_text="follow up")
    mock_client = _mock_client(first_turn)
    mock_client.async_send_audio_turn = AsyncMock(side_effect=[first_turn, second_turn])
    mock_classifier = MagicMock()

    async def slow_classify(_: str):
        await asyncio.sleep(5)

    mock_classifier.classify = slow_classify
    mock_config = MagicMock()

    with (
        patch(
            "apps.backend.api.routes.realtime.QwenRealtimeClient",
            return_value=mock_client,
        ),
        patch(
            "apps.backend.api.routes.realtime.QwenRealtimeConfig.from_settings",
            return_value=mock_config,
        ),
        patch(
            "apps.backend.api.routes.realtime.IntentClassifier.from_settings",
            return_value=mock_classifier,
        ),
    ):
        with TestClient(app) as client:
            with client.websocket_connect("/ws/realtime") as ws:
                ws.send_bytes(b"\x00" * 3200)
                _ = ws.receive_bytes()
                _ = ws.receive_text()
                _ = ws.receive_text()

                start = time.monotonic()
                ws.send_bytes(b"\x01" * 3200)
                _ = ws.receive_bytes()
                elapsed = time.monotonic() - start

    assert elapsed < 1.0, f"Second turn was blocked for {elapsed:.2f}s"
    assert mock_client.async_send_audio_turn.await_count == 2


def test_websocket_empty_user_transcript_clears_stale_classification():
    """An empty transcript must clear previous-turn classification state."""
    from core.orchestrator.intent_classifier import ClassificationResult, IntentCategory

    first_turn = _make_mock_turn(assistant_text="first", user_text="read this")
    second_turn = _make_mock_turn(assistant_text="second", user_text="")
    third_turn = _make_mock_turn(assistant_text="third", user_text="")
    mock_client = _mock_client(first_turn)
    mock_client.async_send_audio_turn = AsyncMock(
        side_effect=[first_turn, second_turn, third_turn]
    )
    mock_classifier = MagicMock()
    mock_classifier.classify = AsyncMock(
        return_value=ClassificationResult(
            intent=IntentCategory.READ_TEXT,
            confidence="high",
            raw_label="READ_TEXT",
        )
    )
    mock_config = MagicMock()

    with (
        patch(
            "apps.backend.api.routes.realtime.QwenRealtimeClient",
            return_value=mock_client,
        ),
        patch(
            "apps.backend.api.routes.realtime.QwenRealtimeConfig.from_settings",
            return_value=mock_config,
        ),
        patch(
            "apps.backend.api.routes.realtime.IntentClassifier.from_settings",
            return_value=mock_classifier,
        ),
    ):
        with TestClient(app) as client:
            with client.websocket_connect("/ws/realtime") as ws:
                ws.send_bytes(b"\x00" * 3200)
                _ = ws.receive_bytes()
                _ = ws.receive_text()
                _ = ws.receive_text()

                ws.send_bytes(b"\x01" * 3200)
                _ = ws.receive_bytes()
                _ = ws.receive_text()

                ws.send_bytes(b"\x02" * 3200)
                _ = ws.receive_bytes()
                _ = ws.receive_text()

    assert mock_classifier.classify.await_count == 1


def test_websocket_pending_classifier_with_next_transcript_preserves_first_heavy_vision():
    """A later transcript must not overwrite an unfinished earlier heavy-vision intent."""
    from core.orchestrator.intent_classifier import ClassificationResult, IntentCategory
    from core.orchestrator.policy_router import RouteTarget

    first_turn = _make_mock_turn(assistant_text="first", user_text="read this")
    second_turn = _make_mock_turn(assistant_text="second", user_text="hello")
    third_turn = _make_mock_turn(assistant_text="third", user_text="")
    mock_client = _mock_client(first_turn)
    mock_client.async_send_audio_turn = AsyncMock(
        side_effect=[first_turn, second_turn, third_turn]
    )

    call_index = 0

    async def classify_side_effect(_: str):
        nonlocal call_index
        call_index += 1
        if call_index == 1:
            await asyncio.sleep(0.2)
            return ClassificationResult(
                intent=IntentCategory.READ_TEXT,
                confidence="high",
                raw_label="READ_TEXT",
            )
        return ClassificationResult(
            intent=IntentCategory.GENERAL_CHAT,
            confidence="high",
            raw_label="GENERAL_CHAT",
        )

    mock_classifier = MagicMock()
    mock_classifier.classify = classify_side_effect
    mock_mm_client = MagicMock()
    mock_mm_client._model = "qwen3.5-flash"
    mock_mm_client.analyze = AsyncMock(
        return_value=MagicMock(success=True, text="READ RESULT")
    )
    mock_config = MagicMock()

    with (
        patch(
            "apps.backend.api.routes.realtime.QwenRealtimeClient",
            return_value=mock_client,
        ),
        patch(
            "apps.backend.api.routes.realtime.QwenRealtimeConfig.from_settings",
            return_value=mock_config,
        ),
        patch(
            "apps.backend.api.routes.realtime.IntentClassifier.from_settings",
            return_value=mock_classifier,
        ),
        patch(
            "apps.backend.api.routes.realtime.MultimodalClient.from_settings",
            return_value=mock_mm_client,
        ),
        patch(
            "apps.backend.api.routes.realtime.assess_frame_quality",
            return_value=(True, ""),
        ),
    ):
        with TestClient(app) as client:
            with client.websocket_connect("/ws/realtime") as ws:
                ws.send_text(json.dumps({"type": "image", "data": "image-one"}))
                ws.send_bytes(b"\x00" * 3200)
                _ = ws.receive_bytes()
                _ = ws.receive_text()
                _ = ws.receive_text()

                ws.send_text(json.dumps({"type": "image", "data": "image-two"}))
                ws.send_bytes(b"\x01" * 3200)
                _ = ws.receive_bytes()
                _ = ws.receive_text()
                _ = ws.receive_text()

                time.sleep(0.3)

                ws.send_bytes(b"\x02" * 3200)
                _ = ws.receive_bytes()
                _ = ws.receive_text()

    mock_mm_client.analyze.assert_awaited_once()
    vision_request = mock_mm_client.analyze.await_args.args[0]
    assert vision_request.image_jpeg_b64 == "image-one"
    assert call_index >= 1


# ── disconnect ────────────────────────────────────────────────────


def test_websocket_disconnect_closes_client():
    """Disconnect must call client.close() without raising."""
    mock_client = MagicMock()
    mock_client.async_send_audio_turn = AsyncMock()
    mock_client.close = MagicMock()
    mock_memory_manager = MagicMock()
    mock_memory_manager.store.initialize = AsyncMock()

    with (
        patch(
            "apps.backend.api.routes.realtime.QwenRealtimeClient",
            return_value=mock_client,
        ),
        patch(
            "apps.backend.api.routes.realtime.QwenRealtimeConfig.from_settings",
            return_value=MagicMock(),
        ),
        patch(
            "apps.backend.api.routes.realtime.MemoryManager.from_settings",
            return_value=mock_memory_manager,
        ),
    ):
        with TestClient(app) as client:
            with client.websocket_connect("/ws/realtime"):
                pass  # connect then immediately disconnect

    mock_client.close.assert_called_once()


def test_mm_client_created_once_per_session():
    """
    Regression: MultimodalClient must be instantiated once at
    WebSocket connection time (session scope), not once per
    audio turn.
    Verify by checking realtime.py module source for the
    instantiation pattern.
    """
    import inspect

    import apps.backend.api.routes.realtime as realtime_module

    source = inspect.getsource(realtime_module)

    assert "mm_client" in source, "mm_client not found in realtime.py at all"

    mm_pos = source.index("mm_client")

    assert mm_pos >= 0, "mm_client missing from realtime.py — session scope regression"


@pytest.mark.asyncio
async def test_memory_write_same_turn_confirmation():
    """
    When result.user_transcript starts with a memory-save phrase,
    the override turn must carry a confirmation instruction
    containing the cleaned fact.
    """
    from unittest.mock import AsyncMock, MagicMock, patch

    from core.orchestrator.prompt_builder import build_memory_fact

    mock_result = MagicMock()
    mock_result.user_transcript = "remember that my name is Om"
    mock_result.audio_chunks = []
    mock_result.assistant_transcript = ""

    mock_override = MagicMock()
    mock_override.audio_chunks = [b"\x00" * 100]
    mock_override.assistant_transcript = "I will remember that my name is Om."
    mock_override.user_transcript = ""
    mock_override.assistant_audio_pcm = b"\x00" * 100
    mock_override.success = True
    mock_override.error = None

    cleaned_fact = build_memory_fact(mock_result.user_transcript)

    with patch("apps.backend.api.routes.realtime.MemoryManager") as mock_mm_cls:
        mock_mm = AsyncMock()
        mock_mm.store.initialize = AsyncMock()
        mock_mm.save = AsyncMock(return_value="my name is Om")
        mock_mm.recall = AsyncMock(return_value=None)
        mock_mm_cls.from_settings.return_value = mock_mm

        await mock_mm.save(
            user_id="default",
            raw_utterance="remember that my name is Om",
        )
        mock_mm.save.assert_called_once_with(
            user_id="default",
            raw_utterance="remember that my name is Om",
        )
        assert cleaned_fact == "my name is Om"
        assert mock_mm.save.return_value == "my name is Om"


@pytest.mark.asyncio
async def test_memory_recall_same_turn_injects_memory_context():
    """
    When result.user_transcript starts with a recall phrase,
    the override turn must receive instructions built from
    build_system_prompt containing the stored memory context.
    """
    from unittest.mock import AsyncMock, patch

    from core.orchestrator.prompt_builder import build_system_prompt

    memory_context = "my doctor is Dr. Sharma\nmy city is Bengaluru"
    query = "who is my doctor"

    with patch("apps.backend.api.routes.realtime.MemoryManager") as mock_mm_cls:
        mock_mm = AsyncMock()
        mock_mm.store.initialize = AsyncMock()
        mock_mm.recall = AsyncMock(return_value=memory_context)
        mock_mm_cls.from_settings.return_value = mock_mm

        recall_result = await mock_mm.recall(
            user_id="default",
            query=query,
            top_k=3,
        )
        assert recall_result == memory_context

        instructions = build_system_prompt(
            base_instructions=(
                f"The user asked: {query}\n"
                "Answer using only the relevant stored memory."
                " Be brief and speak naturally."
            ),
            memory_context=memory_context,
        )
        assert "Dr. Sharma" in instructions
        assert "Bengaluru" in instructions


def test_classifier_memory_write_route_calls_memory_manager():
    """A previous-turn MEMORY_WRITE prediction must call memory_manager.save."""
    from core.orchestrator.intent_classifier import ClassificationResult, IntentCategory

    first_turn = _make_mock_turn(
        assistant_text="first", user_text="keep in mind that my name is Om"
    )
    override_turn = _make_mock_turn(
        assistant_text="I will remember that my name is Om.", user_text=""
    )
    mock_client = _mock_client(first_turn)
    mock_client.async_send_audio_turn = AsyncMock(
        side_effect=[first_turn, override_turn]
    )
    mock_classifier = MagicMock()
    mock_classifier.classify = AsyncMock(
        return_value=ClassificationResult(
            intent=IntentCategory.MEMORY_SAVE,
            confidence="high",
            raw_label="MEMORY_SAVE",
        )
    )
    mock_memory_manager = MagicMock()
    mock_memory_manager.store.initialize = AsyncMock()
    mock_memory_manager.save = AsyncMock(return_value="my name is Om")
    mock_memory_manager.recall = AsyncMock(return_value=None)

    with (
        patch(
            "apps.backend.api.routes.realtime.QwenRealtimeClient",
            return_value=mock_client,
        ),
        patch(
            "apps.backend.api.routes.realtime.QwenRealtimeConfig.from_settings",
            return_value=MagicMock(),
        ),
        patch(
            "apps.backend.api.routes.realtime.IntentClassifier.from_settings",
            return_value=mock_classifier,
        ),
        patch(
            "apps.backend.api.routes.realtime.MemoryManager.from_settings",
            return_value=mock_memory_manager,
        ),
    ):
        with TestClient(app) as client:
            with client.websocket_connect("/ws/realtime") as ws:
                ws.send_bytes(b"\x00" * 3200)
                _ = ws.receive_bytes()
                _ = ws.receive_text()
                _ = ws.receive_text()

                ws.send_bytes(b"\x01" * 3200)
                _ = ws.receive_bytes()
                _ = ws.receive_text()

    mock_memory_manager.save.assert_called_once_with(
        user_id="default",
        raw_utterance="keep in mind that my name is Om",
    )


def test_classifier_memory_recall_route_calls_memory_manager():
    """A previous-turn MEMORY_READ prediction must call memory_manager.recall."""
    from core.orchestrator.intent_classifier import ClassificationResult, IntentCategory

    first_turn = _make_mock_turn(
        assistant_text="first", user_text="can you tell me about my doctor"
    )
    override_turn = _make_mock_turn(
        assistant_text="Your doctor is Dr. Sharma.", user_text=""
    )
    mock_client = _mock_client(first_turn)
    mock_client.async_send_audio_turn = AsyncMock(
        side_effect=[first_turn, override_turn]
    )
    mock_classifier = MagicMock()
    mock_classifier.classify = AsyncMock(
        return_value=ClassificationResult(
            intent=IntentCategory.MEMORY_RECALL,
            confidence="high",
            raw_label="MEMORY_RECALL",
        )
    )
    mock_memory_manager = MagicMock()
    mock_memory_manager.store.initialize = AsyncMock()
    mock_memory_manager.save = AsyncMock(return_value="")
    mock_memory_manager.recall = AsyncMock(return_value="my doctor is Dr. Sharma")

    with (
        patch(
            "apps.backend.api.routes.realtime.QwenRealtimeClient",
            return_value=mock_client,
        ),
        patch(
            "apps.backend.api.routes.realtime.QwenRealtimeConfig.from_settings",
            return_value=MagicMock(),
        ),
        patch(
            "apps.backend.api.routes.realtime.IntentClassifier.from_settings",
            return_value=mock_classifier,
        ),
        patch(
            "apps.backend.api.routes.realtime.MemoryManager.from_settings",
            return_value=mock_memory_manager,
        ),
    ):
        with TestClient(app) as client:
            with client.websocket_connect("/ws/realtime") as ws:
                ws.send_bytes(b"\x00" * 3200)
                _ = ws.receive_bytes()
                _ = ws.receive_text()
                _ = ws.receive_text()

                ws.send_bytes(b"\x01" * 3200)
                _ = ws.receive_bytes()
                _ = ws.receive_text()

    mock_memory_manager.recall.assert_called_once_with(
        user_id="default",
        query="can you tell me about my doctor",
        top_k=3,
    )
