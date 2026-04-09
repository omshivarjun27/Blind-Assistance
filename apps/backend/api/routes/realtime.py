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
import time
from collections.abc import Coroutine
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from apps.backend.db.bootstrap import bootstrap_learning_tables
from apps.backend.services.dashscope.multimodal_client import (
    MultimodalClient,
    VisionRequest,
)
from apps.backend.services.dashscope.realtime_client import (
    QwenRealtimeClient,
    QwenRealtimeConfig,
)
from core.learning import CorrectionStore, OfflineReplay, OnlineReflection, PatchStore
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
from shared.config import settings

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


_SEARCH_TRIGGERS = [
    "search for",
    "look up",
    "find out",
    "what is the latest",
    "latest news",
    "current price",
    "today's",
    "news about",
    "who won",
    "what happened",
    "how much does",
    "is it open",
    "weather",
    "score",
    "trending",
    "right now",
    "currently",
    "live score",
]


def _is_search_query(transcript: str) -> bool:
    t = transcript.lower().strip()
    return any(trigger in t for trigger in _SEARCH_TRIGGERS)


def _is_effective_silence(transcript: str) -> bool:
    cleaned = transcript.strip().lower().strip(".?!,;:。！？،")
    return cleaned in {"", "uh", "um", "hmm", "mm", "mhm", "嗯", "嗯嗯"}


_CORRECTION_SIGNALS: frozenset[str] = frozenset(
    {
        "that's wrong",
        "thats wrong",
        "no that's not right",
        "no thats not right",
        "incorrect",
        "not what i asked",
        "wrong answer",
        "try again",
        "that's not it",
        "thats not it",
        "stop",
        "no no",
        "ತಪ್ಪು",
        "ಇಲ್ಲ",
        "ಸರಿಯಿಲ್ಲ",
        "गलत है",
        "गलत",
        "नहीं",
        "यह सही नहीं",
    }
)


def _is_correction_signal(transcript: str) -> tuple[bool, str]:
    """Returns (is_correction, matched_signal). Never raises."""
    t = transcript.lower().strip()
    for sig in _CORRECTION_SIGNALS:
        if sig in t:
            return True, sig
    return False, ""


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


def _is_silent_audio(audio_pcm: bytes) -> bool:
    return not any(audio_pcm)


async def _defer_auto_extract(
    memory_manager: MemoryManager,
    user_id: str,
    user_transcript: str,
    assistant_transcript: str,
) -> None:
    await _asyncio.sleep(0.05)
    await memory_manager.auto_extract_and_store(
        user_id=user_id,
        user_transcript=user_transcript,
        assistant_transcript=assistant_transcript,
    )


def _schedule_background_task(
    coro: Coroutine[Any, Any, object],
    label: str,
) -> None:
    try:
        _ = _asyncio.create_task(coro)
    except Exception as exc:
        logger.warning("%s create_task failed: %s", label, exc)


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

    session_id = uuid4().hex
    default_instructions = route(IntentCategory.GENERAL_CHAT).system_instructions
    config = QwenRealtimeConfig.from_settings()
    config.instructions = default_instructions
    client = QwenRealtimeClient(config)

    last_user_transcript: str = ""
    classifier = IntentClassifier.from_settings()
    mm_client = MultimodalClient.from_settings()
    memory_manager = MemoryManager.from_settings()
    offline_replay_api_key = settings.DASHSCOPE_API_KEY
    if not offline_replay_api_key:
        try:
            offline_replay_api_key = settings.get_api_key()
        except Exception as exc:
            logger.warning("Offline replay API key unavailable: %s", exc)
    correction_store = CorrectionStore.from_settings()
    online_reflection = OnlineReflection.from_settings()
    patch_store = PatchStore.from_settings()
    offline_replay = OfflineReplay(
        db_path=settings.MEMORY_DB_PATH,
        correction_store=correction_store,
        patch_store=patch_store,
        priority_min_recalls=settings.LEARNING_PRIORITY_PROMOTION_MIN_RECALLS,
        turbo_model=settings.QWEN_TURBO_MODEL,
        api_key=offline_replay_api_key,
        base_url=settings.DASHSCOPE_COMPAT_BASE,
    )
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
    await bootstrap_learning_tables(settings.MEMORY_DB_PATH)
    try:
        startup_ctx = await memory_manager.get_startup_memory_context("default")
    except Exception as exc:
        logger.warning("Startup priority memory load failed: %s", exc)
        startup_ctx = None
    if startup_ctx:
        default_instructions = build_system_prompt(
            base_instructions=route(IntentCategory.GENERAL_CHAT).system_instructions,
            memory_context=startup_ctx,
        )
        config.instructions = default_instructions
    pending_image_b64: str | None = None
    pending_instructions: str | None = None
    _scene_described_once: bool = False
    _last_instructions: str = default_instructions
    _turns_since_corr: int = 0
    _last_response_complete_at: float = 0.0

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

                if (
                    _scene_described_once
                    and not pending_image_b64
                    and not pending_instructions
                    and _is_silent_audio(audio_pcm)
                ):
                    logger.debug("Silent turn after first scene — skipping response")
                    last_user_transcript = ""
                    continue

                effective_instructions = pending_instructions or _last_instructions
                predicted_target = RouteTarget.REALTIME_CHAT
                applied_target = RouteTarget.REALTIME_CHAT
                predicted_intent: IntentCategory | None = None
                routing_decision = route(IntentCategory.GENERAL_CHAT)
                route_image_b64 = pending_image_b64
                session_memory_recorded = False
                scene_fallback_this_turn = False
                current_user_transcript = ""

                try:
                    current_user_transcript = await client.async_prepare_audio_turn(
                        audio_pcm=audio_pcm,
                        image_jpeg_b64=route_image_b64,
                    )
                except Exception as exc:
                    await _send_upstream_error(ws, str(exc), config)
                    break

                _cleaned = build_memory_fact(current_user_transcript)
                _silence_like = _is_effective_silence(current_user_transcript)
                _is_memory_save = (
                    bool(current_user_transcript.strip())
                    and not _silence_like
                    and (_cleaned != current_user_transcript.strip())
                )
                _is_memory_recall = bool(
                    current_user_transcript.strip() and not _silence_like
                ) and _is_memory_query(current_user_transcript)

                if _is_memory_save:
                    predicted_intent = IntentCategory.MEMORY_SAVE
                elif _is_memory_recall:
                    predicted_intent = IntentCategory.MEMORY_RECALL
                elif current_user_transcript.strip() and not _silence_like:
                    clf_result = await classifier.classify(current_user_transcript)
                    predicted_intent = clf_result.intent
                elif route_image_b64 and not _scene_described_once:
                    predicted_intent = IntentCategory.SCENE_DESCRIBE
                    _scene_described_once = True
                    scene_fallback_this_turn = True
                    logger.debug("No transcript yet, image present → SCENE_DESCRIBE")
                else:
                    logger.debug("Silent turn after first scene — skipping response")
                    pending_image_b64 = None
                    pending_instructions = None
                    last_user_transcript = ""
                    continue

                if predicted_intent is not None:
                    decision = route(predicted_intent)
                    routing_decision = decision
                    predicted_target = decision.target
                    prompt_verbosity = online_reflection.get_verbosity_mode(session_id)
                    prompt_penalty = online_reflection.get_intent_penalty(
                        str(predicted_intent)
                    )
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
                                raw_utterance=current_user_transcript,
                            )
                            effective_instructions = (
                                f"Tell the user: I will remember that {confirmed_fact}."
                            )
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
                                query=current_user_transcript,
                                top_k=3,
                            )
                            if memory_context:
                                effective_instructions = build_system_prompt(
                                    base_instructions=(
                                        f"The user asked: {current_user_transcript}\n"
                                        "Answer using only the relevant stored memory."
                                        " Be brief and speak naturally."
                                    ),
                                    memory_context=memory_context,
                                    verbosity_mode=prompt_verbosity,
                                    intent_penalty=prompt_penalty,
                                )
                            else:
                                effective_instructions = "Tell the user: I don't have anything stored about that yet."
                        except Exception as exc:
                            logger.warning(
                                "Classifier-routed memory recall failed: %s",
                                exc,
                            )
                    elif decision.target == RouteTarget.HEAVY_VISION:
                        applied_target = RouteTarget.HEAVY_VISION
                        vision_image_b64 = route_image_b64
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
                                    user_transcript=current_user_transcript,
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
                        # WEB_SEARCH: currently uses Qwen knowledge + disclaimer.
                        # TODO Plan 08: wire DashScope search tool here for live results.
                        effective_instructions = build_system_prompt(
                            base_instructions=decision.system_instructions,
                            verbosity_mode=prompt_verbosity,
                            intent_penalty=prompt_penalty,
                        )

                if predicted_target != applied_target:
                    logger.debug(
                        "Predicted route %s but applying handler %s in Plan 05",
                        predicted_target.value,
                        applied_target.value,
                    )

                if effective_instructions != _last_instructions:
                    try:
                        await client.async_update_instructions(effective_instructions)
                        _last_instructions = effective_instructions
                    except Exception as exc:
                        await _send_upstream_error(ws, str(exc), config)
                        break

                try:
                    result = await client.async_create_response_for_prepared_turn()
                except Exception as exc:
                    await _send_upstream_error(ws, str(exc), config)
                    break
                _last_response_complete_at = time.monotonic()

                if not result.user_transcript:
                    result.user_transcript = current_user_transcript

                current_user_transcript = (
                    result.user_transcript or current_user_transcript
                )
                if current_user_transcript and not _is_memory_query(
                    current_user_transcript
                ):
                    _schedule_background_task(
                        _defer_auto_extract(
                            memory_manager,
                            "default",
                            current_user_transcript,
                            result.assistant_transcript or "",
                        ),
                        "defer_auto_extract",
                    )

                if not session_memory_recorded:
                    session_memory.add_turn(
                        current_user_transcript,
                        result.assistant_transcript or "",
                    )

                _turn_id = f"{session_id}:{uuid4().hex}"
                _response_text = result.assistant_transcript or ""
                _current_intent = str(predicted_intent)
                _current_target = str(routing_decision.target)

                _schedule_background_task(
                    correction_store.log_turn(
                        session_id=session_id,
                        turn_id=_turn_id,
                        transcript=current_user_transcript,
                        response=_response_text,
                        intent=_current_intent,
                        route_target=_current_target,
                    ),
                    "correction_store.log_turn",
                )

                _is_corr, _corr_sig = _is_correction_signal(current_user_transcript)
                if _is_corr:
                    _schedule_background_task(
                        correction_store.log_correction(
                            session_id=session_id,
                            turn_id=_turn_id,
                            transcript=current_user_transcript,
                            response=_response_text,
                            signal=_corr_sig,
                            intent=_current_intent,
                        ),
                        "correction_store.log_correction",
                    )
                    _turns_since_corr = 0
                else:
                    _turns_since_corr += 1

                online_reflection.record_turn(
                    session_id=session_id,
                    turn_id=_turn_id,
                    intent=_current_intent,
                    was_corrected=_is_corr,
                    turns_since_last_correction=_turns_since_corr,
                )
                online_reflection.update_verbosity(session_id, current_user_transcript)

                turn_image_b64 = pending_image_b64

                last_user_transcript = current_user_transcript

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
                    elapsed = (
                        time.monotonic() - _last_response_complete_at
                        if _last_response_complete_at > 0.0
                        else float("inf")
                    )
                    if elapsed < 1.5:
                        logger.debug(
                            "Interrupt BLOCKED (premature): %.2fs since last response",
                            elapsed,
                        )
                        continue
                    client.cancel_response()
                    logger.info(
                        "Interrupt received from browser — response.cancel sent (%.2fs since last response complete)",
                        elapsed,
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
        _schedule_background_task(
            offline_replay.run_replay(session_id),
            "offline_replay.run_replay",
        )
        _schedule_background_task(
            offline_replay.promote_priority_memories(session_id),
            "offline_replay.promote_priority_memories",
        )
        logger.info("WebSocket session ended, client closed")
