"""
Ally Vision v2 — /ws/realtime WebSocket route.

Accepts browser audio (raw PCM binary frames)
and optional JSON control messages.
Routes each audio turn to QwenRealtimeClient.
Returns Qwen's spoken PCM audio + transcripts.

Audio contract:
  Binary frame = one complete PCM audio turn
  (frontend must send raw PCM, not MediaRecorder chunks)
  Text frame  = JSON control message
"""

from __future__ import annotations

import json
import logging
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from apps.backend.services.dashscope.realtime_client import (
    QwenRealtimeClient,
    QwenRealtimeConfig,
)

logger = logging.getLogger("ally-vision-realtime-route")
router = APIRouter()


async def _send_upstream_error(
    ws: WebSocket,
    message: str,
    config: QwenRealtimeConfig,
) -> None:
    await ws.send_text(
        json.dumps(
            {
                "type": "error",
                "code": "upstream_realtime_unavailable",
                "message": message,
                "details": {
                    "model": config.model,
                    "voice": config.voice,
                    "endpoint": config.endpoint,
                },
            }
        )
    )
    await ws.close()


@router.websocket("/ws/realtime")
async def realtime_endpoint(ws: WebSocket) -> None:
    """
    Main WebSocket endpoint for voice + vision interaction.

    Binary frames: raw PCM audio (16kHz 16-bit mono)
    Text frames:   JSON control messages:
      {"type": "image",        "data": "<base64 jpeg>"}
      {"type": "instructions", "text": "..."}
      {"type": "ping"}
    """
    await ws.accept()
    logger.info("WebSocket client connected")

    config = QwenRealtimeConfig.from_settings()
    client = QwenRealtimeClient(config)

    pending_image_b64: str | None = None
    pending_instructions: str | None = None

    try:
        while True:
            data = await ws.receive()

            # Handle disconnect signal
            if data["type"] == "websocket.disconnect":
                break

            # ── binary frame: audio turn ───────────────────
            if data.get("bytes"):
                audio_pcm = data["bytes"]
                if not isinstance(audio_pcm, bytes):
                    logger.warning("Ignoring non-bytes binary payload")
                    continue
                logger.debug("Audio turn received: %d bytes", len(audio_pcm))

                try:
                    result = await client.async_send_audio_turn(
                        audio_pcm=audio_pcm,
                        image_jpeg_b64=pending_image_b64,
                        instructions=pending_instructions,
                    )
                except Exception as exc:
                    await _send_upstream_error(ws, str(exc), config)
                    break

                # Reset per-turn context
                pending_image_b64 = None
                pending_instructions = None

                # Send spoken audio back
                if result.assistant_audio_pcm:
                    await ws.send_bytes(result.assistant_audio_pcm)

                # Send assistant transcript
                if result.assistant_transcript:
                    await ws.send_text(
                        json.dumps(
                            {
                                "type": "transcript",
                                "role": "assistant",
                                "text": result.assistant_transcript,
                            }
                        )
                    )

                # Send user transcript (reference only)
                if result.user_transcript:
                    await ws.send_text(
                        json.dumps(
                            {
                                "type": "transcript",
                                "role": "user",
                                "text": result.user_transcript,
                            }
                        )
                    )

                # Surface error if turn failed
                if not result.success:
                    await _send_upstream_error(
                        ws,
                        result.error or "Turn failed",
                        config,
                    )
                    break

            # ── text frame: JSON control message ──────────
            elif data.get("text"):
                raw_text = data["text"]
                if not isinstance(raw_text, str):
                    logger.warning("Ignoring non-text control payload")
                    continue
                try:
                    msg: dict[str, Any] = json.loads(raw_text)
                except json.JSONDecodeError:
                    logger.warning("Invalid JSON in text frame: %r", raw_text[:100])
                    break

                msg_type = msg.get("type", "")
                if not isinstance(msg_type, str):
                    logger.warning("Invalid control message type: %r", msg_type)
                    break

                if msg_type == "image":
                    image_data = msg.get("data")
                    pending_image_b64 = (
                        image_data if isinstance(image_data, str) else None
                    )
                    logger.debug("Image queued for next audio turn")

                elif msg_type == "instructions":
                    instruction_text = msg.get("text")
                    pending_instructions = (
                        instruction_text if isinstance(instruction_text, str) else None
                    )
                    logger.debug("Instructions queued for next audio turn")

                elif msg_type == "ping":
                    await ws.send_text(json.dumps({"type": "pong"}))

                else:
                    logger.warning("Unknown control message type: %r", msg_type)
                    break

    except WebSocketDisconnect:
        logger.info("WebSocket client disconnected")

    except Exception as exc:
        logger.error("WebSocket error: %s", exc)

    finally:
        client.close()
        logger.info("WebSocket session ended, client closed")
