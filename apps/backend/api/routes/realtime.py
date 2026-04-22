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
from typing import Any, cast
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
    QwenRealtimeTurn,
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
    "tell me about my",
    "what do you know about me",
    "what do you know about my",
    "can you tell me about my",
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

_MEMORY_RECALL_TOP_K = 5
_MEMORY_RECALL_THRESHOLD = 0.72


def _is_memory_query(transcript: str) -> bool:
    """Return True if transcript appears to be asking about past memory or history."""
    if not transcript:
        return False
    t = transcript.lower().strip()
    return any(trigger.lower() in t for trigger in _PAST_TENSE_TRIGGERS)


def _is_effective_silence(transcript: str) -> bool:
    cleaned = transcript.strip().lower().strip(".?!,;:。！？،")
    return cleaned in {"", "uh", "um", "hmm", "mm", "mhm", "嗯", "嗯嗯"}


_CORRECTION_SIGNALS: frozenset[str] = frozenset(
    {
        "that's wrong",
        "thats wrong",
        "that is wrong",
        "you're wrong",
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
        "ಅದು ತಪ್ಪು",
        "ತಪ್ಪಾಗಿದೆ",
        "गलत है",
        "गलत",
        "नहीं",
        "यह सही नहीं",
    }
)

_GREETING_PATTERNS: tuple[str, ...] = (
    "how can i help",
    "how may i help",
    "what can i do for you",
    "hello",
    "hi there",
    "nice to",
    "nice to meet",
    "good morning",
    "good evening",
    "good afternoon",
)

_ACK_WORDS: frozenset[str] = frozenset(
    {
        "ok",
        "okay",
        "yes",
        "no",
        "yeah",
        "sure",
        "indeed",
        "alright",
        "right",
        "fine",
        "good",
        "got it",
        "i see",
        "understood",
        "thanks",
        "thank you",
        "cool",
        "great",
        "nice",
        "हाँ",
        "नहीं",
        "ठीक है",
        "अच्छा",
        "हां",
        "ओके",
        "ಹೌದು",
        "ಇಲ್ಲ",
        "ಸರಿ",
        "ಆಯ್ತು",
        "ಒಕೆ",
        "ಧನ್ಯವಾದ",
    }
)

_VISION_TRIGGERS: tuple[str, ...] = (
    "see",
    "look",
    "what",
    "describe",
    "show",
    "read",
    "tell me what",
    "what is",
    "what's",
    "who is",
    "who's",
    "where is",
    "which",
    "color",
    "text",
    "sign",
    "write",
    "written",
    "number",
    "find",
    "identify",
    "any",
    "help me see",
    "can you see",
    "देखो",
    "क्या है",
    "बताओ",
    "दिखाओ",
    "पढ़ो",
    "कौन",
    "कहाँ है",
    "रंग",
    "लिखा",
    "नंबर",
    "ನೋಡು",
    "ಏನು",
    "ಹೇಳು",
    "ತೋರಿಸು",
    "ಓದು",
    "ಯಾರು",
    "ಎಲ್ಲಿ",
    "ಬಣ್ಣ",
    "ಬರೆದಿದೆ",
    "ಸಂಖ್ಯೆ",
)

_MEMORY_SAVE_TRIGGERS: tuple[str, ...] = (
    "permanent memory",
    "store permanently",
    "remember forever",
    "save permanently",
    "long term",
    "remember this always",
    "ಶಾಶ್ವತ ಸ್ಮರಣೆ",
    "हमेशा के लिए याद",
)

_SHORT_GENERAL_CHAT_PHRASES: frozenset[str] = frozenset(
    {
        "how are you",
        "who are you",
        "what can you do",
        "can you help",
        "help me",
    }
)

_PERSONAL_MEMORY_KEYWORDS: tuple[str, ...] = (
    "my name",
    "i am",
    "i'm",
    "my city",
    "i live",
    "my doctor",
    "my school",
    "my job",
    "my age",
    "remember",
    "store",
    "save",
    "note",
    "ನನ್ನ ಹೆಸರು",
    "ನಾನು",
    "ನನ್ನ",
    "ನನ್ನ ನಗರ",
    "मेरा नाम",
    "मैं",
    "मेरा",
    "मेरी",
)

_SEND_EXCEPTIONS = (WebSocketDisconnect, RuntimeError, ConnectionResetError)


def _is_correction_signal(transcript: str) -> tuple[bool, str]:
    """Returns (is_correction, matched_signal). Never raises."""
    t = transcript.lower().strip()
    for sig in _CORRECTION_SIGNALS:
        if sig in t:
            return True, sig
    return False, ""


def _is_greeting(text: str) -> bool:
    cleaned = text.lower().strip()
    return any(pattern in cleaned for pattern in _GREETING_PATTERNS) and len(cleaned) < 80


def _normalize_spoken_text(text: str) -> str:
    return text.strip().lower().strip(".?!,;:。！？،")


def _is_acknowledgement(text: str) -> bool:
    cleaned = _normalize_spoken_text(text)
    return cleaned in _ACK_WORDS


def _contains_vision_trigger(text: str) -> bool:
    cleaned = _normalize_spoken_text(text)
    return any(trigger in cleaned for trigger in _VISION_TRIGGERS)


def _should_force_scene_describe(transcript: str, image_present: bool) -> bool:
    if not image_present:
        return False
    cleaned = _normalize_spoken_text(transcript)
    if not cleaned:
        return True
    if cleaned in _ACK_WORDS:
        return False
    if cleaned in _SHORT_GENERAL_CHAT_PHRASES or _is_greeting(cleaned):
        return False
    return len(cleaned.split()) <= 3


def _is_explicit_memory_save_request(transcript: str) -> bool:
    cleaned = transcript.strip()
    if not cleaned or _is_effective_silence(cleaned):
        return False
    if build_memory_fact(cleaned) != cleaned:
        return True
    lowered = cleaned.lower()
    return any(token in lowered for token in _MEMORY_SAVE_TRIGGERS)


def _should_auto_extract_memory(
    transcript: str,
    intent: IntentCategory | None,
    route_target: RouteTarget,
) -> bool:
    cleaned = transcript.strip()
    if not cleaned or _is_effective_silence(cleaned):
        return False
    if route_target == RouteTarget.MEMORY_WRITE or intent == IntentCategory.MEMORY_SAVE:
        return True
    if intent not in {IntentCategory.GENERAL_CHAT, IntentCategory.MEMORY_RECALL}:
        return False
    lowered = cleaned.lower()
    return any(keyword in lowered for keyword in _PERSONAL_MEMORY_KEYWORDS)


def _build_memory_write_confirmation(saved_fact: str) -> str:
    return f"Done. I've saved that you told me: {saved_fact}."


def _is_short_ambiguous_general_chat(
    transcript: str,
    intent: IntentCategory | None,
) -> bool:
    cleaned = transcript.strip()
    if intent != IntentCategory.GENERAL_CHAT or not cleaned:
        return False
    if "?" in cleaned or _is_greeting(cleaned):
        return False
    return len(cleaned.split()) < 4


def _build_short_input_clarification_prompt(transcript: str) -> str:
    return (
        f"The user said: '{transcript}'. This is very short. "
        "Please ask one short clarifying question before answering."
    )


def _is_short_visual_fragment(transcript: str) -> bool:
    cleaned = transcript.strip()
    if not cleaned:
        return True
    return len(cleaned.split()) < 3


def _detect_script(text: str) -> str:
    for ch in text:
        cp = ord(ch)
        if 0x0C80 <= cp <= 0x0CFF:
            return "kn"
        if 0x0900 <= cp <= 0x097F:
            return "hi"
        if 0x4E00 <= cp <= 0x9FFF:
            return "zh"
    return "en"


def _normalize_memory_fact(fact: str) -> str:
    cleaned = fact.strip()
    if cleaned.lower().startswith("object/text seen: "):
        cleaned = cleaned.split(":", 1)[1].strip()
    return cleaned.rstrip(".")


def _build_memory_recall_system_prompt(base_prompt: str, facts: list[str]) -> str:
    if not facts:
        return base_prompt
    context_block = "\n".join(f"- {fact}" for fact in facts)
    return f"{base_prompt}\n\nWhat I know about you:\n{context_block}"


def _build_exact_memory_recall_note(query: str, facts: list[str]) -> str:
    lowered_query = query.lower()
    if not any(token in lowered_query for token in ("name", "ಹೆಸರು", "नाम")):
        return ""
    for fact in facts:
        lowered_fact = fact.lower().strip().rstrip(".")
        if lowered_fact.startswith("user's name is ") or lowered_fact.startswith("user name is "):
            return (
                "The user asked about their name. According to memory, their name is exactly: "
                f"'{fact}'. Use this exact name in your response."
            )
    return ""


async def _apply_memory_recall_instructions(
    client: QwenRealtimeClient,
    memory_manager: MemoryManager,
    user_id: str,
    query: str,
    base_prompt: str,
) -> str:
    facts = await memory_manager.retrieve_relevant_facts(
        user_id=user_id,
        query=query,
        top_k=_MEMORY_RECALL_TOP_K,
        threshold=_MEMORY_RECALL_THRESHOLD,
    )
    if facts:
        logger.info(
            "Memory retrieved: %d facts — injected into system prompt",
            len(facts),
        )
    else:
        logger.info("Memory retrieval: no facts above threshold — using base prompt")
    system_prompt = _build_memory_recall_system_prompt(base_prompt, facts)
    exact_note = _build_exact_memory_recall_note(query, facts)
    if exact_note:
        system_prompt = f"{system_prompt}\n\n{exact_note}"
    await client.async_update_instructions(system_prompt)
    return system_prompt


async def _safe_send_json(ws: WebSocket, payload: dict[str, Any]) -> bool:
    try:
        await ws.send_text(json.dumps(payload))
        return True
    except _SEND_EXCEPTIONS as exc:
        logger.warning("Frontend WebSocket closed before send: %s", exc)
        return False


async def _safe_send_bytes(ws: WebSocket, payload: bytes) -> bool:
    try:
        await ws.send_bytes(payload)
        return True
    except _SEND_EXCEPTIONS as exc:
        logger.warning("Frontend WebSocket closed before send: %s", exc)
        return False


async def _safe_close_websocket(ws: WebSocket) -> None:
    try:
        await ws.close()
    except _SEND_EXCEPTIONS:
        return


async def _send_heartbeat(ws: WebSocket, interval: float = 5.0) -> None:
    while True:
        await _asyncio.sleep(interval)
        sent = await _safe_send_json(ws, {"type": "ping"})
        if not sent:
            return


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
    turn_index: int,
) -> None:
    await _asyncio.sleep(0.05)
    try:
        await _asyncio.wait_for(
            memory_manager.auto_extract_and_store(
                user_id=user_id,
                user_transcript=user_transcript,
                assistant_transcript=assistant_transcript,
                turn_index=turn_index,
            ),
            timeout=5.0,
        )
    except _asyncio.TimeoutError:
        logger.warning(
            "Memory extraction timed out — turn %d skipped",
            turn_index,
        )
    except Exception as exc:
        logger.warning(
            "Memory extraction failed — turn %d: %s",
            turn_index,
            exc,
        )


def _schedule_background_task(
    coro: Coroutine[Any, Any, object],
    label: str,
) -> None:
    try:
        _ = _asyncio.create_task(coro)
    except Exception as exc:
        logger.warning("%s create_task failed: %s", label, exc)


async def _handle_control_message(
    ws: WebSocket,
    client: QwenRealtimeClient,
    raw_text: str,
    pending_image_b64: str | None,
    pending_instructions: str | None,
    last_response_complete_at: float,
) -> tuple[bool, str | None, str | None]:
    try:
        msg: dict[str, Any] = json.loads(raw_text)
    except json.JSONDecodeError:
        logger.warning("Invalid JSON in text frame: %r", raw_text[:100])
        return False, pending_image_b64, pending_instructions

    msg_type = msg.get("type", "")
    if not isinstance(msg_type, str):
        logger.warning("Invalid control message type: %r", msg_type)
        return False, pending_image_b64, pending_instructions

    if msg_type == "image":
        image_data = msg.get("data")
        pending_image_b64 = image_data if isinstance(image_data, str) else None
        logger.debug("Image queued for next audio turn")
        return True, pending_image_b64, pending_instructions

    if msg_type == "instructions":
        instruction_text = msg.get("text")
        pending_instructions = instruction_text if isinstance(instruction_text, str) else None
        logger.debug("Instructions queued for next audio turn")
        return True, pending_image_b64, pending_instructions

    if msg_type == "ping":
        sent = await _safe_send_json(ws, {"type": "pong"})
        return sent, pending_image_b64, pending_instructions

    if msg_type == "interrupt":
        if not client.has_active_response():
            logger.debug("Cancel: no active response — image slot flushed")
            return True, None, pending_instructions

        client.cancel_response()
        logger.info("Barge-in detected — response cancelled")
        return True, None, pending_instructions

    logger.warning("Unknown control message type: %r", msg_type)
    return False, pending_image_b64, pending_instructions


async def _await_turn_result_or_messages(
    ws: WebSocket,
    client: QwenRealtimeClient,
    turn_task: _asyncio.Task[QwenRealtimeTurn],
    config: QwenRealtimeConfig,
    pending_image_b64: str | None,
    pending_instructions: str | None,
    last_response_complete_at: float,
) -> tuple[QwenRealtimeTurn | None, dict[str, Any] | None, str | None, str | None, bool]:
    receive_task: _asyncio.Task[Any] | None = None
    queued_data: dict[str, Any] | None = None

    while True:
        if receive_task is None:
            receive_task = _asyncio.create_task(ws.receive())

        assert receive_task is not None

        done, _ = await _asyncio.wait(
            {turn_task, receive_task},
            return_when=_asyncio.FIRST_COMPLETED,
        )

        if turn_task in done:
            if receive_task is not None and receive_task.done():
                try:
                    queued_data = receive_task.result()
                except WebSocketDisconnect:
                    logger.info("User WebSocket disconnected — closing DashScope session")
                    return None, queued_data, pending_image_b64, pending_instructions, True
                receive_task = None
            elif receive_task is not None:
                receive_task.cancel()
                await _asyncio.gather(receive_task, return_exceptions=True)
                receive_task = None
            try:
                result = cast(QwenRealtimeTurn, turn_task.result())
            except (WebSocketDisconnect, _asyncio.CancelledError):
                turn_task.cancel()
                await _asyncio.gather(turn_task, return_exceptions=True)
                logger.info("User WebSocket disconnected — closing DashScope session")
                return None, queued_data, pending_image_b64, pending_instructions, True
            except Exception as exc:
                await _send_upstream_error(ws, str(exc), config)
                return None, queued_data, pending_image_b64, pending_instructions, True
            return result, queued_data, pending_image_b64, pending_instructions, False

        if receive_task in done:
            try:
                incoming = receive_task.result()
            except WebSocketDisconnect:
                turn_task.cancel()
                await _asyncio.gather(turn_task, return_exceptions=True)
                logger.info("User WebSocket disconnected — closing DashScope session")
                return None, queued_data, pending_image_b64, pending_instructions, True
            receive_task = None

            if incoming["type"] == "websocket.disconnect":
                turn_task.cancel()
                await _asyncio.gather(turn_task, return_exceptions=True)
                logger.info("User WebSocket disconnected — closing DashScope session")
                return None, queued_data, pending_image_b64, pending_instructions, True

            if incoming.get("text"):
                raw_text = incoming["text"]
                if not isinstance(raw_text, str):
                    logger.warning("Ignoring non-text control payload")
                    continue
                handled, pending_image_b64, pending_instructions = (
                    await _handle_control_message(
                        ws,
                        client,
                        raw_text,
                        pending_image_b64,
                        pending_instructions,
                        last_response_complete_at,
                    )
                )
                if not handled:
                    turn_task.cancel()
                    await _asyncio.gather(turn_task, return_exceptions=True)
                    return None, queued_data, pending_image_b64, pending_instructions, True
                continue

            if incoming.get("bytes"):
                queued_data = incoming
                if client.has_active_response():
                    client.cancel_response()
                    logger.info("Barge-in detected — response cancelled")
                continue


async def _send_upstream_error(
    ws: WebSocket,
    message: str,
    config: QwenRealtimeConfig,
) -> None:
    await _safe_send_json(
        ws,
        {
            "type": "error",
            "code": "upstream_realtime_unavailable",
            "message": message,
            "details": {
                "model": config.model,
                "voice": config.voice,
                "endpoint": config.endpoint,
            },
        },
    )
    await _safe_close_websocket(ws)


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
        startup_facts = await memory_manager.get_priority_facts("default", top_k=10)
    except Exception as exc:
        logger.warning("Startup priority memory load failed: %s", exc)
        startup_facts = []
    if startup_facts:
        startup_ctx = "Known facts about this user from memory:\n" + "\n".join(
            f"- {fact}" for fact in startup_facts
        )
        default_instructions = build_system_prompt(
            base_instructions=route(IntentCategory.GENERAL_CHAT).system_instructions,
            memory_context=startup_ctx,
        )
        config.instructions = default_instructions
        logger.info(
            "Memory pre-loaded: %d facts injected into session",
            len(startup_facts),
        )
    else:
        logger.info("Memory pre-load: no facts found in DB")
    try:
        await client.async_connect()
    except Exception as exc:
        await _send_upstream_error(ws, str(exc), config)
        return
    pending_image_b64: str | None = None
    pending_instructions: str | None = None
    _scene_described_once: bool = False
    _last_instructions: str = default_instructions
    _turns_since_corr: int = 0
    _last_response_complete_at: float = 0.0
    _turn_index: int = 0
    _last_transcript: str = ""
    queued_data: dict[str, Any] | None = None
    heartbeat_task = _asyncio.create_task(_send_heartbeat(ws, interval=5.0))
    _last_vision_descriptions: list[str] = []

    try:
        while True:
            data = queued_data if queued_data is not None else await ws.receive()
            queued_data = None

            # Handle disconnect signal
            if data["type"] == "websocket.disconnect":
                logger.info("User WebSocket disconnected — closing DashScope session")
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
                current_turn_index = _turn_index
                _turn_index += 1
                prior_transcript = _last_transcript.strip()
                predicted_target = RouteTarget.REALTIME_CHAT
                applied_target = RouteTarget.REALTIME_CHAT
                predicted_intent: IntentCategory | None = None
                resolved_intent: IntentCategory | None = None
                routing_decision = route(IntentCategory.GENERAL_CHAT)
                route_image_b64 = pending_image_b64
                pending_image_b64 = None
                session_memory_recorded = False
                turn_user_input_text: str | None = None
                response_instructions: str | None = None
                current_user_transcript: str | None = ""
                user_transcript_sent = False
                intent_task: _asyncio.Task[object] | None = None
                intent_started_at: float | None = None
                classification_deferred = False
                instructions_already_updated = False
                should_update_session_instructions = True
                _turn_id = f"{session_id}:{uuid4().hex}"

                turn_connect_started = time.monotonic()
                if not client.is_connected():
                    logger.warning("DashScope session dropped — reconnecting")
                    try:
                        await client.async_connect()
                    except Exception as exc:
                        await _send_upstream_error(ws, str(exc), config)
                        break
                elif client.session_needs_reconnect():
                    logger.info("DashScope session expiring — reconnecting before turn")
                    try:
                        await client.async_reconnect()
                        logger.info(
                            "DashScope session reconnected — session.updated confirmed in %dms",
                            client._last_session_updated_elapsed_ms,
                        )
                    except Exception as exc:
                        await _send_upstream_error(ws, str(exc), config)
                        break
                else:
                    logger.info(
                        "Reusing existing DashScope session — turn latency: %dms",
                        int((time.monotonic() - turn_connect_started) * 1000),
                    )

                try:
                    current_user_transcript = await client.async_prepare_audio_turn(
                        audio_pcm=audio_pcm,
                        image_jpeg_b64=None,
                    )
                except Exception as exc:
                    await _send_upstream_error(ws, str(exc), config)
                    break

                commit_failure_message = client.consume_last_commit_failure()
                if commit_failure_message is not None:
                    sent = await _safe_send_json(
                        ws,
                        {
                            "type": "status",
                            "status": "turn_failed",
                            "message": "Voice turn failed — please try again",
                        },
                    )
                    if not sent:
                        break
                    logger.info("DashScope session recovered after InternalError")
                    pending_instructions = None
                    _last_transcript = ""
                    last_user_transcript = ""
                    continue

                transcript_for_routing = current_user_transcript or ""
                transcript_script = _detect_script(transcript_for_routing)
                language_override_note: str | None = None
                if transcript_script == "zh":
                    logger.warning(
                        "Transcript appears Chinese but user likely spoke Kannada/Hindi — possible transcription error"
                    )
                    language_override_note = (
                        "The transcript may be mistranscribed. Do not respond in Chinese. Default to Kannada unless Hindi or English are clearly intended."
                    )
                if transcript_for_routing.strip():
                    sent = await _safe_send_json(
                        ws,
                        {
                            "type": "transcript",
                            "role": "user",
                            "text": transcript_for_routing,
                            "turn_id": _turn_id,
                        },
                    )
                    if not sent:
                        break
                    user_transcript_sent = True

                if transcript_for_routing.strip():
                    online_reflection.update_verbosity(session_id, transcript_for_routing)

                _silence_like = _is_effective_silence(transcript_for_routing)
                _is_memory_save = _is_explicit_memory_save_request(transcript_for_routing)
                _is_memory_recall = bool(
                    transcript_for_routing.strip() and not _silence_like
                ) and _is_memory_query(transcript_for_routing)

                if _is_memory_save:
                    predicted_intent = IntentCategory.MEMORY_SAVE
                elif _is_memory_recall:
                    predicted_intent = IntentCategory.MEMORY_RECALL
                elif route_image_b64 and _should_force_scene_describe(
                    transcript_for_routing,
                    True,
                ):
                    predicted_intent = IntentCategory.SCENE_DESCRIBE
                    logger.debug(
                        "Turn %d: short/empty non-ack transcript + image present → forcing SCENE_DESCRIBE (heavy vision)",
                        current_turn_index,
                    )
                elif route_image_b64 and _is_acknowledgement(transcript_for_routing):
                    predicted_intent = IntentCategory.GENERAL_CHAT
                    effective_instructions = default_instructions
                elif (
                    route_image_b64
                    and transcript_for_routing.strip()
                    and not _silence_like
                ):
                    clf_result = await classifier.classify(transcript_for_routing)
                    predicted_intent = clf_result.intent
                    if (
                        _contains_vision_trigger(transcript_for_routing)
                        and route(predicted_intent).target != RouteTarget.HEAVY_VISION
                    ):
                        predicted_intent = IntentCategory.SCENE_DESCRIBE
                elif not prior_transcript or len(prior_transcript) < 3:
                    _last_transcript = ""
                    logger.info(
                        "Intent classification skipped — no transcript (turn %d cold start)",
                        current_turn_index,
                    )
                    if route_image_b64 and not _scene_described_once:
                        predicted_intent = IntentCategory.SCENE_DESCRIBE
                        _scene_described_once = True
                        logger.debug(
                            "No transcript yet, image present → SCENE_DESCRIBE"
                        )
                    else:
                        predicted_intent = IntentCategory.GENERAL_CHAT
                        effective_instructions = default_instructions
                else:
                    intent_started_at = time.monotonic()
                    logger.info("Intent classification started — background task fired")
                    intent_task = _asyncio.create_task(
                        classifier.classify(prior_transcript)
                    )
                    predicted_intent = IntentCategory.GENERAL_CHAT
                    effective_instructions = default_instructions
                    classification_deferred = True

                if predicted_intent is not None:
                    decision = route(predicted_intent)
                    routing_decision = decision
                    predicted_target = decision.target
                    prompt_verbosity = online_reflection.get_verbosity_mode(session_id)
                    prompt_penalty = online_reflection.get_session_intent_penalty(
                        session_id,
                        str(predicted_intent),
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
                            response_instructions = (
                                "Respond exactly with this sentence and nothing else: "
                                f"{_build_memory_write_confirmation(confirmed_fact)}"
                            )
                            should_update_session_instructions = False
                        except Exception as exc:
                            logger.warning(
                                "Classifier-routed memory save failed: %s",
                                exc,
                            )
                    elif decision.target == RouteTarget.MEMORY_READ:
                        applied_target = RouteTarget.MEMORY_READ
                        try:
                            effective_instructions = await _apply_memory_recall_instructions(
                                client=client,
                                memory_manager=memory_manager,
                                user_id="default",
                                query=current_user_transcript or "",
                                base_prompt=(
                                    f"{default_instructions}\n\n"
                                    f"The user asked: {current_user_transcript}\n"
                                    "Answer using only the remembered facts that are relevant to the question. "
                                    "If nothing relevant is stored, say so briefly."
                                ),
                            )
                            _last_instructions = effective_instructions
                            instructions_already_updated = True
                        except Exception as exc:
                            logger.warning(
                                "Classifier-routed memory recall failed: %s",
                                exc,
                            )
                    elif decision.target == RouteTarget.HEAVY_VISION:
                        intent_log_value = (
                            "SCENE_DESCRIPTION"
                            if predicted_intent == IntentCategory.SCENE_DESCRIBE
                            else predicted_intent.value
                        )
                        logger.info(
                            "Heavy vision dispatch — intent: %s",
                            intent_log_value,
                        )
                        applied_target = RouteTarget.HEAVY_VISION
                        vision_image_b64 = route_image_b64
                        is_usable, guidance = assess_frame_quality(vision_image_b64)
                        if not is_usable:
                            logger.warning(
                                "CaptureCoach rejected frame — %s",
                                guidance,
                            )
                            effective_instructions = (
                                f"Tell the user this guidance: {guidance}"
                            )
                            logger.debug(
                                "HEAVY_VISION blocked by capture_coach: %s",
                                guidance,
                            )
                        elif vision_image_b64:
                            logger.info(
                                "CaptureCoach: frame accepted — quality: pass"
                            )
                            logger.debug(
                                "HEAVY_VISION: calling multimodal model=%s",
                                mm_client._model,
                            )
                            vision_prompt = (
                                decision.system_instructions or "Describe what you see."
                            )
                            if _last_vision_descriptions:
                                prior_context = "\n".join(
                                    f"- {item[:100]}..."
                                    for item in _last_vision_descriptions[-2:]
                                )
                                vision_prompt = (
                                    f"{vision_prompt}\n\nPrevious descriptions of this scene (avoid repeating):\n{prior_context}"
                                )
                            vision_result = await mm_client.analyze(
                                VisionRequest(
                                    image_jpeg_b64=vision_image_b64,
                                    prompt=vision_prompt,
                                )
                            )
                            if vision_result.success:
                                logger.info(
                                    "Vision model response received — %d chars",
                                    len(vision_result.text),
                                )
                                if (current_user_transcript or "").strip():
                                    turn_user_input_text = (
                                        f"The user asked: {current_user_transcript}\n"
                                        f"[Camera sees]: {vision_result.text}"
                                    )
                                else:
                                    turn_user_input_text = (
                                        f"[Camera sees]: {vision_result.text}"
                                    )
                                session_memory.add_turn(
                                    user_transcript=current_user_transcript or "",
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
                                _last_vision_descriptions.append(vision_result.text[:200])
                                if len(_last_vision_descriptions) > 3:
                                    _last_vision_descriptions.pop(0)
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
                    elif decision.requires_frame and not route_image_b64:
                        logger.debug(
                            "Frame required but not available — will ask user to capture"
                        )
                        effective_instructions = (
                            "Tell the user briefly to press the camera "
                            "capture button first, then ask again."
                        )
                    elif decision.system_instructions:
                        effective_instructions = build_system_prompt(
                            base_instructions=decision.system_instructions,
                            verbosity_mode=prompt_verbosity,
                            intent_penalty=prompt_penalty,
                        )

                if language_override_note:
                    effective_instructions = (
                        f"{effective_instructions}\n\n{language_override_note}"
                    )

                if predicted_target != applied_target:
                    logger.debug(
                        "Predicted route %s but applying handler %s in Plan 05",
                        predicted_target.value,
                        applied_target.value,
                    )

                if should_update_session_instructions and (not instructions_already_updated) and (
                    effective_instructions != _last_instructions
                ):
                    try:
                        await client.async_update_instructions(effective_instructions)
                        _last_instructions = effective_instructions
                    except Exception as exc:
                        await _send_upstream_error(ws, str(exc), config)
                        break

                loop = _asyncio.get_running_loop()
                streamed_audio = False
                heavy_vision_audio_logged = False

                if _is_short_ambiguous_general_chat(
                    current_user_transcript or "",
                    predicted_intent,
                ):
                    turn_user_input_text = _build_short_input_clarification_prompt(
                        current_user_transcript or ""
                    )

                if applied_target == RouteTarget.HEAVY_VISION:
                    spoken_request = (current_user_transcript or "").strip()
                    request_context = (
                        spoken_request if spoken_request else "Describe what is visible."
                    )
                    effective_instructions = (
                        "You are Ally, a warm and capable AI assistant for a visually impaired user. "
                        f"The user's spoken request was: {request_context}. "
                        "You have already received the camera result for this turn. "
                        "Treat the camera result below as ground truth and answer from it directly. "
                        "Never say you lack a camera feed, never say you cannot see, and never say you are audio-only. "
                        "Answer in the same language the user spoke."
                    )
                    if turn_user_input_text:
                        effective_instructions = (
                            f"{effective_instructions}\n\n{turn_user_input_text}"
                        )
                    response_instructions = effective_instructions

                def _forward_audio_delta(delta_bytes: bytes) -> None:
                    nonlocal streamed_audio, heavy_vision_audio_logged
                    streamed_audio = True
                    if (
                        applied_target == RouteTarget.HEAVY_VISION
                        and not heavy_vision_audio_logged
                    ):
                        logger.info("Heavy vision audio sent to user")
                        heavy_vision_audio_logged = True
                    try:
                        running_loop = _asyncio.get_running_loop()
                    except RuntimeError:
                        running_loop = None

                    if running_loop is loop:
                        _schedule_background_task(
                            _safe_send_bytes(ws, delta_bytes),
                            "stream_audio_delta",
                        )
                        return

                    future = _asyncio.run_coroutine_threadsafe(
                        _safe_send_bytes(ws, delta_bytes),
                        loop,
                    )
                    future.result()

                if classification_deferred and (
                    intent_task is None or not intent_task.done()
                ):
                    logger.info(
                        "Audio streaming started — intent not yet resolved (correct behavior)"
                    )

                if (turn_user_input_text is not None or response_instructions is not None) and client.has_buffered_response_events():
                    logger.info(
                        "Buffered upstream response detected — reconnecting before contextual response"
                    )
                    await client.async_reconnect()

                create_response_kwargs: dict[str, Any] = {}
                if response_instructions is not None:
                    create_response_kwargs["instructions"] = response_instructions
                if turn_user_input_text is not None:
                    create_response_kwargs["user_input_text"] = turn_user_input_text

                turn_task = _asyncio.create_task(
                    client.async_create_response_for_prepared_turn_streaming(
                        _forward_audio_delta,
                        **create_response_kwargs,
                    )
                )
                result, queued_data, pending_image_b64, pending_instructions, should_close_session = await _await_turn_result_or_messages(
                    ws=ws,
                    client=client,
                    turn_task=turn_task,
                    config=config,
                    pending_image_b64=pending_image_b64,
                    pending_instructions=pending_instructions,
                    last_response_complete_at=_last_response_complete_at,
                )

                if should_close_session or result is None:
                    break

                if queued_data is not None and (
                    result.response_cancelled or client.was_response_cancelled()
                ):
                    logger.info(
                        "DashScope response cancelled — reconnecting before queued turn"
                    )
                    await client.async_reconnect()

                _last_response_complete_at = time.monotonic()

                if not result.user_transcript:
                    result.user_transcript = current_user_transcript or ""

                current_user_transcript = (
                    result.user_transcript or current_user_transcript or ""
                )
                _last_transcript = current_user_transcript or ""
                resolved_intent = predicted_intent or IntentCategory.GENERAL_CHAT
                if intent_task is not None:
                    try:
                        clf_result = await _asyncio.wait_for(intent_task, timeout=2.0)
                        resolved_intent = clf_result.intent
                        elapsed_ms = (
                            int((time.monotonic() - intent_started_at) * 1000)
                            if intent_started_at is not None
                            else 0
                        )
                        logger.info(
                            "Intent classified: %s in %dms",
                            resolved_intent.value,
                            elapsed_ms,
                        )
                    except _asyncio.TimeoutError:
                        resolved_intent = IntentCategory.GENERAL_CHAT
                        logger.warning(
                            "Intent classification timed out — defaulting to general_chat"
                        )
                    except Exception as exc:
                        resolved_intent = IntentCategory.GENERAL_CHAT
                        logger.warning(
                            "Intent classification failed post-audio: %s",
                            exc,
                        )
                assistant_text = (result.assistant_transcript or "").strip()
                transcript_for_memory = current_user_transcript.strip()
                if _should_auto_extract_memory(
                    transcript_for_memory,
                    resolved_intent,
                    applied_target,
                ):
                    logger.info(
                        "Memory extraction task fired — turn %d (source: user_transcript)",
                        current_turn_index,
                    )
                    _schedule_background_task(
                        _defer_auto_extract(
                            memory_manager,
                            "default",
                            transcript_for_memory,
                            result.assistant_transcript or "",
                            current_turn_index,
                        ),
                        "defer_auto_extract",
                    )
                elif len(transcript_for_memory) < 3:
                    logger.info(
                        "Memory extraction skipped — no usable text (turn %d)",
                        current_turn_index,
                    )
                else:
                    logger.info(
                        "Memory extraction skipped — no qualifying personal fact signal (turn %d)",
                        current_turn_index,
                    )
                if not session_memory_recorded:
                    session_memory.add_turn(
                        current_user_transcript,
                        result.assistant_transcript or "",
                    )

                _response_text = result.assistant_transcript or ""
                _clean_user = (current_user_transcript or "").strip()
                _clean_response = _response_text.strip()
                _db_user_transcript = current_user_transcript or ""
                _skip_turn_logging = False
                if not _clean_user and not _clean_response:
                    logger.debug(
                        "Skipping transcript/reflection logs — both fields empty, silent turn"
                    )
                    _skip_turn_logging = True
                elif not _clean_user and _clean_response:
                    _db_user_transcript = "[no transcript — timeout]"

                _current_intent = str(resolved_intent or predicted_intent)
                _current_target = str(
                    route(
                        resolved_intent
                        or predicted_intent
                        or IntentCategory.GENERAL_CHAT
                    ).target
                )

                if not _skip_turn_logging:
                    _schedule_background_task(
                        correction_store.log_turn(
                            session_id=session_id,
                            turn_id=_turn_id,
                            transcript=_db_user_transcript,
                            response=_response_text,
                            intent=_current_intent,
                            route_target=_current_target,
                        ),
                        "correction_store.log_turn",
                    )

                _is_corr, _corr_sig = _is_correction_signal(current_user_transcript)
                if _is_corr:
                    logger.info(
                        "Correction signal detected: %r — inserting into correction_log",
                        current_user_transcript,
                    )
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

                if not _skip_turn_logging:
                    online_reflection.record_turn(
                        session_id=session_id,
                        turn_id=_turn_id,
                        intent=_current_intent,
                        was_corrected=_is_corr,
                        turns_since_last_correction=_turns_since_corr,
                    )

                last_user_transcript = current_user_transcript

                # Reset per-turn context
                pending_instructions = None

                # Send spoken audio back
                if result.assistant_audio_pcm and not streamed_audio:
                    sent = await _safe_send_bytes(ws, result.assistant_audio_pcm)
                    if not sent:
                        break
                    if (
                        applied_target == RouteTarget.HEAVY_VISION
                        and not heavy_vision_audio_logged
                    ):
                        logger.info("Heavy vision audio sent to user")
                        heavy_vision_audio_logged = True

                # Send assistant transcript
                if result.assistant_transcript:
                    sent = await _safe_send_json(
                        ws,
                        {
                            "type": "transcript",
                            "role": "assistant",
                            "text": result.assistant_transcript,
                            "turn_id": _turn_id,
                        },
                    )
                    if not sent:
                        break

                # Send user transcript (reference only)
                if result.user_transcript and not user_transcript_sent:
                    sent = await _safe_send_json(
                        ws,
                        {
                            "type": "transcript",
                            "role": "user",
                            "text": result.user_transcript,
                            "turn_id": _turn_id,
                        },
                    )
                    if not sent:
                        break

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
                handled, pending_image_b64, pending_instructions = await _handle_control_message(
                    ws,
                    client,
                    raw_text,
                    pending_image_b64,
                    pending_instructions,
                    _last_response_complete_at,
                )
                if not handled:
                    break

    except WebSocketDisconnect:
        logger.info("User WebSocket disconnected — closing DashScope session")

    except Exception as exc:
        logger.error("Unhandled error in realtime route: %s", exc)

    finally:
        heartbeat_task.cancel()
        await _asyncio.gather(heartbeat_task, return_exceptions=True)
        session_memory.clear()
        try:
            await classifier.close()
        except Exception as exc:
            logger.warning("Intent classifier close failed: %s", exc)
        try:
            await mm_client.close()
        except Exception as exc:
            logger.warning("Multimodal client close failed: %s", exc)
        try:
            await memory_manager.close()
        except Exception as exc:
            logger.warning("Memory manager close failed: %s", exc)
        await client.async_close()
        _schedule_background_task(
            offline_replay.run_replay(session_id),
            "offline_replay.run_replay",
        )
        _schedule_background_task(
            offline_replay.promote_priority_memories(session_id),
            "offline_replay.promote_priority_memories",
        )
        logger.info("DashScope session closed — no leak")
