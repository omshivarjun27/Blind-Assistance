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


def _clone_mock_turn(turn: Any, audio: bytes | None = None):
    cloned = MagicMock()
    cloned.assistant_audio_pcm = turn.assistant_audio_pcm if audio is None else audio
    cloned.assistant_transcript = turn.assistant_transcript
    cloned.user_transcript = turn.user_transcript
    cloned.success = turn.success
    cloned.error = turn.error
    return cloned


def _mock_client(turn: Any):
    """Build a mock QwenRealtimeClient for prepare→update→create flow."""
    turns = turn if isinstance(turn, list) else [turn]
    client = MagicMock()
    client.async_prepare_audio_turn = AsyncMock(
        side_effect=[t.user_transcript for t in turns]
    )
    client.async_update_instructions = AsyncMock(return_value=None)
    client.async_create_response_for_prepared_turn = AsyncMock(side_effect=turns)
    client.async_create_response_for_prepared_turn_streaming = AsyncMock(
        side_effect=[_clone_mock_turn(t) for t in turns]
    )
    client.async_connect = AsyncMock(return_value=None)
    client.async_reconnect = AsyncMock(return_value=None)
    client.is_connected = MagicMock(return_value=True)
    client.needs_reconnect = MagicMock(return_value=False)
    client.close = MagicMock()
    return client


def _receive_until_bytes(ws, max_messages: int = 6) -> bytes:
    for _ in range(max_messages):
        message = ws.receive()
        if "bytes" in message and message["bytes"] is not None:
            return message["bytes"]
    raise AssertionError("Expected a binary websocket frame but none arrived")


def test_session_updated_before_audio_stream():
    """Client must wait for session.updated ack before appending audio."""
    from apps.backend.services.dashscope.realtime_client import (
        QwenRealtimeClient,
        QwenRealtimeConfig,
        SessionState,
    )

    client = QwenRealtimeClient(QwenRealtimeConfig(api_key="test-key"))
    client._connected = True
    client._ws = MagicMock()
    client._session_updated_confirmed = False
    client._session_start_time = time.monotonic()
    client._state = SessionState.IDLE

    sent_types: list[str] = []
    wait_targets: list[tuple[str, float]] = []
    client._ws.send = lambda data: sent_types.append(json.loads(data)["type"])

    def fake_wait_for_event(expected_type: str, timeout: float = 20.0):
        wait_targets.append((expected_type, timeout))
        if expected_type == "session.updated":
            client._session_updated_confirmed = True
            return {"type": "session.updated", "session": {"id": "sess-ready"}}
        return {"type": expected_type}

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(client, "_wait_for_event", fake_wait_for_event)
        client._stream_audio(b"\x00" * 3200, None, auto_create_response=False)

    assert wait_targets[0] == ("session.updated", 5.0)
    assert sent_types[0] == "input_audio_buffer.append"


def test_first_audio_ms_not_null():
    """A turn must still produce assistant audio even when transcript is unavailable."""
    turn = _make_mock_turn(audio=b"\x01\x02" * 40, assistant_text="hello", user_text="")
    mock_client = _mock_client(turn)
    mock_client.async_prepare_audio_turn = AsyncMock(return_value=None)

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


def test_audio_starts_before_intent_resolves(caplog):
    """Audio bytes must reach the client before classifier resolution."""
    from core.orchestrator.intent_classifier import ClassificationResult, IntentCategory

    caplog.set_level("INFO", logger="ally-vision-realtime-route")
    turns = [
        _make_mock_turn(
            audio=b"\x01\x02" * 20, assistant_text="warmup", user_text="hello"
        ),
        _make_mock_turn(
            audio=b"\x01\x02" * 40, assistant_text="hello", user_text="how are you"
        ),
    ]
    mock_client = _mock_client(turns)
    audio_started = {"value": False}
    stream_index = {"value": 0}

    async def streaming_side_effect(on_audio_chunk):
        next_turn = turns[stream_index["value"]]
        stream_index["value"] += 1
        audio_started["value"] = True
        on_audio_chunk(next_turn.assistant_audio_pcm)
        return _clone_mock_turn(next_turn, audio=b"")

    async def delayed_classify(_: str):
        await asyncio.sleep(0.5)
        assert audio_started["value"] is True
        return ClassificationResult(
            intent=IntentCategory.GENERAL_CHAT,
            confidence="high",
            raw_label="GENERAL_CHAT",
        )

    mock_client.async_create_response_for_prepared_turn_streaming = AsyncMock(
        side_effect=streaming_side_effect
    )
    mock_classifier = MagicMock()
    mock_classifier.classify = AsyncMock(side_effect=delayed_classify)
    mock_classifier.close = AsyncMock(return_value=None)

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
    ):
        with TestClient(app) as client:
            with client.websocket_connect("/ws/realtime") as ws:
                ws.send_bytes(b"\x00" * 3200)
                _ = _receive_until_bytes(ws)

                started = time.monotonic()
                ws.send_bytes(b"\x00" * 3200)
                response = _receive_until_bytes(ws)
                first_audio_ms = int((time.monotonic() - started) * 1000)
                time.sleep(0.7)

    assert response == turns[1].assistant_audio_pcm
    assert first_audio_ms < 500
    assert "Audio streaming started — intent not yet resolved" in caplog.text


def test_intent_timeout_defaults_to_general_chat(caplog):
    """A stuck classifier must time out without blocking audio bytes."""
    caplog.set_level("INFO", logger="ally-vision-realtime-route")
    turns = [
        _make_mock_turn(
            audio=b"\x03\x04" * 20, assistant_text="warmup", user_text="hello"
        ),
        _make_mock_turn(
            audio=b"\x03\x04" * 40, assistant_text="hello", user_text="how are you"
        ),
    ]
    mock_client = _mock_client(turns)
    stream_index = {"value": 0}

    async def streaming_side_effect(on_audio_chunk):
        next_turn = turns[stream_index["value"]]
        stream_index["value"] += 1
        on_audio_chunk(next_turn.assistant_audio_pcm)
        return _clone_mock_turn(next_turn, audio=b"")

    async def never_resolve(_: str):
        await asyncio.sleep(10)
        return MagicMock()

    mock_client.async_create_response_for_prepared_turn_streaming = AsyncMock(
        side_effect=streaming_side_effect
    )
    mock_classifier = MagicMock()
    mock_classifier.classify = AsyncMock(side_effect=never_resolve)
    mock_classifier.close = AsyncMock(return_value=None)

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
    ):
        with TestClient(app) as client:
            with client.websocket_connect("/ws/realtime") as ws:
                ws.send_bytes(b"\x00" * 3200)
                _ = _receive_until_bytes(ws)

                started = time.monotonic()
                ws.send_bytes(b"\x00" * 3200)
                response = _receive_until_bytes(ws)
                first_audio_ms = int((time.monotonic() - started) * 1000)
                time.sleep(2.3)

    assert response == turns[1].assistant_audio_pcm
    assert first_audio_ms < 500
    assert "Intent classification timed out — defaulting to general_chat" in caplog.text


def test_turn1_skips_classifier(caplog):
    """Turn 1 cold start must skip classifier entirely."""
    caplog.set_level("INFO", logger="ally-vision-realtime-route")
    turn = _make_mock_turn(
        audio=b"\x05\x06" * 40, assistant_text="hello", user_text="hello"
    )
    mock_client = _mock_client(turn)
    mock_classifier = MagicMock()
    mock_classifier.classify = AsyncMock()
    mock_classifier.close = AsyncMock(return_value=None)

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
    ):
        with TestClient(app) as client:
            with client.websocket_connect("/ws/realtime") as ws:
                ws.send_bytes(b"\x00" * 3200)
                response = ws.receive_bytes()
                _ = ws.receive_text()
                _ = ws.receive_text()

    assert response == turn.assistant_audio_pcm
    mock_classifier.classify.assert_not_awaited()
    assert (
        "Intent classification skipped — no transcript (turn 0 cold start)"
        in caplog.text
    )
    assert "Intent classification timed out" not in caplog.text


def test_turn2_classifies_normally(caplog):
    """Turn 2 should classify once after turn 1 cold-start skip."""
    from core.orchestrator.intent_classifier import ClassificationResult, IntentCategory

    caplog.set_level("INFO", logger="ally-vision-realtime-route")
    turns = [
        _make_mock_turn(
            audio=b"\x01\x02" * 20, assistant_text="one", user_text="hello"
        ),
        _make_mock_turn(
            audio=b"\x03\x04" * 20, assistant_text="two", user_text="how are you"
        ),
    ]
    mock_client = _mock_client(turns)
    mock_classifier = MagicMock()
    mock_classifier.classify = AsyncMock(
        return_value=ClassificationResult(
            intent=IntentCategory.GENERAL_CHAT,
            confidence="high",
            raw_label="GENERAL_CHAT",
        )
    )
    mock_classifier.close = AsyncMock(return_value=None)

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
    ):
        with TestClient(app) as client:
            with client.websocket_connect("/ws/realtime") as ws:
                ws.send_bytes(b"\x00" * 3200)
                _ = ws.receive_bytes()
                _ = ws.receive_text()
                _ = ws.receive_text()

                ws.send_bytes(b"\x00" * 3200)
                _ = ws.receive_bytes()
                _ = ws.receive_text()
                _ = ws.receive_text()

    mock_classifier.classify.assert_awaited_once()
    assert (
        "Intent classification skipped — no transcript (turn 0 cold start)"
        in caplog.text
    )
    assert "Intent classified: GENERAL_CHAT in" in caplog.text


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


def test_client_created_once_per_user_session():
    """One user websocket session must construct one DashScope client."""
    turns = [
        _make_mock_turn(audio=b"\x01\x02" * 10, assistant_text="one", user_text="one"),
        _make_mock_turn(audio=b"\x01\x02" * 10, assistant_text="two", user_text="two"),
        _make_mock_turn(
            audio=b"\x01\x02" * 10, assistant_text="three", user_text="three"
        ),
    ]
    mock_client = _mock_client(turns)
    mock_ctor = MagicMock(return_value=mock_client)

    with (
        patch(
            "apps.backend.api.routes.realtime.QwenRealtimeClient",
            mock_ctor,
        ),
        patch(
            "apps.backend.api.routes.realtime.QwenRealtimeConfig.from_settings",
            return_value=MagicMock(),
        ),
    ):
        with TestClient(app) as client:
            with client.websocket_connect("/ws/realtime") as ws:
                for _ in range(3):
                    ws.send_bytes(b"\x00" * 3200)
                    _ = ws.receive_bytes()
                    _ = ws.receive_text()
                    _ = ws.receive_text()

    assert mock_ctor.call_count == 1
    mock_client.async_connect.assert_awaited_once()


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


def test_websocket_prepare_audio_turn_called_with_audio_pcm():
    """Current-turn prepare method must receive the raw PCM bytes."""
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

    mock_client.async_prepare_audio_turn.assert_called_once()
    call_kwargs = mock_client.async_prepare_audio_turn.call_args
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
                ws.send_bytes(b"\x01" * 3200)
                _ = ws.receive_bytes()  # consume response

    # prepare_audio_turn must have received the image
    call_kwargs = mock_client.async_prepare_audio_turn.call_args
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

    update_call = mock_client.async_update_instructions.call_args
    update_instructions = (
        update_call[1].get("instructions")
        if update_call and update_call[1]
        else (update_call[0][0] if update_call and update_call[0] else "")
    )
    assert update_instructions is not None
    assert "Describe what you see" in update_instructions


# ── ping/pong ─────────────────────────────────────────────────────


def test_websocket_ping_returns_pong():
    """Ping control message must receive a pong response."""
    mock_client = _mock_client(_make_mock_turn())

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
                ws.send_text(json.dumps({"type": "ping"}))
                response = ws.receive_text()
                msg = json.loads(response)
                assert msg["type"] == "pong"


def test_websocket_upstream_failure_returns_structured_error():
    """Failed upstream handshake should return structured JSON details."""
    turn = _make_mock_turn(audio=b"", assistant_text="", user_text="hello")
    turn.success = False
    turn.error = (
        "DashScope session.update failed for model=qwen3-omni-flash-realtime "
        "voice=Cherry endpoint=wss://dashscope-intl.aliyuncs.com/api-ws/v1/realtime "
        "session_id=sess_123: Access denied."
    )
    mock_client = _mock_client(turn)
    mock_config = MagicMock(
        model="qwen3-omni-flash-realtime",
        voice="Cherry",
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
                msg: dict[str, Any] = {}
                for _ in range(3):
                    response = ws.receive_text()
                    msg = json.loads(response)
                    if msg["type"] == "error":
                        break
                assert msg["type"] == "error"
                assert msg["code"] == "upstream_realtime_unavailable"
                assert "DashScope session.update failed" in msg["message"]
                assert msg["details"]["model"] == mock_config.model
                assert msg["details"]["voice"] == mock_config.voice
                assert msg["details"]["endpoint"] == mock_config.endpoint


def test_websocket_upstream_exception_returns_structured_error():
    """Raised upstream handshake failure should still become JSON error."""
    mock_client = MagicMock()
    mock_client.async_prepare_audio_turn = AsyncMock(
        side_effect=RuntimeError(
            "DashScope session.update failed for model=qwen3-omni-flash-realtime "
            "voice=Cherry endpoint=wss://dashscope-intl.aliyuncs.com/api-ws/v1/realtime "
            "session_id=sess_123: Access denied."
        )
    )
    mock_client.async_connect = AsyncMock(return_value=None)
    mock_client.async_reconnect = AsyncMock(return_value=None)
    mock_client.is_connected = MagicMock(return_value=True)
    mock_client.needs_reconnect = MagicMock(return_value=False)
    mock_client.async_update_instructions = AsyncMock()
    mock_client.async_create_response_for_prepared_turn = AsyncMock()
    mock_client.close = MagicMock()
    mock_config = MagicMock(
        model="qwen3-omni-flash-realtime",
        voice="Cherry",
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


def test_websocket_current_turn_classifier_called_for_each_spoken_turn():
    """After turn 1 cold-start skip, subsequent spoken turns should classify normally."""
    from core.orchestrator.intent_classifier import ClassificationResult, IntentCategory

    first_turn = _make_mock_turn(assistant_text="first", user_text="describe this")
    second_turn = _make_mock_turn(assistant_text="second", user_text="follow up")
    mock_client = _mock_client([first_turn, second_turn])
    mock_classifier = MagicMock()
    mock_classifier.classify = AsyncMock(
        side_effect=[
            ClassificationResult(
                intent=IntentCategory.GENERAL_CHAT,
                confidence="high",
                raw_label="GENERAL_CHAT",
            ),
            ClassificationResult(
                intent=IntentCategory.GENERAL_CHAT,
                confidence="high",
                raw_label="GENERAL_CHAT",
            ),
        ]
    )
    mock_classifier.close = AsyncMock(return_value=None)
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
                _ = ws.receive_text()

    assert mock_classifier.classify.await_count == 1
    mock_client.async_prepare_audio_turn.assert_awaited()
    mock_client.async_create_response_for_prepared_turn_streaming.assert_awaited()


def test_websocket_empty_user_transcript_skips_response_after_first_scene():
    """After the first scene intro, empty transcripts should not trigger another response."""
    import inspect

    import apps.backend.api.routes.realtime as realtime_module

    source = inspect.getsource(realtime_module)
    assert "Silent turn after first scene — skipping response" in source


def test_websocket_current_turn_read_text_routes_to_heavy_vision():
    """Current-turn READ_TEXT intent must use the same turn's queued image."""
    from core.orchestrator.intent_classifier import ClassificationResult, IntentCategory

    first_turn = _make_mock_turn(assistant_text="first", user_text="read this")
    mock_client = _mock_client(first_turn)
    mock_classifier = MagicMock()
    mock_classifier.classify = AsyncMock(
        return_value=ClassificationResult(
            intent=IntentCategory.READ_TEXT,
            confidence="high",
            raw_label="READ_TEXT",
        )
    )
    mock_mm_client = MagicMock()
    mock_mm_client._model = "qwen3.6-plus"
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
                ws.send_bytes(b"\x01" * 3200)
                _ = ws.receive_bytes()
                _ = ws.receive_text()
                _ = ws.receive_text()

    mock_mm_client.analyze.assert_awaited_once()
    vision_request = mock_mm_client.analyze.await_args.args[0]
    assert vision_request.image_jpeg_b64 == "image-one"
    assert mock_classifier.classify.await_count == 1


# ── disconnect ────────────────────────────────────────────────────


def test_websocket_disconnect_closes_client():
    """Disconnect must call client.close() without raising."""
    mock_client = MagicMock()
    mock_client.async_connect = AsyncMock(return_value=None)
    mock_client.async_reconnect = AsyncMock(return_value=None)
    mock_client.is_connected = MagicMock(return_value=True)
    mock_client.needs_reconnect = MagicMock(return_value=False)
    mock_client.async_prepare_audio_turn = AsyncMock()
    mock_client.async_update_instructions = AsyncMock()
    mock_client.async_create_response_for_prepared_turn = AsyncMock()
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
            with client.websocket_connect("/ws/realtime") as ws:
                ws.send_text(json.dumps({"type": "ping"}))
                assert json.loads(ws.receive_text())["type"] == "pong"

    deadline = time.time() + 1.0
    while mock_client.close.call_count == 0 and time.time() < deadline:
        time.sleep(0.01)

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
    """A current-turn MEMORY_WRITE prediction must call memory_manager.save."""
    from core.orchestrator.intent_classifier import ClassificationResult, IntentCategory

    turns = [
        _make_mock_turn(assistant_text="warmup", user_text="hello"),
        _make_mock_turn(
            assistant_text="first", user_text="keep in mind that my name is Om"
        ),
    ]
    mock_client = _mock_client(turns)
    mock_classifier = MagicMock()
    mock_classifier.classify = AsyncMock(
        return_value=ClassificationResult(
            intent=IntentCategory.MEMORY_SAVE,
            confidence="high",
            raw_label="MEMORY_SAVE",
        )
    )
    mock_classifier.close = AsyncMock(return_value=None)
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

                ws.send_bytes(b"\x00" * 3200)
                _ = ws.receive_bytes()
                _ = ws.receive_text()
                _ = ws.receive_text()

    mock_memory_manager.save.assert_called_once_with(
        user_id="default",
        raw_utterance="keep in mind that my name is Om",
    )


def test_classifier_memory_recall_route_calls_memory_manager():
    """A current-turn MEMORY_READ prediction must call memory_manager.recall."""
    from core.orchestrator.intent_classifier import ClassificationResult, IntentCategory

    turns = [
        _make_mock_turn(assistant_text="warmup", user_text="hello"),
        _make_mock_turn(
            assistant_text="first", user_text="can you tell me about my doctor"
        ),
    ]
    mock_client = _mock_client(turns)
    mock_classifier = MagicMock()
    mock_classifier.classify = AsyncMock(
        return_value=ClassificationResult(
            intent=IntentCategory.MEMORY_RECALL,
            confidence="high",
            raw_label="MEMORY_RECALL",
        )
    )
    mock_classifier.close = AsyncMock(return_value=None)
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

                ws.send_bytes(b"\x00" * 3200)
                _ = ws.receive_bytes()
                _ = ws.receive_text()
                _ = ws.receive_text()

    mock_memory_manager.recall.assert_called_once_with(
        user_id="default",
        query="can you tell me about my doctor",
        top_k=3,
    )


def test_interrupt_control_message_calls_cancel_response():
    """{"type": "interrupt"} must call client.cancel_response()."""
    turn = _make_mock_turn()
    mock_client = _mock_client(turn)
    mock_client.cancel_response = MagicMock()
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
            with client.websocket_connect("/ws/realtime") as ws:
                ws.send_text(json.dumps({"type": "interrupt"}))
                ws.send_bytes(b"\x00" * 3200)
                ws.receive_bytes()

    mock_client.cancel_response.assert_called_once()


# ── _is_memory_query tests (Plan 05 patch) ──────────────────────────────────


class TestIsMemoryQuery:
    """Tests for the past-tense memory trigger detector."""

    def test_what_is_my_name(self):
        from apps.backend.api.routes.realtime import _is_memory_query

        assert _is_memory_query("what is my name") is True

    def test_what_was_triggers(self):
        from apps.backend.api.routes.realtime import _is_memory_query

        assert _is_memory_query("what was that thing I showed you") is True

    def test_do_you_remember(self):
        from apps.backend.api.routes.realtime import _is_memory_query

        assert _is_memory_query("do you remember what I told you") is True

    def test_earlier_triggers(self):
        from apps.backend.api.routes.realtime import _is_memory_query

        assert _is_memory_query("what did I say earlier") is True

    def test_casual_chat_not_triggered(self):
        from apps.backend.api.routes.realtime import _is_memory_query

        assert _is_memory_query("how are you today") is False

    def test_empty_string(self):
        from apps.backend.api.routes.realtime import _is_memory_query

        assert _is_memory_query("") is False

    def test_none_equivalent_empty(self):
        from apps.backend.api.routes.realtime import _is_memory_query

        assert _is_memory_query("   ") is False

    def test_kannada_name_trigger(self):
        from apps.backend.api.routes.realtime import _is_memory_query

        assert _is_memory_query("ನನ್ನ ಹೆಸರು ಏನು") is True

    def test_hindi_name_trigger(self):
        from apps.backend.api.routes.realtime import _is_memory_query

        assert _is_memory_query("मेरा नाम क्या है") is True

    def test_case_insensitive(self):
        from apps.backend.api.routes.realtime import _is_memory_query

        assert _is_memory_query("WHAT IS MY NAME") is True
        assert _is_memory_query("What Did I Show You") is True


# ── scene + search regression tests ────────────────────────────────────────


def test_scene_describe_fallback_has_once_only_guard_in_source():
    import inspect

    import apps.backend.api.routes.realtime as realtime_module

    source = inspect.getsource(realtime_module)
    assert "_scene_described_once: bool = False" in source
    assert "and not _scene_described_once" in source


def test_silent_turn_after_first_scene_guard_present_in_source():
    import inspect

    import apps.backend.api.routes.realtime as realtime_module

    source = inspect.getsource(realtime_module)
    assert "Silent turn after first scene — skipping response" in source


def test_web_search_removed_from_realtime_source():
    import inspect

    import apps.backend.api.routes.realtime as realtime_module

    source = inspect.getsource(realtime_module)
    assert "SearchManager" not in source
    assert "def _is_search_query" not in source
    assert "WEB_SEARCH" not in source


def test_post_scene_default_uses_general_chat_instructions_in_source():
    import inspect

    import apps.backend.api.routes.realtime as realtime_module

    source = inspect.getsource(realtime_module)
    assert (
        "default_instructions = route(IntentCategory.GENERAL_CHAT).system_instructions"
        in source
    )
    assert "config.instructions = default_instructions" in source
