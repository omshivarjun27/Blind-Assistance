"""Offline replay and memory promotion for Plan 10."""

from __future__ import annotations

from collections import Counter
import json
import logging
import re
from importlib import import_module
from typing import Protocol
from typing import cast

import aiosqlite
import httpx

from shared.config import settings

from .correction_store import CorrectionStore

logger = logging.getLogger(__name__)


class _PatchStoreProtocol(Protocol):
    async def create_patch(
        self,
        scope: str,
        target: str,
        before: dict[str, object],
        after: dict[str, object],
        description: str,
    ) -> int: ...


class _MemoryStoreProtocol(Protocol):
    async def mark_priority_facts(
        self,
        user_id: str,
        facts: list[str],
    ) -> int: ...


_MEMORY_RECALL_PATTERNS: tuple[str, ...] = (
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

_REPLAY_SYSTEM_PROMPT = (
    "You are analyzing a voice assistant's conversation turn to\n"
    "identify what caused an incorrect response."
)

_REPLAY_USER_PROMPT = (
    "Here is a sequence of conversation turns ending in a user\n"
    " correction. The turns are in chronological order.\n\n"
    " Turns:\n"
    " {formatted_turns}\n\n"
    " Correction signal: {correction_signal}\n"
    " Intent at time of correction: {intent_at_time}\n\n"
    " Identify the root cause of the incorrect response and suggest\n"
    " ONE small fix. Respond in valid JSON only:\n"
    ' {{"root_cause": "...", "suggested_scope": "routing|prompt|threshold",\n'
    '  "suggested_change": "..."}}'
)


class OfflineReplay:
    def __init__(
        self,
        db_path: str,
        correction_store: CorrectionStore,
        patch_store: _PatchStoreProtocol,
        priority_min_recalls: int,
        turbo_model: str,
        api_key: str,
        base_url: str,
        memory_store: _MemoryStoreProtocol | None = None,
    ) -> None:
        self._db_path: str = db_path
        self._correction_store: CorrectionStore = correction_store
        self._patch_store: _PatchStoreProtocol = patch_store
        self._priority_min_recalls: int = priority_min_recalls
        self._turbo_model: str = turbo_model
        self._api_key: str = api_key
        self._base_url: str = base_url.rstrip("/")
        if memory_store is None:
            memory_store_module = import_module("core.memory.memory_store")
            memory_store = cast(
                _MemoryStoreProtocol,
                memory_store_module.MemoryStore.from_settings(),
            )
        self._memory_store: _MemoryStoreProtocol = memory_store

    @classmethod
    def from_settings(cls) -> "OfflineReplay":
        patch_store_module = import_module("core.learning.patch_store")
        return cls(
            db_path=settings.MEMORY_DB_PATH,
            correction_store=CorrectionStore.from_settings(),
            patch_store=cast(
                _PatchStoreProtocol,
                patch_store_module.PatchStore.from_settings(),
            ),
            priority_min_recalls=getattr(
                settings,
                "LEARNING_PRIORITY_PROMOTION_MIN_RECALLS",
                3,
            ),
            turbo_model=settings.QWEN_TURBO_MODEL,
            api_key=settings.get_api_key(),
            base_url=settings.DASHSCOPE_COMPAT_BASE,
        )

    @staticmethod
    def _format_turns(turns: list[dict[str, object]]) -> str:
        lines: list[str] = []
        for index, turn in enumerate(turns, start=1):
            user_text = str(turn.get("user_transcript") or "")
            assistant_text = str(turn.get("assistant_response") or "")
            lines.append(f"{index}. User: {user_text}\n   Assistant: {assistant_text}")
        return "\n".join(lines)

    @staticmethod
    def _extract_first_sentence(text: str) -> str:
        cleaned = text.strip()
        if not cleaned:
            return ""
        parts = re.split(r"(?<=[.!?])\s+", cleaned, maxsplit=1)
        return parts[0].strip()

    async def _request_replay_patch(
        self,
        formatted_turns: str,
        correction_signal: str,
        intent_at_time: str,
    ) -> dict[str, str] | None:
        payload = {
            "model": self._turbo_model,
            "messages": [
                {"role": "system", "content": _REPLAY_SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": _REPLAY_USER_PROMPT.format(
                        formatted_turns=formatted_turns,
                        correction_signal=correction_signal,
                        intent_at_time=intent_at_time,
                    ),
                },
            ],
            "response_format": {"type": "json_object"},
        }

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    f"{self._base_url}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self._api_key}",
                        "Content-Type": "application/json",
                    },
                    json=payload,
                )
                _ = response.raise_for_status()
                data = response.json()
        except Exception as exc:
            logger.warning("offline replay model call failed: %s", exc)
            return None

        try:
            if not isinstance(data, dict):
                logger.warning("offline replay response was not a JSON object")
                return None
            choices_obj = data.get("choices")
            if not isinstance(choices_obj, list) or not choices_obj:
                logger.warning("offline replay response missing choices")
                return None
            first_choice = choices_obj[0]
            if not isinstance(first_choice, dict):
                logger.warning("offline replay first choice was malformed")
                return None
            message_obj = first_choice.get("message")
            if not isinstance(message_obj, dict):
                logger.warning("offline replay message payload was malformed")
                return None
            content_obj = message_obj.get("content")
            parsed = json.loads(str(content_obj))
            if not isinstance(parsed, dict):
                logger.warning("offline replay JSON was not an object")
                return None
            root_cause_obj = parsed.get("root_cause")
            suggested_scope_obj = parsed.get("suggested_scope")
            suggested_change_obj = parsed.get("suggested_change")
            if not all(
                isinstance(value, str) and value.strip()
                for value in (
                    root_cause_obj,
                    suggested_scope_obj,
                    suggested_change_obj,
                )
            ):
                logger.warning("offline replay JSON missing required keys")
                return None
            root_cause = str(root_cause_obj)
            suggested_scope = str(suggested_scope_obj)
            suggested_change = str(suggested_change_obj)
            return {
                "root_cause": root_cause.strip(),
                "suggested_scope": suggested_scope.strip(),
                "suggested_change": suggested_change.strip(),
            }
        except Exception as exc:
            logger.warning("offline replay JSON parse failed: %s", exc)
            return None

    async def run_replay(self, session_id: str) -> None:
        try:
            corrections = await self._correction_store.get_corrections(
                session_id=session_id,
                limit=1000,
            )
            for correction in corrections:
                turn_id_obj = correction.get("turn_id")
                if not isinstance(turn_id_obj, str) or not turn_id_obj:
                    continue
                correction_signal = str(correction.get("correction_signal") or "")
                intent_at_time = str(correction.get("intent_at_time") or "")
                turn_window = await self._correction_store.get_turn_window(
                    session_id=session_id,
                    turn_id=turn_id_obj,
                    before=3,
                    after=3,
                )
                if not turn_window:
                    continue

                replay_result = await self._request_replay_patch(
                    formatted_turns=self._format_turns(turn_window),
                    correction_signal=correction_signal,
                    intent_at_time=intent_at_time,
                )
                if replay_result is None:
                    continue

                _ = await self._patch_store.create_patch(
                    scope=replay_result["suggested_scope"],
                    target=intent_at_time,
                    before={"description": "pre-replay state"},
                    after={"description": replay_result["suggested_change"]},
                    description=replay_result["root_cause"],
                )
        except Exception as exc:
            logger.warning("run_replay failed: %s", exc)

    async def promote_priority_memories(self, session_id: str) -> None:
        try:
            async with aiosqlite.connect(self._db_path) as db:
                db.row_factory = aiosqlite.Row
                cursor = await db.execute(
                    """
                    SELECT user_transcript, assistant_response
                    FROM transcript_log
                    WHERE session_id = ?
                    ORDER BY id ASC
                    """,
                    (session_id,),
                )
                rows = await cursor.fetchall()

            topic_counter: Counter[str] = Counter()
            for row in rows:
                user_text = str(row["user_transcript"] or "")
                cleaned_user = user_text.lower().strip()
                if not any(
                    pattern in cleaned_user for pattern in _MEMORY_RECALL_PATTERNS
                ):
                    continue
                topic = self._extract_first_sentence(
                    str(row["assistant_response"] or "")
                )
                if topic:
                    topic_counter[topic] += 1

            priority_topics = [
                topic
                for topic, count in topic_counter.items()
                if count >= self._priority_min_recalls
            ]
            if priority_topics:
                _ = await self._memory_store.mark_priority_facts(
                    user_id="default",
                    facts=priority_topics,
                )
        except Exception as exc:
            logger.warning("promote_priority_memories failed: %s", exc)
