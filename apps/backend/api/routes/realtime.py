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
import asyncio as _asyncio
import struct
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from apps.backend.services.dashscope.multimodal_client import (
    MultimodalClient,
    VisionRequest,
)
from apps.backend.services.dashscope.realtime_client import (
    QwenRealtimeClient,
    QwenRealtimeConfig,
)
from core.memory import MemoryManager, SessionMemory, compose_memory_context
from core.orchestrator.capture_coach import assess_frame_quality
from core.orchestrator.intent_classifier import (
    IntentCategory,
    IntentClassifier,
)
from core.orchestrator.prompt_builder import (
    build_memory_fact,
    build_system_prompt,
)
from core.orchestrator.policy_router import RouteTarget, route

# Past-tense phrases that signal the user is asking about memory/history.
# Used by Plan 07 memory recall to auto-trigger MEMORY_READ without
# the user needing to say an explicit "recall" or "remember" command.
_PAST_TENSE_TRIGGERS: tuple[str, ...] = (
    "what is my",
    "what's my",
    "what was",
    "what did i",
    "what did you",
    "what have i",
    "what have you",
    "do you remember",
    "do you recall",
    "earlier",
    "last time",
    "before this",
    "who am i",
    "where do i live",
    "where do i work",
    "what do i do",
    "what did i show",
    "what did i tell",
    "what did i say",
    "ನನ್ನ ಹೆಸರು",
    "ನಾನು ಯಾರು",
    "मेरा नाम",
    "मैं कौन हूं",
    "before",
    "previously",
    "nanna hesaru",
    "neevu",
    "hinde",
    "mundhe",
    "mera naam",
    "meri",
    "tumhe yaad hai",
    "pehle",
    "aage",
    "was ",
    "were ",
    "had ",
    "did ",
    "showed",
    "told ",
    "said ",
)


def _is_memory_query(transcript: str) -> bool:
    """Return True if transcript appears to be asking about past memory or history."""
    if not transcript:
        return False
    t = transcript.lower().strip()
    return any(trigger.lower() in t for trigger in _PAST_TENSE_TRIGGERS)


def _normalize_memory_fact(fact: str) -> str:
    cleaned = fact.strip()
    if cleaned.lower().startswith("object/text seen: "):
        cleaned = cleaned.split(":", 1)[1].strip()
    return cleaned.rstrip(".")


def _build_memory_reply(
    query: str,
    st_facts: list[str],
    lt_facts: list[str],
    objects_seen: list[dict[str, str]],
) -> str | None:
    q = query.lower().strip()
    object_facts = [
        _normalize_memory_fact(obj.get("object_desc", ""))
        for obj in objects_seen
        if obj.get("object_desc")
    ]
    normalized_long = [
        _normalize_memory_fact(fact) for fact in lt_facts if fact.strip()
    ]
    normalized_short = [
        _normalize_memory_fact(fact) for fact in st_facts if fact.strip()
    ]
    combined = list(dict.fromkeys([*object_facts, *normalized_short, *normalized_long]))
    if not combined:
        return None

    if "name" in q:
        candidates = [*normalized_long, *normalized_short]
        for fact in candidates:
            lower = fact.lower()
            if lower.startswith("my name is "):
                return f"Your name is {fact[11:].strip()}."
            if lower.startswith("user name is "):
                return f"Your name is {fact[13:].strip()}."
        plain_candidates = [
            fact
            for fact in candidates
            if "name" not in fact.lower() and len(fact.split()) <= 4
        ]
        if plain_candidates:
            best_name = min(
                plain_candidates, key=lambda value: (len(value.split()), len(value))
            )
            return f"Your name is {best_name}."

    if ("show" in q or "earlier" in q) and object_facts:
        return f"You showed me {object_facts[0]}."

    if len(combined) == 1:
        return f"I remember: {combined[0]}."

    return "Here’s what I remember: " + "; ".join(combined[:3]) + "."


logger = logging.getLogger("ally-vision-realtime-route")
router = APIRouter()

_RECALL_PHRASES = (
    "what did i tell you",
    "do you remember",
    "recall ",
    "what is my",
    "who is my",
    "where is my",
)


def make_silent_pcm(duration_seconds: float, sample_rate: int = 16000) -> bytes:
    """Generate silent PCM audio (16-bit mono zeros)."""
    num_samples = int(sample_rate * duration_seconds)
    return struct.pack(f"<{num_samples}h", *([0] * num_samples))


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
    config.instructions = (
        "You are Ally, a voice and vision assistant "
        "for blind and visually impaired users. "
        "When an image is provided, ALWAYS describe "
        "or analyze it as part of your response. "
        "Be specific about what you see — objects, "
        "text, positions, distances, colors. "
        "Speak clearly and concisely. "
        "Support all languages — respond in the same "
        "language the user speaks."
    )
    client = QwenRealtimeClient(config)

    last_user_transcript: str = ""
    classifier = IntentClassifier.from_settings()
    mm_client = MultimodalClient.from_settings()
    memory_manager = MemoryManager.from_settings()
    if hasattr(type(memory_manager.store), "initialize_all"):
        await memory_manager.store.initialize_all()
    else:
        await memory_manager.store.initialize()
    session_memory_obj = getattr(memory_manager, "session_memory", None)
    if isinstance(session_memory_obj, SessionMemory):
        session_memory = session_memory_obj
    else:
        session_memory = SessionMemory()
        memory_manager.session_memory = session_memory
    pending_classification_task: _asyncio.Task[object] | None = None
    pending_classification_image_b64: str | None = None
    queued_classification_input: tuple[str, str | None] | None = None
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

                # Classify intent from PREVIOUS turn's transcript
                # (current transcript arrives WITH the response)
                effective_instructions = pending_instructions
                predicted_target = RouteTarget.REALTIME_CHAT
                applied_target = RouteTarget.REALTIME_CHAT
                predicted_intent: IntentCategory | None = None
                classified_image_b64: str | None = None
                route_audio_pcm = audio_pcm
                route_image_b64 = pending_image_b64
                classifier_handled_previous_memory = False
                session_memory_recorded = False

                if (
                    pending_classification_task
                    and pending_classification_task.done()
                    and not pending_instructions
                ):
                    try:
                        clf_result = pending_classification_task.result()
                        predicted_intent = clf_result.intent
                        classified_image_b64 = pending_classification_image_b64
                    except Exception as exc:
                        logger.warning(
                            "Orchestrator failed, using default: %s",
                            exc,
                        )
                    finally:
                        pending_classification_task = None
                        pending_classification_image_b64 = None
                        if queued_classification_input:
                            queued_transcript, queued_image_b64 = (
                                queued_classification_input
                            )
                            pending_classification_task = _asyncio.create_task(
                                classifier.classify(queued_transcript)
                            )
                            pending_classification_image_b64 = queued_image_b64
                            queued_classification_input = None
                elif (
                    pending_classification_task
                    and not pending_classification_task.done()
                ):
                    logger.debug(
                        "Intent classification still pending for previous turn — using default realtime behavior"
                    )

                # If no transcript yet but image is present, assume a visual request.
                if predicted_intent is None and pending_image_b64:
                    predicted_intent = IntentCategory.SCENE_DESCRIBE
                    logger.debug("No transcript yet, image present → SCENE_DESCRIBE")

                if predicted_intent is not None:
                    decision = route(predicted_intent)
                    predicted_target = decision.target
                    logger.debug(
                        "Intent: %s → Route: %s (frame=%s)",
                        predicted_intent.value,
                        decision.target.value,
                        decision.requires_frame,
                    )
                    if decision.target == RouteTarget.MEMORY_WRITE:
                        applied_target = RouteTarget.MEMORY_WRITE
                        try:
                            confirmed_fact = await memory_manager.save(
                                user_id="default",
                                raw_utterance=last_user_transcript,
                            )
                            effective_instructions = (
                                f"Tell the user: I will remember that {confirmed_fact}."
                            )
                            route_audio_pcm = make_silent_pcm(0.5)
                            route_image_b64 = None
                            classifier_handled_previous_memory = True
                        except Exception as exc:
                            logger.warning(
                                "Classifier-routed memory save failed: %s",
                                exc,
                            )
                    elif decision.target == RouteTarget.MEMORY_READ:
                        applied_target = RouteTarget.MEMORY_READ
                        try:
                            memory_context = await memory_manager.recall(
                                user_id="default",
                                query=last_user_transcript,
                                top_k=3,
                            )
                            if memory_context:
                                effective_instructions = build_system_prompt(
                                    base_instructions=(
                                        f"The user asked: {last_user_transcript}\n"
                                        "Answer using only the relevant stored memory."
                                        " Be brief and speak naturally."
                                    ),
                                    memory_context=memory_context,
                                )
                            else:
                                effective_instructions = "Tell the user: I don't have anything stored about that yet."
                            route_audio_pcm = make_silent_pcm(0.5)
                            route_image_b64 = None
                            classifier_handled_previous_memory = True
                        except Exception as exc:
                            logger.warning(
                                "Classifier-routed memory recall failed: %s",
                                exc,
                            )
                    elif decision.target == RouteTarget.HEAVY_VISION:
                        applied_target = RouteTarget.HEAVY_VISION
                        vision_image_b64 = classified_image_b64 or pending_image_b64
                        is_usable, guidance = assess_frame_quality(vision_image_b64)
                        if not is_usable:
                            effective_instructions = (
                                f"Tell the user this guidance: {guidance}"
                            )
                            logger.debug(
                                "HEAVY_VISION blocked by capture_coach: %s",
                                guidance,
                            )
                        elif vision_image_b64:
                            logger.debug(
                                "HEAVY_VISION: calling multimodal model=%s",
                                mm_client._model,
                            )
                            vision_result = await mm_client.analyze(
                                VisionRequest(
                                    image_jpeg_b64=vision_image_b64,
                                    prompt=decision.system_instructions
                                    or "Describe what you see.",
                                )
                            )
                            if vision_result.success:
                                effective_instructions = (
                                    "Say exactly this to the user: "
                                    f"{vision_result.text}"
                                )
                                session_memory.add_turn(
                                    user_transcript=last_user_transcript,
                                    assistant_response=vision_result.text,
                                    vision_objects=[
                                        f"Object/text seen: {vision_result.text[:120]}"
                                    ],
                                )
                                session_memory_recorded = True
                                logger.info(
                                    "HEAVY_VISION result: %d chars",
                                    len(vision_result.text),
                                )
                            else:
                                effective_instructions = (
                                    "Tell the user the image could not be "
                                    "analyzed. Ask them to try again."
                                )
                                logger.warning(
                                    "HEAVY_VISION error: %s",
                                    vision_result.error,
                                )
                        else:
                            effective_instructions = (
                                "Tell the user to press the capture button "
                                "to take a photo first, then ask again."
                            )
                    elif decision.requires_frame and not pending_image_b64:
                        logger.debug(
                            "Frame required but not available — will ask user to capture"
                        )
                        effective_instructions = (
                            "Tell the user briefly to press the camera "
                            "capture button first, then ask again."
                        )
                    elif decision.system_instructions:
                        effective_instructions = decision.system_instructions

                if predicted_target != applied_target:
                    logger.debug(
                        "Predicted route %s but applying handler %s in Plan 05",
                        predicted_target.value,
                        applied_target.value,
                    )

                try:
                    result = await client.async_send_audio_turn(
                        audio_pcm=route_audio_pcm,
                        image_jpeg_b64=route_image_b64,
                        instructions=effective_instructions,
                    )
                except Exception as exc:
                    await _send_upstream_error(ws, str(exc), config)
                    break

                current_user_transcript = result.user_transcript or ""

                # ── same-turn memory detection ──────────────────────────────
                _is_memory_save = False
                _is_memory_recall = _is_memory_query(current_user_transcript)

                _cleaned = build_memory_fact(current_user_transcript)
                if _cleaned != current_user_transcript.strip():
                    _is_memory_save = True

                if _is_memory_save:
                    try:
                        if _cleaned:
                            confirmed_fact = await memory_manager.save(
                                user_id="default",
                                raw_utterance=current_user_transcript,
                            )
                            override_result = await client.async_send_audio_turn(
                                audio_pcm=make_silent_pcm(0.5),
                                instructions=(
                                    f"Tell the user: I will remember that {confirmed_fact}."
                                ),
                            )
                            override_result.user_transcript = current_user_transcript
                            result = override_result
                            _skip_classifier = True
                        else:
                            override_result = await client.async_send_audio_turn(
                                audio_pcm=make_silent_pcm(0.5),
                                instructions=(
                                    "Tell the user: Please say the fact you want me to remember."
                                ),
                            )
                            override_result.user_transcript = current_user_transcript
                            result = override_result
                            _skip_classifier = True
                    except Exception as exc:
                        logger.warning("Memory save failed: %s", exc)
                        _skip_classifier = False

                elif _is_memory_recall:
                    try:
                        query_embedding = await memory_manager.embedder.embed(
                            current_user_transcript
                        )
                        st_facts_list = await memory_manager.store.recall_facts(
                            "default",
                            query_embedding,
                            top_k=3,
                            tier="short",
                        )
                        lt_facts_list = await memory_manager.store.recall_facts(
                            "default",
                            query_embedding,
                            top_k=3,
                            tier="long",
                        )
                        st_facts = "\n".join(st_facts_list) if st_facts_list else None
                        lt_facts = "\n".join(lt_facts_list) if lt_facts_list else None
                        combined = compose_memory_context(
                            session_memory.get_recent(5),
                            st_facts,
                            lt_facts,
                            session_memory.get_objects_seen(),
                        )
                        memory_reply = _build_memory_reply(
                            current_user_transcript,
                            st_facts_list,
                            lt_facts_list,
                            session_memory.get_objects_seen(),
                        )
                        if combined:
                            recall_instructions = (
                                "Reply with exactly this sentence and nothing else: "
                                f'"{memory_reply or combined}"'
                            )
                        else:
                            recall_instructions = "Tell the user: I don't have anything stored about that yet."
                        override_result = await client.async_send_audio_turn(
                            audio_pcm=make_silent_pcm(0.5),
                            instructions=recall_instructions,
                        )
                        override_result.user_transcript = current_user_transcript
                        result = override_result
                        _skip_classifier = True
                    except Exception as exc:
                        logger.warning("Memory recall failed: %s", exc)
                        _skip_classifier = False

                else:
                    _skip_classifier = classifier_handled_previous_memory
                # ── end same-turn memory detection ──────────────────────────

                current_user_transcript = (
                    result.user_transcript or current_user_transcript
                )
                if current_user_transcript and not _is_memory_query(
                    current_user_transcript
                ):
                    extract_coro = memory_manager.auto_extract_and_store(
                        user_id="default",
                        user_transcript=current_user_transcript,
                        assistant_transcript=result.assistant_transcript or "",
                    )
                    if _asyncio.iscoroutine(extract_coro):
                        _asyncio.create_task(extract_coro)

                if not session_memory_recorded:
                    session_memory.add_turn(
                        current_user_transcript,
                        result.assistant_transcript or "",
                    )

                turn_image_b64 = pending_image_b64

                # Store for next turn classification
                last_user_transcript = result.user_transcript or ""
                if last_user_transcript and not _skip_classifier:
                    if pending_classification_task is None:
                        pending_classification_task = _asyncio.create_task(
                            classifier.classify(last_user_transcript)
                        )
                        pending_classification_image_b64 = turn_image_b64
                    else:
                        queued_classification_input = (
                            last_user_transcript,
                            turn_image_b64,
                        )
                    if _is_memory_query(last_user_transcript or ""):
                        logger.debug(
                            "Memory query detected in transcript: %r — Plan 07 will handle recall",
                            (last_user_transcript or "")[:60],
                        )

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

                elif msg_type == "interrupt":
                    # User started speaking — cancel any in-progress response
                    client.cancel_response()
                    logger.info(
                        "Interrupt received from browser — response.cancel sent"
                    )

                else:
                    logger.warning("Unknown control message type: %r", msg_type)
                    break

    except WebSocketDisconnect:
        logger.info("WebSocket client disconnected")

    except Exception as exc:
        logger.error("WebSocket error: %s", exc)

    finally:
        session_memory.clear()
        client.close()
        logger.info("WebSocket session ended, client closed")
