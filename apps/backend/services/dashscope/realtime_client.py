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
import io
import json
import logging
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Optional

import websocket

logger = logging.getLogger("qwen-realtime-client")

# Session safety margin: reconnect at 110 min (before 120 min expiry)
_SESSION_MAX_LIFETIME_S = 110 * 60


def default_voice_for_model(model: str) -> str:
    """Return the safest default voice for a realtime model family."""
    model_lower = model.lower()
    if "qwen3-omni-flash-realtime" in model_lower:
        return "Cherry"
    return "Cherry"


@dataclass
class QwenRealtimeConfig:
    """Configuration for QwenRealtimeClient."""

    api_key: str
    model: str = "qwen3-omni-flash-realtime"
    endpoint: str = "wss://dashscope-intl.aliyuncs.com/api-ws/v1/realtime"
    voice: str = "Cherry"
    instructions: str = (
        "You are Ally, a helpful voice and vision assistant "
        "for blind and visually impaired users. "
        "Respond clearly and briefly in the same language the user speaks. "
        "For scene descriptions, be specific about objects, "
        "their positions, and distances."
    )
    transcription_model: str = "gummy-realtime-v1"
    audio_in_rate: int = 16000
    audio_out_rate: int = 24000
    chunk_bytes: int = 3200
    response_timeout_s: float = 60.0

    @classmethod
    def from_settings(cls) -> "QwenRealtimeConfig":
        """Create config from environment / settings module."""
        from shared.config.settings import (
            DASHSCOPE_REALTIME_URL,
            QWEN_REALTIME_MODEL,
            QWEN_TRANSCRIPTION_MODEL,
            get_api_key,
        )

        return cls(
            api_key=get_api_key(),
            model=QWEN_REALTIME_MODEL,
            endpoint=DASHSCOPE_REALTIME_URL,
            voice=default_voice_for_model(QWEN_REALTIME_MODEL),
            transcription_model=QWEN_TRANSCRIPTION_MODEL,
        )


@dataclass
class QwenRealtimeTurn:
    """Result of one completed realtime turn."""

    user_transcript: str = ""
    assistant_transcript: str = ""
    assistant_audio_pcm: bytes = field(default_factory=bytes)
    usage: dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None

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
        self._session_id: Optional[str] = None

    # ── connection lifecycle ──────────────────────────────────

    def connect(self) -> None:
        """Open WebSocket, configure session, wait until ready."""
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
            self._send_session_update()
            try:
                updated_event = self._wait_for_event("session.updated", timeout=15.0)
            except Exception as exc:
                session_context = (
                    f" session_id={self._session_id}" if self._session_id else ""
                )
                raise RuntimeError(
                    "DashScope session.update failed for "
                    f"model={self._config.model} voice={self._config.voice} "
                    f"endpoint={self._config.endpoint}{session_context}: {exc}"
                ) from exc
            self._session_id = (
                self._extract_session_id(updated_event) or self._session_id
            )
            self._connected = True
            self._session_start_time = time.monotonic()
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
        if self._ws:
            try:
                self._ws.close()
            except Exception:
                pass
            self._ws = None
        self._connected = False
        logger.info("Realtime session closed")

    def needs_reconnect(self) -> bool:
        """True when session is near the 120-minute lifetime limit."""
        if self._session_start_time is None:
            return True
        elapsed = time.monotonic() - self._session_start_time
        return elapsed >= _SESSION_MAX_LIFETIME_S

    def reconnect(self) -> None:
        """Full reconnect — new session, context NOT preserved."""
        logger.info("Reconnecting realtime session (new session)")
        self.close()
        self.connect()

    def ensure_connected(self) -> None:
        """Connect if not connected; reconnect if near expiry."""
        if not self._connected or self._ws is None:
            self.connect()
        elif self.needs_reconnect():
            self.reconnect()

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
                self._send_session_update(instructions=instructions)
                self._wait_for_event("session.updated", timeout=10.0)
            self._stream_audio(audio_pcm, image_jpeg_b64)
            self._collect_response(result)
        except Exception as exc:
            logger.error("Realtime turn failed: %s", exc)
            result.error = str(exc)
        finally:
            if instructions is not None and self._connected and self._ws is not None:
                try:
                    self._send_session_update()
                    self._wait_for_event("session.updated", timeout=10.0)
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

    def _send_event(self, payload: dict[str, Any]) -> None:
        payload = dict(payload)
        payload["event_id"] = "event_" + uuid.uuid4().hex
        self._require_ws().send(json.dumps(payload))

    def _recv_event(self, timeout: Optional[float] = None) -> dict[str, Any]:
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

    def _wait_for_event(
        self,
        expected_type: str,
        timeout: float = 20.0,
    ) -> dict[str, Any]:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            remaining = max(0.5, deadline - time.monotonic())
            try:
                event = self._recv_event(timeout=remaining)
            except websocket.WebSocketTimeoutException:
                break
            t = event.get("type", "")
            if t == expected_type:
                return event
            if t == "error":
                raise RuntimeError(f"Server error waiting for {expected_type}: {event}")
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
                        "model": self._config.transcription_model,
                    },
                    "turn_detection": None,
                },
            }
        )

    def _stream_audio(self, pcm_bytes: bytes, image_jpeg_b64: Optional[str]) -> None:
        """Stream PCM chunks and optional image, then commit."""
        chunk = self._config.chunk_bytes
        image_sent = False

        for i in range(0, len(pcm_bytes), chunk):
            audio_chunk = pcm_bytes[i : i + chunk]
            self._send_event(
                {
                    "type": "input_audio_buffer.append",
                    "audio": base64.b64encode(audio_chunk).decode("utf-8"),
                }
            )
            # Image must be sent AFTER first audio chunk
            if image_jpeg_b64 is not None and not image_sent:
                self._send_event(
                    {
                        "type": "input_image_buffer.append",
                        "image": image_jpeg_b64,
                    }
                )
                image_sent = True
                logger.debug("Image sent after first audio chunk")

        self._send_event({"type": "input_audio_buffer.commit"})
        self._wait_for_event("input_audio_buffer.committed", timeout=10.0)
        self._send_event({"type": "response.create"})
        logger.debug(
            "Streamed %d bytes audio, image=%s",
            len(pcm_bytes),
            "yes" if image_jpeg_b64 else "no",
        )

    def _collect_response(self, result: QwenRealtimeTurn) -> None:
        """Collect server events until response.done."""
        audio_chunks = bytearray()
        text_deltas: list[str] = []
        deadline = time.monotonic() + self._config.response_timeout_s
        saw_response_done = False

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
                result.user_transcript = event.get("transcript", "")

            elif t == "response.audio_transcript.delta":
                text_deltas.append(event.get("delta", ""))

            elif t == "response.audio_transcript.done":
                result.assistant_transcript = event.get(
                    "transcript", "".join(text_deltas)
                )

            elif t == "response.audio.delta":
                delta = event.get("delta")
                if isinstance(delta, str):
                    audio_chunks.extend(base64.b64decode(delta))

            elif t == "response.audio.done":
                pass  # audio.delta already collected

            elif t == "response.done":
                saw_response_done = True
                response = event.get("response", {})
                if isinstance(response, dict):
                    usage = response.get("usage", {})
                    if isinstance(usage, dict):
                        result.usage = usage
                    status = response.get("status")
                    if isinstance(status, str) and status != "completed":
                        result.error = f"Response finished with status: {status}"
                if not result.assistant_transcript:
                    result.assistant_transcript = "".join(text_deltas)
                break

            elif t == "error":
                result.error = str(event)
                logger.error("Server error event: %s", event)
                return

        if not saw_response_done and result.error is None:
            result.error = "Response ended before response.done"

        result.assistant_audio_pcm = bytes(audio_chunks)
        logger.info(
            "Turn complete: transcript=%d chars audio=%d bytes",
            len(result.assistant_transcript),
            len(result.assistant_audio_pcm),
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
