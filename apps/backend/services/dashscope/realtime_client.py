"""
Ally Vision v2 — DashScope Qwen Omni Realtime WebSocket client.

Confirmed protocol from DashScope docs:
  Endpoint: wss://dashscope-intl.aliyuncs.com/api-ws/v1/realtime?model={model}
  Auth:     Authorization: Bearer {api_key}
  Audio IN: PCM 16kHz 16-bit mono, 3200-byte chunks (100ms)
  Audio OUT: PCM 24kHz 16-bit mono (example/default — not formal guarantee)
  Image:    JPEG base64 < 500KB, sent AFTER first audio chunk
  Session:  max 120 minutes, reconnect = full new session

UNCONFIRMED:
  - 24kHz output is example behavior, not formal guarantee
  - 3200 bytes is documented example, not hard requirement
  - No session resume after expiry (reconnect creates new session)
"""

from __future__ import annotations

import asyncio
import base64
from collections import deque
import io
import json
import logging
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Optional

import websocket

logger = logging.getLogger("qwen-realtime-client")

# Session safety margin: reconnect at 110 min (before 120 min expiry)
_SESSION_MAX_LIFETIME_S = 110 * 60
_SESSION_UPDATED_TIMEOUT_S = 5.0
_INPUT_TRANSCRIPT_TIMEOUT_S = 6.0


def detect_and_clean_transcript(text: str) -> tuple[str, str]:
    """Return (cleaned_text, detected_language_code)."""
    if not text or not text.strip():
        return text, "unknown"

    for ch in text:
        cp = ord(ch)
        if 0x0C80 <= cp <= 0x0CFF:
            return text, "kn"
        if 0x0900 <= cp <= 0x097F:
            return text, "hi"
        if 0x0B80 <= cp <= 0x0BFF:
            return text, "ta"

    suspicious = False
    for ch in text:
        cp = ord(ch)
        if 0x4E00 <= cp <= 0x9FFF:
            suspicious = True
            break
        if 0x0E00 <= cp <= 0x0E7F:
            suspicious = True
            break
        if 0x0102 <= cp <= 0x01B0:
            suspicious = True
            break

    if suspicious:
        logger.warning(
            "Transcript appears to be wrong language: %r — likely mis-transcription of Kannada/Hindi",
            text[:50],
        )
        return "", "wrong_lang"

    return text, "en"


class SessionState(str, Enum):
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    READY = "ready"
    STREAMING = "streaming"
    IDLE = "idle"


class RecoverableRealtimeError(RuntimeError):
    """Raised when the current realtime session is recoverable via reconnect."""


class TurnCommitFailedError(RuntimeError):
    """Raised when the current turn failed before a response could be created."""


def _default_realtime_model() -> str:
    from shared.config.settings import QWEN_REALTIME_MODEL

    return QWEN_REALTIME_MODEL


def _default_realtime_endpoint() -> str:
    from shared.config.settings import DASHSCOPE_REALTIME_URL

    return DASHSCOPE_REALTIME_URL


def _default_transcription_model() -> str:
    from shared.config.settings import QWEN_TRANSCRIPTION_MODEL

    return QWEN_TRANSCRIPTION_MODEL


def _default_realtime_voice() -> str:
    from shared.config.settings import QWEN_OMNI_VOICE, QWEN_REALTIME_MODEL

    return QWEN_OMNI_VOICE or default_voice_for_model(QWEN_REALTIME_MODEL)


def default_voice_for_model(model: str) -> str:
    """Return the safest default voice for a realtime model family."""
    from shared.config.settings import QWEN_OMNI_VOICE

    return QWEN_OMNI_VOICE or "Tina"


def _wire_transcription_model(model: str) -> str:
    if model == "gummy-realtime-v1":
        logger.warning(
            "Transcription model %s is not compatible with DashScope realtime session.update — using qwen3-asr-flash-realtime on the wire",
            model,
        )
        return "qwen3-asr-flash-realtime"
    return model


@dataclass
class QwenRealtimeConfig:
    """Configuration for QwenRealtimeClient."""

    api_key: str
    model: str = field(default_factory=_default_realtime_model)
    endpoint: str = field(default_factory=_default_realtime_endpoint)
    voice: str = field(default_factory=_default_realtime_voice)
    instructions: str = (
        "You are Ally, an AI assistant for visually impaired users. "
        "You have a live camera feed. "
        "When a message contains [Camera sees], it contains a real-time description of what the camera currently sees. "
        "Use it to answer visual questions. Never say you cannot see — always use the camera context provided to you. "
        "If no [Camera sees] context is provided, do not invent visual details. "
        "You support 113 spoken languages including English, Hindi, and Kannada. "
        "The user is from Karnataka, India. They speak Kannada (ಕನ್ನಡ), Hindi (हिंदी), and English. "
        "They do NOT speak Chinese, Vietnamese, Thai, Japanese, or other East/Southeast Asian languages. "
        "Always detect the user's actual spoken language and respond in the SAME language. "
        "If the user's speech is transcribed in Chinese, Vietnamese, Thai, or any other unexpected script, ignore that transcription and ask the user to repeat in Kannada, Hindi, or English. "
        "Never respond in Chinese, Thai, Vietnamese, or Japanese. "
        "If language is unclear, default to Kannada. "
        "Never switch languages unless explicitly asked. "
        "You have access to vision (camera frames), memory (stored facts), and function calling. "
        "Respond concisely — blind users cannot see the screen. "
        "For medicine safety questions, be extremely careful and always recommend consulting a doctor."
    )
    transcription_model: str = field(default_factory=_default_transcription_model)
    audio_in_rate: int = 16000
    audio_out_rate: int = 24000
    chunk_bytes: int = 3200
    response_timeout_s: float = 60.0

    @classmethod
    def from_settings(cls) -> "QwenRealtimeConfig":
        """Create config from environment / settings module."""
        from shared.config import settings as settings_module

        return cls(
            api_key=settings_module.get_api_key(),
            model=settings_module.QWEN_REALTIME_MODEL,
            endpoint=settings_module.DASHSCOPE_REALTIME_URL,
            voice=(
                settings_module.QWEN_OMNI_VOICE
                or default_voice_for_model(settings_module.QWEN_REALTIME_MODEL)
            ),
            transcription_model=settings_module.QWEN_TRANSCRIPTION_MODEL,
        )


@dataclass
class QwenRealtimeTurn:
    """Result of one completed realtime turn."""

    user_transcript: str = ""
    assistant_transcript: str = ""
    assistant_audio_pcm: bytes = field(default_factory=bytes)
    usage: dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None
    response_cancelled: bool = False
    assistant_audio_bytes: int = 0

    @property
    def success(self) -> bool:
        return self.error is None


class QwenRealtimeClient:
    """
    Synchronous WebSocket client for DashScope Qwen Omni Realtime.

    Usage:
        config = QwenRealtimeConfig.from_settings()
        client = QwenRealtimeClient(config)
        client.connect()
        result = client.send_audio_turn(pcm_bytes, image_b64)
        client.close()

    Thread safety: send_audio_turn is blocking.
    Use async_send_audio_turn inside asyncio code.
    """

    def __init__(self, config: QwenRealtimeConfig) -> None:
        self._config = config
        self._ws: Optional[websocket.WebSocket] = None
        self._connected: bool = False
        self._session_start_time: Optional[float] = None
        self._session_started_at: Optional[float] = None
        self._session_id: Optional[str] = None
        self._response_active: bool = False
        self._session_updated_confirmed: bool = False
        self._session_update_sent_at: Optional[float] = None
        self._buffered_events: deque[dict[str, Any]] = deque()
        self._state: SessionState = SessionState.DISCONNECTED
        self._turn_started_at: Optional[float] = None
        self._last_session_updated_elapsed_ms: int = 0
        self._response_cancelled: bool = False
        self._discarded_audio_chunks: int = 0
        self._last_commit_failed: bool = False
        self._last_commit_error_message: str = ""
        self._total_audio_bytes_appended: int = 0

    # ── connection lifecycle ──────────────────────────────────

    def connect(self) -> None:
        """Open WebSocket, configure session, wait until ready."""
        self._state = SessionState.CONNECTING
        url = f"{self._config.endpoint}?model={self._config.model}"
        headers = [f"Authorization: Bearer {self._config.api_key}"]
        logger.info(
            "Connecting to DashScope realtime: model=%s",
            self._config.model,
        )
        self._ws = websocket.create_connection(url, header=headers, timeout=30)
        try:
            created_event = self._wait_for_event("session.created", timeout=15.0)
            self._session_id = self._extract_session_id(created_event)
            self._session_updated_confirmed = False
            self._session_update_sent_at = time.monotonic()
            self._send_session_update()
            try:
                self._wait_for_session_updated(timeout=_SESSION_UPDATED_TIMEOUT_S)
            except Exception as exc:
                session_context = (
                    f" session_id={self._session_id}" if self._session_id else ""
                )
                raise RuntimeError(
                    "DashScope session.update failed for "
                    f"model={self._config.model} voice={self._config.voice} "
                    f"endpoint={self._config.endpoint}{session_context}: {exc}"
                ) from exc
            self._connected = True
            self._session_start_time = time.monotonic()
            self._session_started_at = self._session_start_time
            self._state = SessionState.IDLE
            logger.info(
                "Realtime session ready: voice=%s model=%s session_id=%s",
                self._config.voice,
                self._config.model,
                self._session_id,
            )
        except Exception:
            self.close()
            self._session_start_time = None
            self._session_id = None
            raise

    def close(self) -> None:
        """Close WebSocket gracefully."""
        ws = self._ws
        if ws is None or not getattr(ws, "connected", False):
            self._ws = None
            self._connected = False
            self._response_active = False
            self._response_cancelled = False
            self._discarded_audio_chunks = 0
            self._session_start_time = None
            self._session_started_at = None
            self._session_updated_confirmed = False
            self._session_update_sent_at = None
            self._buffered_events.clear()
            self._state = SessionState.DISCONNECTED
            return

        try:
            ws.close()
        except Exception:
            pass
        finally:
            self._ws = None
            self._connected = False
            self._response_active = False
            self._response_cancelled = False
            self._discarded_audio_chunks = 0
            self._session_start_time = None
            self._session_started_at = None
            self._session_updated_confirmed = False
            self._session_update_sent_at = None
            self._buffered_events.clear()
            self._state = SessionState.DISCONNECTED
        logger.info("Realtime session closed")

    async def async_close(self) -> None:
        self.close()

    def is_connected(self) -> bool:
        """True when websocket transport is alive and session is usable."""
        ws = self._ws
        return bool(
            self._connected
            and ws is not None
            and getattr(ws, "connected", False)
            and self._state is not SessionState.DISCONNECTED
        )

    def has_active_response(self) -> bool:
        return self._response_active

    def was_response_cancelled(self) -> bool:
        return self._response_cancelled

    def has_buffered_response_events(self) -> bool:
        return any(
            isinstance(event, dict)
            and str(event.get("type", "")).startswith("response.")
            for event in self._buffered_events
        )

    def consume_last_commit_failure(self) -> str | None:
        if not self._last_commit_failed:
            return None
        message = self._last_commit_error_message or "Voice turn failed"
        self._last_commit_failed = False
        self._last_commit_error_message = ""
        return message

    def session_needs_reconnect(self) -> bool:
        """True when session is near the 120-minute lifetime limit."""
        if self._session_started_at is None:
            return True
        elapsed = time.monotonic() - self._session_started_at
        logger.info(
            "DashScope session age: %.1fmin — reconnect threshold: 110min",
            elapsed / 60.0,
        )
        return elapsed >= _SESSION_MAX_LIFETIME_S

    def needs_reconnect(self) -> bool:
        """Backward-compatible alias for expiry checks."""
        return self.session_needs_reconnect()

    def reconnect(self) -> None:
        """Full reconnect — new session, context NOT preserved."""
        logger.info("Reconnecting realtime session (new session)")
        self._session_updated_confirmed = False
        self._session_update_sent_at = None
        self._buffered_events.clear()
        self.close()
        self.connect()

    def ensure_connected(self) -> None:
        """Connect if not connected; reconnect if near expiry."""
        if not self.is_connected():
            self.connect()
        elif self.session_needs_reconnect():
            self.reconnect()
        elif not self._session_updated_confirmed:
            self._wait_for_session_updated(timeout=_SESSION_UPDATED_TIMEOUT_S)

    async def async_connect(self) -> None:
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, self.connect)

    async def async_reconnect(self) -> None:
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, self.reconnect)

    # ── main turn ─────────────────────────────────────────────

    def send_audio_turn(
        self,
        audio_pcm: bytes,
        image_jpeg_b64: Optional[str] = None,
        instructions: Optional[str] = None,
    ) -> QwenRealtimeTurn:
        """
        Send one audio (+ optional image) turn and collect response.

        audio_pcm:       raw PCM 16kHz 16-bit mono bytes
        image_jpeg_b64:  JPEG base64 string, < 500KB before encoding
                         IMPORTANT: sent after first audio chunk
        instructions:    optional per-turn instruction override

        Returns QwenRealtimeTurn with transcript, audio PCM, usage.
        """
        self.ensure_connected()

        result = QwenRealtimeTurn()
        try:
            if instructions is not None:
                self.update_instructions(instructions=instructions)
            user_transcript = self.prepare_audio_turn(audio_pcm, image_jpeg_b64)
            response = self.create_response_for_prepared_turn()
            if not response.user_transcript:
                response.user_transcript = user_transcript or ""
            result = response
        except Exception as exc:
            logger.error("Realtime turn failed: %s", exc)
            result.error = str(exc)
        finally:
            if instructions is not None and self._connected and self._ws is not None:
                try:
                    self.update_instructions()
                except Exception as exc:
                    logger.warning(
                        "Failed to restore default instructions after turn: %s",
                        exc,
                    )
                    self.close()

        return result

    async def async_send_audio_turn(
        self,
        audio_pcm: bytes,
        image_jpeg_b64: Optional[str] = None,
        instructions: Optional[str] = None,
    ) -> QwenRealtimeTurn:
        """Async wrapper for send_audio_turn via thread executor."""
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            None,
            lambda: self.send_audio_turn(audio_pcm, image_jpeg_b64, instructions),
        )

    def prepare_audio_turn(
        self,
        audio_pcm: bytes,
        image_jpeg_b64: Optional[str] = None,
    ) -> str | None:
        """Stream a turn, commit it, and wait for the input transcript."""
        self.ensure_connected()
        self._last_commit_failed = False
        self._last_commit_error_message = ""
        self._stream_audio(audio_pcm, image_jpeg_b64, auto_create_response=False)
        return self._wait_for_input_transcript(timeout=_INPUT_TRANSCRIPT_TIMEOUT_S)

    async def async_prepare_audio_turn(
        self,
        audio_pcm: bytes,
        image_jpeg_b64: Optional[str] = None,
    ) -> str | None:
        loop = asyncio.get_running_loop()
        try:
            return await loop.run_in_executor(
                None,
                lambda: self.prepare_audio_turn(audio_pcm, image_jpeg_b64),
            )
        except TurnCommitFailedError:
            await self.async_reconnect()
            return None
        except RecoverableRealtimeError:
            await self.async_reconnect()
            return await loop.run_in_executor(
                None,
                lambda: self.prepare_audio_turn(audio_pcm, image_jpeg_b64),
            )

    def update_instructions(self, instructions: Optional[str] = None) -> None:
        """Apply session instructions and wait until DashScope acknowledges them."""
        self.ensure_connected()
        self._session_updated_confirmed = False
        self._session_update_sent_at = time.monotonic()
        self._send_session_update(instructions=instructions)
        self._wait_for_session_updated(timeout=_SESSION_UPDATED_TIMEOUT_S)

    @staticmethod
    def _build_response_create_payload(
        instructions: Optional[str] = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {"type": "response.create"}
        if instructions:
            payload["response"] = {"instructions": instructions}
        return payload

    @staticmethod
    def _build_user_message_item_payload(text: str) -> dict[str, Any]:
        return {
            "type": "conversation.item.create",
            "item": {
                "type": "message",
                "role": "user",
                "content": [
                    {
                        "type": "input_text",
                        "text": text,
                    }
                ],
            },
        }

    async def async_update_instructions(
        self, instructions: Optional[str] = None
    ) -> None:
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, lambda: self.update_instructions(instructions))

    def create_response_for_prepared_turn(
        self,
        instructions: Optional[str] = None,
        user_input_text: Optional[str] = None,
    ) -> QwenRealtimeTurn:
        """Create a response for already-committed input and collect output."""
        self.ensure_connected()
        result = QwenRealtimeTurn()
        self._response_cancelled = False
        self._discarded_audio_chunks = 0
        if not any(
            (event.get("type", "")).startswith("response.")
            for event in self._buffered_events
        ):
            if user_input_text:
                self._send_event(self._build_user_message_item_payload(user_input_text))
            self._send_event(self._build_response_create_payload(instructions))
        self._collect_response(result)
        return result

    def create_response_for_prepared_turn_streaming(
        self,
        on_audio_chunk: Callable[[bytes], None],
        instructions: Optional[str] = None,
        user_input_text: Optional[str] = None,
    ) -> QwenRealtimeTurn:
        """Create a response and forward audio deltas immediately."""
        self.ensure_connected()
        result = QwenRealtimeTurn()
        self._response_cancelled = False
        self._discarded_audio_chunks = 0
        if not any(
            (event.get("type", "")).startswith("response.")
            for event in self._buffered_events
        ):
            if user_input_text:
                self._send_event(self._build_user_message_item_payload(user_input_text))
            self._send_event(self._build_response_create_payload(instructions))
        self._collect_response(result, on_audio_chunk=on_audio_chunk)
        return result

    async def async_create_response_for_prepared_turn(
        self,
        instructions: Optional[str] = None,
        user_input_text: Optional[str] = None,
    ) -> QwenRealtimeTurn:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            None,
            lambda: self.create_response_for_prepared_turn(
                instructions,
                user_input_text,
            ),
        )

    async def async_create_response_for_prepared_turn_streaming(
        self,
        on_audio_chunk: Callable[[bytes], None],
        instructions: Optional[str] = None,
        user_input_text: Optional[str] = None,
    ) -> QwenRealtimeTurn:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            None,
            lambda: self.create_response_for_prepared_turn_streaming(
                on_audio_chunk,
                instructions,
                user_input_text,
            ),
        )

    # ── internal helpers ──────────────────────────────────────

    @staticmethod
    def _extract_session_id(event: dict[str, Any]) -> Optional[str]:
        session = event.get("session")
        if isinstance(session, dict):
            session_id = session.get("id") or session.get("session_id")
            if isinstance(session_id, str):
                return session_id
        event_session_id = event.get("session_id")
        if isinstance(event_session_id, str):
            return event_session_id
        return None

    def _require_ws(self) -> websocket.WebSocket:
        if self._ws is None:
            raise RuntimeError("Realtime WebSocket is not connected")
        return self._ws

    def _buffer_event(self, event: dict[str, Any]) -> None:
        self._buffered_events.append(event)

    def _send_event(self, payload: dict[str, Any]) -> None:
        payload = dict(payload)
        payload["event_id"] = "event_" + uuid.uuid4().hex
        self._require_ws().send(json.dumps(payload))

    def cancel_response(self) -> None:
        """Send response.cancel to DashScope to stop current output."""
        if not self._response_active:
            logger.debug("Cancel request ignored — no active response")
            return
        if not self._connected or self._ws is None:
            return
        try:
            self._response_cancelled = True
            self._send_event({"type": "response.cancel"})
            self._response_active = False
            logger.info("response.cancel sent to DashScope")
        except Exception as exc:
            logger.warning("cancel_response failed: %s", exc)

    @staticmethod
    def _extract_error_message(event: dict[str, Any]) -> str:
        error = event.get("error")
        if isinstance(error, dict):
            message = error.get("message")
            if isinstance(message, str) and message.strip():
                return message
            error_type = error.get("type")
            if isinstance(error_type, str) and error_type.strip():
                return error_type
        message = event.get("message")
        if isinstance(message, str) and message.strip():
            return message
        return str(event)

    @classmethod
    def _is_recoverable_session_error(cls, message: str) -> bool:
        lowered = message.lower()
        return (
            "none active response" in lowered
            or "invalid_request_error" in lowered
        )

    def _recv_event(self, timeout: Optional[float] = None) -> dict[str, Any]:
        if self._buffered_events:
            return self._buffered_events.popleft()
        return self._recv_ws_event(timeout=timeout)

    def _recv_ws_event(self, timeout: Optional[float] = None) -> dict[str, Any]:
        ws = self._require_ws()
        if timeout is not None:
            ws.settimeout(timeout)
        raw = ws.recv()
        # Guard against empty body (idle session)
        if not raw or not raw.strip():
            logger.warning("Empty WebSocket message received, skipping")
            return {}
        event = json.loads(raw)
        session_id = self._extract_session_id(event)
        if session_id is not None:
            self._session_id = session_id
        return event

    def _wait_for_session_updated(
        self, timeout: float = _SESSION_UPDATED_TIMEOUT_S
    ) -> None:
        if self._session_updated_confirmed:
            return

        started_at = self._session_update_sent_at or time.monotonic()
        try:
            updated_event = self._wait_for_event("session.updated", timeout=timeout)
        except Exception as exc:
            self.close()
            raise RuntimeError(
                f"Retryable session.updated timeout after {timeout:.1f}s: {exc}"
            ) from exc

        self._session_id = self._extract_session_id(updated_event) or self._session_id
        self._session_updated_confirmed = True
        elapsed_ms = int((time.monotonic() - started_at) * 1000)
        self._last_session_updated_elapsed_ms = elapsed_ms
        logger.info(
            "session.updated confirmed in %dms — safe to stream audio",
            elapsed_ms,
        )

    def _wait_for_event(
        self,
        expected_type: str,
        timeout: float = 20.0,
    ) -> dict[str, Any]:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            remaining = max(0.5, deadline - time.monotonic())
            try:
                event = self._recv_ws_event(timeout=remaining)
            except websocket.WebSocketTimeoutException:
                break
            t = event.get("type", "")
            if t == expected_type:
                return event
            if t == "error":
                message = self._extract_error_message(event)
                if expected_type == "input_audio_buffer.committed":
                    error = event.get("error")
                    code = error.get("code") if isinstance(error, dict) else "unknown"
                    logger.error(
                        "DashScope InternalError on buffer commit: %s — %s",
                        code,
                        message,
                    )
                    self._last_commit_failed = True
                    self._last_commit_error_message = message
                    self._session_updated_confirmed = False
                    self._response_active = False
                    self._response_cancelled = False
                    raise TurnCommitFailedError(message)
                if self._is_recoverable_session_error(message):
                    logger.error(
                        "DashScope session error: %s — triggering reconnect",
                        message,
                    )
                    self._session_updated_confirmed = False
                    self._response_active = False
                    self._response_cancelled = False
                    raise RecoverableRealtimeError(message)
                raise RuntimeError(
                    f"Server error waiting for {expected_type}: {event}"
                )
            if expected_type == "session.updated" and t.startswith("response."):
                self._buffer_event(event)
                logger.debug(
                    "Buffering event type=%s while waiting for %s",
                    t,
                    expected_type,
                )
                continue
            if expected_type == "input_audio_buffer.committed":
                self._buffer_event(event)
                logger.debug(
                    "Buffering event type=%s while waiting for %s",
                    t,
                    expected_type,
                )
                continue
            logger.debug(
                "Skipping event type=%s while waiting for %s",
                t,
                expected_type,
            )
        raise TimeoutError(f"Timed out waiting for event: {expected_type}")

    def _send_session_update(self, instructions: Optional[str] = None) -> None:
        self._send_event(
            {
                "type": "session.update",
                "session": {
                    "modalities": ["text", "audio"],
                    "voice": self._config.voice,
                    "instructions": instructions or self._config.instructions,
                    "input_audio_format": "pcm",
                    "output_audio_format": "pcm",
                    "input_audio_transcription": {
                        "model": _wire_transcription_model(
                            self._config.transcription_model
                        ),
                    },
                    "turn_detection": None,
                },
            }
        )

    def _wait_for_input_transcript(
        self,
        timeout: float = _INPUT_TRANSCRIPT_TIMEOUT_S,
    ) -> str | None:
        """Wait for current-turn transcription before creating a response."""
        deadline = time.monotonic() + timeout
        deferred_events: list[dict[str, Any]] = []

        def _restore_deferred_events() -> None:
            while deferred_events:
                self._buffered_events.appendleft(deferred_events.pop())

        while time.monotonic() < deadline:
            remaining = max(0.5, deadline - time.monotonic())
            try:
                event = self._recv_event(timeout=remaining)
            except websocket.WebSocketTimeoutException:
                break

            if not event:
                continue

            event_type = event.get("type", "")
            if event_type == "conversation.item.input_audio_transcription.completed":
                transcript = event.get("transcript", "")
                text = transcript if isinstance(transcript, str) else ""
                cleaned_text, detected_lang = detect_and_clean_transcript(text)
                logger.info(
                    'input_audio_transcription.completed received — transcript: "%s" cleaned: "%s" lang=%s',
                    text,
                    cleaned_text,
                    detected_lang,
                )
                _restore_deferred_events()
                return cleaned_text
            if event_type == "error":
                _restore_deferred_events()
                raise RuntimeError(f"Server error waiting for transcript: {event}")
            if event_type.startswith("response."):
                deferred_events.append(event)
                logger.debug(
                    "Buffering event type=%s while waiting for transcript",
                    event_type,
                )
                continue

            logger.debug(
                "Skipping event type=%s while waiting for transcript", event_type
            )

        _restore_deferred_events()
        logger.warning(
            "input_audio_transcription.completed not received in 6s — continuing without transcript"
        )
        return None

    def _stream_audio(
        self,
        pcm_bytes: bytes,
        image_jpeg_b64: Optional[str],
        auto_create_response: bool = True,
    ) -> None:
        """Stream PCM chunks and optional image, then commit."""
        self.ensure_connected()
        self._state = SessionState.STREAMING
        self._turn_started_at = time.monotonic()
        chunk = self._config.chunk_bytes
        self._total_audio_bytes_appended = 0
        image_sent = False

        for i in range(0, len(pcm_bytes), chunk):
            audio_chunk = pcm_bytes[i : i + chunk]
            self._total_audio_bytes_appended += len(audio_chunk)
            self._send_event(
                {
                    "type": "input_audio_buffer.append",
                    "audio": base64.b64encode(audio_chunk).decode("utf-8"),
                }
            )
            # Image must be sent AFTER first audio chunk
            if image_jpeg_b64 is not None and not image_sent:
                logger.debug(
                    "Sending image: size=%d bytes, prefix=%s",
                    len(image_jpeg_b64),
                    image_jpeg_b64[:30],
                )
                self._send_event(
                    {
                        "type": "input_image_buffer.append",
                        "image": image_jpeg_b64,
                    }
                )
                image_sent = True
                logger.debug(
                    "Image sent in supported audio-first order — size=%d chars",
                    len(image_jpeg_b64),
                )

        if self._total_audio_bytes_appended == 0:
            logger.warning("Skipping commit — empty audio buffer (0 bytes appended)")
            self._state = SessionState.IDLE
            self._turn_started_at = None
            return

        self._send_event({"type": "input_audio_buffer.commit"})
        self._wait_for_event("input_audio_buffer.committed", timeout=10.0)
        if self._last_commit_failed:
            self._state = SessionState.IDLE
            self._turn_started_at = None
            return
        if auto_create_response:
            self._send_event({"type": "response.create"})
        logger.debug(
            "Streamed %d bytes audio, image=%s",
            len(pcm_bytes),
            "yes" if image_jpeg_b64 else "no",
        )
        self._state = SessionState.READY

    def _collect_response(
        self,
        result: QwenRealtimeTurn,
        on_audio_chunk: Optional[Callable[[bytes], None]] = None,
    ) -> None:
        """Collect server events until response.done."""
        audio_chunks = bytearray()
        text_deltas: list[str] = []
        deadline = time.monotonic() + self._config.response_timeout_s
        saw_response_done = False
        saw_response_cancelled = False
        first_audio_delta_logged = False

        while time.monotonic() < deadline:
            remaining = max(0.5, deadline - time.monotonic())
            try:
                event = self._recv_event(timeout=remaining)
            except websocket.WebSocketTimeoutException:
                result.error = (
                    f"Response timed out after {self._config.response_timeout_s}s"
                )
                return

            if not event:
                continue  # empty message guard

            t = event.get("type", "")

            if t == "conversation.item.input_audio_transcription.completed":
                transcript = event.get("transcript", "")
                if isinstance(transcript, str):
                    result.user_transcript = detect_and_clean_transcript(transcript)[0]

            elif t == "response.created":
                self._response_active = True

            elif t == "response.audio_transcript.delta":
                text_deltas.append(event.get("delta", ""))

            elif t == "response.audio_transcript.done":
                result.assistant_transcript = event.get(
                    "transcript", "".join(text_deltas)
                )

            elif t == "response.audio.delta":
                delta = event.get("delta")
                if isinstance(delta, str):
                    delta_bytes = base64.b64decode(delta)
                    if self._response_cancelled:
                        self._discarded_audio_chunks += 1
                        continue
                    result.assistant_audio_bytes += len(delta_bytes)
                    if (
                        not first_audio_delta_logged
                        and self._turn_started_at is not None
                    ):
                        logger.info(
                            "first audio delta received — turn latency: %dms",
                            int((time.monotonic() - self._turn_started_at) * 1000),
                        )
                        first_audio_delta_logged = True
                    if on_audio_chunk is not None:
                        on_audio_chunk(delta_bytes)
                    audio_chunks.extend(delta_bytes)

            elif t == "response.audio.done":
                pass  # audio.delta already collected

            elif t in {"input_audio_buffer.speech_started", "input_speech_started"}:
                if self._response_active and not self._response_cancelled:
                    self.cancel_response()
                    logger.info("Barge-in detected — response cancelled")

            elif t == "response.cancelled":
                logger.info("Response cancelled by DashScope")
                saw_response_cancelled = True
                result.response_cancelled = True
                self._response_active = False
                self._state = SessionState.IDLE
                result.error = None
                logger.info(
                    "Audio stream cancelled — %d chunks discarded",
                    self._discarded_audio_chunks,
                )
                break

            elif t == "response.done":
                saw_response_done = True
                self._response_active = False
                self._state = SessionState.IDLE
                response = event.get("response", {})
                if isinstance(response, dict):
                    usage = response.get("usage", {})
                    if isinstance(usage, dict):
                        result.usage = usage
                    status = response.get("status")
                    if (
                        isinstance(status, str)
                        and self._response_cancelled
                        and status in {"cancelled", "incomplete"}
                    ):
                        saw_response_cancelled = True
                        result.response_cancelled = True
                        result.error = None
                        logger.info(
                            "Audio stream cancelled — %d chunks discarded",
                            self._discarded_audio_chunks,
                        )
                    elif isinstance(status, str) and status != "completed":
                        result.error = f"Response finished with status: {status}"
                if not result.assistant_transcript:
                    result.assistant_transcript = "".join(text_deltas)
                break

            elif t == "error":
                self._response_active = False
                result.error = str(event)
                logger.error("Server error event: %s", event)
                return

        if (
            not saw_response_done
            and not saw_response_cancelled
            and result.error is None
        ):
            result.error = "Response ended before response.done"
            self._response_active = False
            self._state = SessionState.IDLE

        result.assistant_audio_pcm = bytes(audio_chunks)
        self._turn_started_at = None
        logger.info(
            "Turn complete: transcript=%d chars audio=%d bytes",
            len(result.assistant_transcript),
            result.assistant_audio_bytes,
        )


# ── utility functions ─────────────────────────────────────────────


def make_silent_pcm(duration_s: float = 0.5) -> bytes:
    """
    Generate silent PCM audio for image-only Qwen turns.

    DashScope realtime requires audio before image.
    Use silence when only a vision query is needed.

    Returns: raw PCM 16kHz 16-bit mono bytes (all zeros)
    """
    n_samples = int(duration_s * 16000)
    return b"\x00\x00" * n_samples


def compress_image_for_realtime(
    image_input: Any,
    max_bytes: int = 500 * 1024,
) -> Optional[str]:
    """
    Convert image to JPEG base64 under max_bytes.

    Accepts: numpy array, PIL Image, or file path string.
    Returns: base64 string, or None if compression fails.
    """
    try:
        from PIL import Image as PILImage

        if isinstance(image_input, str):
            img = PILImage.open(image_input).convert("RGB")
        elif hasattr(image_input, "save"):
            img = image_input.convert("RGB")
        else:
            import numpy as np

            arr = np.asarray(image_input)
            if arr.dtype != np.uint8:
                arr = (arr * 255).clip(0, 255).astype(np.uint8)
            img = PILImage.fromarray(arr).convert("RGB")

        # Resize if larger than 1920x1080
        w, h = img.size
        scale = min(1920 / w, 1080 / h, 1.0)
        if scale < 1.0:
            img = img.resize(
                (int(w * scale), int(h * scale)),
                PILImage.Resampling.BILINEAR,
            )

        for quality in [92, 88, 84, 80, 75, 70, 65, 60]:
            buf = io.BytesIO()
            img.save(buf, format="JPEG", quality=quality, optimize=True)
            data = buf.getvalue()
            if len(data) <= max_bytes:
                return base64.b64encode(data).decode("utf-8")

        logger.warning("Could not compress image below %d bytes", max_bytes)
        return None

    except Exception as exc:
        logger.error("compress_image_for_realtime failed: %s", exc)
        return None
