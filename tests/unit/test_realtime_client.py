"""
Unit tests for Plan 02: QwenRealtimeClient.
All tests use mocks only — no real network calls.
"""

from __future__ import annotations

import base64
import json
import os
import time
from typing import Any, cast
from unittest.mock import MagicMock

import pytest
import websocket


# ── config tests ─────────────────────────────────────────────────


def test_config_defaults():
    """QwenRealtimeConfig defaults should match the upgraded runtime defaults."""
    from apps.backend.services.dashscope.realtime_client import QwenRealtimeConfig

    cfg = QwenRealtimeConfig(api_key="test-key")
    assert cfg.model == "qwen3.5-omni-flash-realtime"
    assert "realtime" in cfg.model
    assert cfg.endpoint == "wss://dashscope-intl.aliyuncs.com/api-ws/v1/realtime"
    assert cfg.endpoint.startswith("wss://")
    assert cfg.audio_in_rate == 16000
    assert cfg.audio_out_rate == 24000
    assert cfg.chunk_bytes == 3200
    assert cfg.voice == "Tina"
    assert cfg.transcription_model == "qwen3-asr-flash-realtime"


def test_config_defaults_follow_reloaded_settings():
    """from_settings() should follow reloaded settings and env overrides."""
    import importlib

    original_model = os.environ.get("QWEN_REALTIME_DEV")
    original_endpoint = os.environ.get("DASHSCOPE_REALTIME_URL")
    original_voice = os.environ.get("QWEN_OMNI_VOICE")

    try:
        os.environ["QWEN_REALTIME_DEV"] = "qwen3.5-omni-plus-realtime"
        os.environ["DASHSCOPE_REALTIME_URL"] = "wss://example.com/realtime"
        os.environ["QWEN_OMNI_VOICE"] = "Tina"

        import shared.config.settings as settings_module
        from apps.backend.services.dashscope import realtime_client as realtime_module

        settings_module = importlib.reload(settings_module)
        realtime_module = importlib.reload(realtime_module)

        cfg = realtime_module.QwenRealtimeConfig.from_settings()

        assert cfg.model == settings_module.QWEN_REALTIME_MODEL
        assert cfg.endpoint == settings_module.DASHSCOPE_REALTIME_URL
        assert cfg.voice == settings_module.QWEN_OMNI_VOICE
        assert cfg.transcription_model == "qwen3-asr-flash-realtime"
    finally:
        if original_model is None:
            os.environ.pop("QWEN_REALTIME_DEV", None)
        else:
            os.environ["QWEN_REALTIME_DEV"] = original_model

        if original_endpoint is None:
            os.environ.pop("DASHSCOPE_REALTIME_URL", None)
        else:
            os.environ["DASHSCOPE_REALTIME_URL"] = original_endpoint

        if original_voice is None:
            os.environ.pop("QWEN_OMNI_VOICE", None)
        else:
            os.environ["QWEN_OMNI_VOICE"] = original_voice

        import shared.config.settings as settings_module
        from apps.backend.services.dashscope import realtime_client as realtime_module

        _ = importlib.reload(settings_module)
        _ = importlib.reload(realtime_module)


def test_default_voice_for_model_prefers_tina_for_qwen35_omni_models():
    """Qwen 3.5 omni realtime models should default to Tina."""
    from apps.backend.services.dashscope.realtime_client import default_voice_for_model

    assert default_voice_for_model("qwen3.5-omni-flash-realtime") == "Tina"
    assert default_voice_for_model("qwen3.5-omni-plus-realtime") == "Tina"


def test_default_voice_for_model_keeps_cherry_for_qwen3_flash():
    """Legacy qwen3 flash realtime model should keep Cherry."""
    from apps.backend.services.dashscope.realtime_client import default_voice_for_model

    assert default_voice_for_model("flash-realtime") == "Cherry"


def test_config_from_settings_reads_env():
    """from_settings() reads model and endpoint from settings."""
    from apps.backend.services.dashscope.realtime_client import QwenRealtimeConfig

    cfg = QwenRealtimeConfig.from_settings()
    assert cfg.api_key == "test-key-for-unit-tests"
    assert "realtime" in cfg.model
    assert cfg.endpoint.startswith("wss://")
    assert cfg.voice == "Tina"


def test_config_from_settings_uses_fixed_asr_model():
    """Phase 1 pins the realtime transcription model to qwen3 ASR."""
    from apps.backend.services.dashscope.realtime_client import QwenRealtimeConfig

    cfg = QwenRealtimeConfig.from_settings()
    assert cfg.transcription_model == "qwen3-asr-flash-realtime"


def test_config_from_settings_raises_on_missing_key():
    """from_settings() raises ValueError when DASHSCOPE_API_KEY absent."""
    original = os.environ.get("DASHSCOPE_API_KEY")
    try:
        os.environ["DASHSCOPE_API_KEY"] = "FILL_IN_YOUR_KEY_HERE"
        import importlib
        import shared.config.settings as s

        _ = importlib.reload(s)
        from apps.backend.services.dashscope import realtime_client as rc

        _ = importlib.reload(rc)
        with pytest.raises(ValueError, match="DASHSCOPE_API_KEY"):
            _ = rc.QwenRealtimeConfig.from_settings()
    finally:
        if original:
            os.environ["DASHSCOPE_API_KEY"] = original
        else:
            os.environ.pop("DASHSCOPE_API_KEY", None)


# ── turn tests ────────────────────────────────────────────────────


def test_turn_success_when_no_error():
    from apps.backend.services.dashscope.realtime_client import QwenRealtimeTurn

    t = QwenRealtimeTurn()
    assert t.success is True
    assert t.user_transcript == ""
    assert t.assistant_audio_pcm == b""


def test_turn_failure_when_error_set():
    from apps.backend.services.dashscope.realtime_client import QwenRealtimeTurn

    t = QwenRealtimeTurn(error="timeout")
    assert t.success is False


# ── make_silent_pcm tests ─────────────────────────────────────────


def test_make_silent_pcm_half_second():
    from apps.backend.services.dashscope.realtime_client import make_silent_pcm

    pcm = make_silent_pcm(0.5)
    assert len(pcm) == 16000
    assert all(b == 0 for b in pcm)


def test_make_silent_pcm_one_second():
    from apps.backend.services.dashscope.realtime_client import make_silent_pcm

    pcm = make_silent_pcm(1.0)
    assert len(pcm) == 32000


# ── session.update payload test ───────────────────────────────────


def test_session_update_payload_structure():
    """session.update payload must match DashScope protocol."""
    from apps.backend.services.dashscope.realtime_client import (
        QwenRealtimeClient,
        QwenRealtimeConfig,
    )

    cfg = QwenRealtimeConfig(api_key="test-key", voice="Tina")
    client = QwenRealtimeClient(cfg)
    client._ws = MagicMock()

    sent: list[dict[str, Any]] = []
    client._ws.send = lambda data: sent.append(json.loads(data))

    client._send_session_update()

    assert len(sent) == 1
    payload = cast(dict[str, Any], sent[0])
    assert payload["type"] == "session.update"
    session = cast(dict[str, Any], payload["session"])
    assert "text" in session["modalities"]
    assert "audio" in session["modalities"]
    assert session["voice"] == "Tina"
    assert session["input_audio_format"] == "pcm"
    assert session["output_audio_format"] == "pcm"
    assert isinstance(session.get("instructions"), str)
    assert "You are Ally" in session["instructions"]
    assert session["turn_detection"] == {
        "type": "server_vad",
        "threshold": 0.5,
        "prefix_padding_ms": 300,
        "silence_duration_ms": 500,
        "interrupt_response": True,
    }
    assert session["input_audio_transcription"]["model"] == "qwen3-asr-flash-realtime"


def test_connect_captures_session_id_and_marks_connected():
    """connect() preserves session_id from handshake events."""
    from apps.backend.services.dashscope.realtime_client import (
        QwenRealtimeClient,
        QwenRealtimeConfig,
    )

    cfg = QwenRealtimeConfig(api_key="test-key")
    client = QwenRealtimeClient(cfg)
    fake_ws = MagicMock()

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(
            websocket,
            "create_connection",
            lambda url, header, timeout: fake_ws,
        )

        events = iter(
            [
                {"type": "session.created", "session": {"id": "sess-created"}},
                {"type": "session.updated", "session": {"id": "sess-updated"}},
            ]
        )
        mp.setattr(
            client, "_wait_for_event", lambda expected_type, timeout=15.0: next(events)
        )

        client.connect()

    assert client._connected is True
    assert client._ws is fake_ws
    assert client._session_id == "sess-updated"
    assert client._session_start_time is not None


def test_connect_closes_socket_if_handshake_fails():
    """connect() closes the socket if setup fails after opening."""
    from apps.backend.services.dashscope.realtime_client import (
        QwenRealtimeClient,
        QwenRealtimeConfig,
    )

    cfg = QwenRealtimeConfig(api_key="test-key")
    client = QwenRealtimeClient(cfg)
    fake_ws = MagicMock()

    def fake_wait(expected_type: str, timeout: float = 15.0) -> dict[str, object]:
        if expected_type == "session.created":
            return {"type": "session.created", "session": {"id": "sess-created"}}
        raise TimeoutError("session.updated timeout")

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(
            websocket,
            "create_connection",
            lambda url, header, timeout: fake_ws,
        )
        mp.setattr(client, "_wait_for_event", fake_wait)

        with pytest.raises(RuntimeError, match="session.updated timeout"):
            client.connect()

    fake_ws.close.assert_called_once()
    assert client._ws is None
    assert client._connected is False
    assert client._session_id is None


def test_connect_surfaces_session_update_failure_context():
    """connect() should expose model and voice on session.update failure."""
    from apps.backend.services.dashscope.realtime_client import (
        QwenRealtimeClient,
        QwenRealtimeConfig,
    )

    cfg = QwenRealtimeConfig(
        api_key="test-key", model="qwen3.5-omni-flash-realtime", voice="Tina"
    )
    client = QwenRealtimeClient(cfg)
    fake_ws = MagicMock()

    def fake_wait(expected_type: str, timeout: float = 15.0) -> dict[str, object]:
        if expected_type == "session.created":
            return {"type": "session.created", "session": {"id": "sess-created"}}
        raise RuntimeError("DashScope closed before session.updated")

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(
            websocket,
            "create_connection",
            lambda url, header, timeout: fake_ws,
        )
        mp.setattr(client, "_wait_for_event", fake_wait)

        with pytest.raises(
            RuntimeError,
            match="qwen3.5-omni-flash-realtime.*Tina.*api-ws/v1/realtime.*sess-created",
        ):
            client.connect()


# ── streaming order tests ─────────────────────────────────────────


def _capture_stream_events(
    audio_bytes: bytes, image_b64: str | None = None
) -> list[str]:
    """Helper: run _stream_audio with mock ws, return event type list."""
    from apps.backend.services.dashscope.realtime_client import (
        QwenRealtimeClient,
        QwenRealtimeConfig,
    )

    cfg = QwenRealtimeConfig(api_key="test-key", chunk_bytes=3200)
    client = QwenRealtimeClient(cfg)
    client._ws = MagicMock()
    client._connected = True
    client._session_start_time = time.monotonic()
    client._session_updated_confirmed = True

    event_types: list[str] = []
    client._ws.send = lambda data: event_types.append(json.loads(data)["type"])

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(
            client,
            "_wait_for_event",
            lambda expected_type, timeout=10.0: {"type": expected_type},
        )
        client._stream_audio(audio_bytes, image_b64)
    return event_types


def test_audio_sent_before_image():
    """Image must appear AFTER first audio chunk in event stream."""
    pcm = b"\x00\x01" * 1600  # 3200 bytes = 1 chunk
    image_b64 = base64.b64encode(b"fake_jpeg_data").decode()
    types = _capture_stream_events(pcm, image_b64)

    audio_idx = next(i for i, t in enumerate(types) if t == "input_audio_buffer.append")
    image_idx = next(i for i, t in enumerate(types) if t == "input_image_buffer.append")
    assert audio_idx < image_idx, "Audio must precede image"


def test_stream_audio_image_field_is_raw_base64():
    """image field in input_image_buffer.append must stay raw base64."""
    from apps.backend.services.dashscope.realtime_client import (
        QwenRealtimeClient,
        QwenRealtimeConfig,
    )

    config = QwenRealtimeConfig(
        api_key="test",
        model="qwen3.5-omni-flash-realtime",
    )
    client = QwenRealtimeClient(config)
    client._ws = MagicMock()
    client._connected = True
    client._session_start_time = time.monotonic()
    client._session_updated_confirmed = True

    sent_events: list[dict[str, Any]] = []
    client._ws.send = lambda data: sent_events.append(json.loads(data))

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(
            client,
            "_wait_for_event",
            lambda expected_type, timeout=10.0: {"type": expected_type},
        )
        fake_jpeg = b"\xff\xd8\xff\xe0" + b"\x00" * 100
        fake_b64 = base64.b64encode(fake_jpeg).decode("utf-8")
        client._stream_audio(b"\x00" * 3200, fake_b64)

    image_events = [
        e for e in sent_events if e.get("type") == "input_image_buffer.append"
    ]
    assert len(image_events) == 1, (
        "Expected exactly one input_image_buffer.append event"
    )
    val = image_events[0]["image"]
    assert not val.startswith("data:"), f"Expected raw base64, got: {val[:60]}"
    assert val == fake_b64, "Base64 payload must be unchanged"


def test_commit_sent_after_all_audio():
    """input_audio_buffer.commit must follow all audio appends."""
    pcm = b"\x00\x01" * 3200  # 6400 bytes = 2 chunks
    types = _capture_stream_events(pcm, None)

    commit_idx = types.index("input_audio_buffer.commit")
    audio_idxs = [i for i, t in enumerate(types) if t == "input_audio_buffer.append"]
    assert all(i < commit_idx for i in audio_idxs)


def test_response_create_after_commit():
    """response.create must follow input_audio_buffer.commit."""
    pcm = b"\x00\x01" * 1600
    types = _capture_stream_events(pcm, None)

    commit_idx = types.index("input_audio_buffer.commit")
    create_idx = types.index("response.create")
    assert commit_idx < create_idx


# ── reconnect tests ───────────────────────────────────────────────


def test_needs_reconnect_false_on_fresh_session():
    from apps.backend.services.dashscope.realtime_client import (
        QwenRealtimeClient,
        QwenRealtimeConfig,
    )

    cfg = QwenRealtimeConfig(api_key="test-key")
    client = QwenRealtimeClient(cfg)
    client._connected = True
    client._ws = MagicMock()
    client._session_start_time = time.monotonic()
    assert client.needs_reconnect() is False


def test_needs_reconnect_true_after_110_minutes():
    from apps.backend.services.dashscope.realtime_client import (
        QwenRealtimeClient,
        QwenRealtimeConfig,
        _SESSION_MAX_LIFETIME_S,
    )

    cfg = QwenRealtimeConfig(api_key="test-key")
    client = QwenRealtimeClient(cfg)
    client._connected = True
    client._ws = MagicMock()
    client._session_start_time = time.monotonic() - _SESSION_MAX_LIFETIME_S - 1
    assert client.needs_reconnect() is True


# ── response collection tests ─────────────────────────────────────


def test_collect_response_happy_path():
    """_collect_response assembles transcripts, audio, and usage."""
    from apps.backend.services.dashscope.realtime_client import (
        QwenRealtimeClient,
        QwenRealtimeConfig,
        QwenRealtimeTurn,
    )

    cfg = QwenRealtimeConfig(api_key="test-key")
    client = QwenRealtimeClient(cfg)
    result = QwenRealtimeTurn()
    audio_b64 = base64.b64encode(b"\x01\x02").decode("utf-8")
    events = iter(
        [
            {
                "type": "conversation.item.input_audio_transcription.completed",
                "transcript": "hello",
            },
            {"type": "response.audio_transcript.delta", "delta": "Hi "},
            {"type": "response.audio_transcript.delta", "delta": "there"},
            {"type": "response.audio.delta", "delta": audio_b64},
            {"type": "response.audio_transcript.done", "transcript": "Hi there"},
            {
                "type": "response.done",
                "response": {"status": "completed", "usage": {"input_tokens": 1}},
            },
        ]
    )

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(client, "_recv_event", lambda timeout=None: next(events))
        client._collect_response(result)

    assert result.success is True
    assert result.user_transcript == "hello"
    assert result.assistant_transcript == "Hi there"
    assert result.assistant_audio_pcm == b"\x01\x02"
    assert result.usage == {"input_tokens": 1}


@pytest.mark.parametrize("status", ["failed", "incomplete"])
def test_collect_response_marks_non_completed_status_as_error(status: str):
    """response.done with non-completed status should fail the turn."""
    from apps.backend.services.dashscope.realtime_client import (
        QwenRealtimeClient,
        QwenRealtimeConfig,
        QwenRealtimeTurn,
    )

    client = QwenRealtimeClient(QwenRealtimeConfig(api_key="test-key"))
    result = QwenRealtimeTurn()
    events = iter(
        [{"type": "response.done", "response": {"status": status, "usage": {}}}]
    )

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(client, "_recv_event", lambda timeout=None: next(events))
        client._collect_response(result)

    assert result.success is False
    assert result.error == f"Response finished with status: {status}"


def test_collect_response_returns_error_event_as_terminal():
    """error events should terminate the turn with an error."""
    from apps.backend.services.dashscope.realtime_client import (
        QwenRealtimeClient,
        QwenRealtimeConfig,
        QwenRealtimeTurn,
    )

    client = QwenRealtimeClient(QwenRealtimeConfig(api_key="test-key"))
    result = QwenRealtimeTurn()
    events = iter([{"type": "error", "message": "boom"}])

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(client, "_recv_event", lambda timeout=None: next(events))
        client._collect_response(result)

    assert result.success is False
    assert "boom" in (result.error or "")


def test_collect_response_errors_if_deadline_expires_without_response_done():
    """Non-terminal events until deadline should not count as success."""
    import apps.backend.services.dashscope.realtime_client as rc

    client = rc.QwenRealtimeClient(
        rc.QwenRealtimeConfig(api_key="test-key", response_timeout_s=0.01)
    )
    result = rc.QwenRealtimeTurn()
    monotonic_values = iter([0.0, 0.0, 0.0, 0.02])

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(rc.time, "monotonic", lambda: next(monotonic_values))
        mp.setattr(
            client,
            "_recv_event",
            lambda timeout=None: {
                "type": "response.audio_transcript.delta",
                "delta": "Hi",
            },
        )
        client._collect_response(result)

    assert result.success is False
    assert result.error == "Response ended before response.done"


def test_cancel_response_sends_event():
    """cancel_response() must send response.cancel to DashScope."""
    from apps.backend.services.dashscope.realtime_client import (
        QwenRealtimeClient,
        QwenRealtimeConfig,
    )

    config = QwenRealtimeConfig(api_key="test", model="qwen3.5-omni-flash-realtime")
    client = QwenRealtimeClient(config)
    client._connected = True
    client._response_active = True
    client._ws = MagicMock()
    client.cancel_response()
    sent = json.loads(client._ws.send.call_args[0][0])
    assert sent["type"] == "response.cancel"


def test_cancel_response_noop_when_not_connected():
    """cancel_response() must not raise when disconnected."""
    from apps.backend.services.dashscope.realtime_client import (
        QwenRealtimeClient,
        QwenRealtimeConfig,
    )

    config = QwenRealtimeConfig(api_key="test", model="qwen3.5-omni-flash-realtime")
    client = QwenRealtimeClient(config)
    client._connected = False
    client._ws = None
    client.cancel_response()


def test_cancel_response_noop_when_no_active_response():
    """cancel_response() must not send when no upstream response is active."""
    from apps.backend.services.dashscope.realtime_client import (
        QwenRealtimeClient,
        QwenRealtimeConfig,
    )

    config = QwenRealtimeConfig(api_key="test", model="qwen3.5-omni-flash-realtime")
    client = QwenRealtimeClient(config)
    client._connected = True
    client._response_active = False
    client._ws = MagicMock()
    client.cancel_response()
    client._ws.send.assert_not_called()


def test_collect_response_handles_response_cancelled():
    """collect_response() must stop collecting on response.cancelled."""
    from apps.backend.services.dashscope.realtime_client import (
        QwenRealtimeClient,
        QwenRealtimeConfig,
        QwenRealtimeTurn,
    )

    config = QwenRealtimeConfig(api_key="test", model="qwen3.5-omni-flash-realtime")
    client = QwenRealtimeClient(config)
    result = QwenRealtimeTurn()
    events = iter(
        [
            {"type": "response.audio.delta", "delta": "AAAA"},
            {"type": "response.cancelled"},
        ]
    )

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(client, "_recv_event", lambda timeout=None: next(events))
        client._collect_response(result)

    assert result.error is None
    assert result.assistant_audio_pcm is not None


# ── compress_image tests ──────────────────────────────────────────


def test_compress_image_returns_valid_jpeg_base64():
    """compress_image_for_realtime returns base64 JPEG under 500KB."""
    import numpy as np

    from apps.backend.services.dashscope.realtime_client import (
        compress_image_for_realtime,
    )

    img = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
    result = compress_image_for_realtime(img)
    assert result is not None
    decoded = base64.b64decode(result)
    assert len(decoded) <= 500 * 1024
    assert decoded[:2] == b"\xff\xd8"  # JPEG magic bytes


def test_compress_image_returns_none_on_invalid_input():
    """compress_image_for_realtime returns None on bad input."""
    from apps.backend.services.dashscope.realtime_client import (
        compress_image_for_realtime,
    )

    result = compress_image_for_realtime("nonexistent_path.jpg")
    assert result is None
