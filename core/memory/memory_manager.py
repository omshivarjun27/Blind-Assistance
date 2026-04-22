"""Ally Vision v2 — MemoryManager: composes embedder + store."""

from __future__ import annotations

import logging
from importlib import import_module
from typing import Any

from .embedding_client import EmbeddingClient, EmbeddingError
from .mem0_extractor import Mem0Extractor
from .memory_context_composer import compose_memory_context
from .session_memory import SessionMemory
from core.orchestrator.prompt_builder import build_memory_fact

logger = logging.getLogger(__name__)

DEFAULT_RECALL_TOP_K = 5
DEFAULT_RECALL_THRESHOLD = 0.72
_FORCE_EXTRACT_TRIGGERS = (
    "remember",
    "ಯಾದ",
    "याद",
    "ನೆನಪಿಡು",
    "ನನ್ನ ಹೆಸರು",
    "मेरा नाम",
    "my name is",
    "my city is",
    "i live in",
    "my doctor is",
    "update that",
    "save this",
    "note that",
    "don't forget",
)


def _should_force_extract(transcript: str) -> bool:
    lowered = transcript.lower()
    return any(token in lowered for token in _FORCE_EXTRACT_TRIGGERS)


def _normalize_category(category: str) -> str:
    cleaned = category.strip().upper() or "GENERAL"
    return cleaned if cleaned in {
        "NAME",
        "LOCATION",
        "MEDICAL",
        "PREFERENCE",
        "RELATIONSHIP",
        "GENERAL",
    } else "GENERAL"


def _infer_category_from_fact(fact: str) -> str:
    lowered = fact.lower()
    if "name is" in lowered:
        return "NAME"
    if "city" in lowered or "live" in lowered or "from" in lowered:
        return "LOCATION"
    if "doctor" in lowered or "medicine" in lowered or "medical" in lowered:
        return "MEDICAL"
    if "like" in lowered or "prefer" in lowered or "favorite" in lowered:
        return "PREFERENCE"
    if "mother" in lowered or "father" in lowered or "wife" in lowered or "husband" in lowered:
        return "RELATIONSHIP"
    return "GENERAL"


class MemoryManager:
    def __init__(
        self,
        embedder: EmbeddingClient,
        store: Any,
        extractor: Mem0Extractor | None = None,
    ) -> None:
        self.embedder: EmbeddingClient = embedder
        self.store: Any = store
        self.extractor: Mem0Extractor | None = extractor
        self.session_memory = SessionMemory()

    @classmethod
    def from_settings(cls) -> "MemoryManager":
        memory_store_cls = import_module("core.memory.memory_store").MemoryStore
        return cls(
            embedder=EmbeddingClient.from_settings(),
            store=memory_store_cls.from_settings(),
            extractor=Mem0Extractor.from_settings(),
        )

    async def auto_extract_and_store(
        self,
        user_id: str,
        user_transcript: str,
        assistant_transcript: str,
        turn_index: int | None = None,
    ) -> None:
        if self.extractor is None:
            return
        try:
            logger.debug(
                "Memory extraction input: %r + %r",
                user_transcript,
                assistant_transcript,
            )
            facts = await self.extractor.extract(user_transcript, assistant_transcript)
            logger.debug("Memory extraction facts: %r", facts)
            if not facts:
                if turn_index is not None:
                    logger.info(
                        "Memory extraction: no facts found — nothing saved (turn %d)",
                        turn_index,
                    )
                return
            saved_count = 0
            for fact_data in facts:
                fact_text = fact_data.get("fact", "").strip()
                category = _normalize_category(fact_data.get("category", "GENERAL"))
                tier = fact_data.get("tier", "long")
                if not fact_text:
                    continue
                try:
                    embedding = await self.embedder.embed(fact_text)
                    await self.store.save_fact(
                        user_id,
                        fact_text,
                        embedding,
                        tier=tier,
                        category=category,
                        priority=1,
                        dedupe_by_category=category != "GENERAL",
                    )
                    saved_count += 1
                except Exception as exc:
                    logger.warning(
                        "auto_extract: save_fact failed for %r: %s", fact_text, exc
                    )
            if turn_index is not None and saved_count > 0:
                logger.info(
                    "Memory saved: %d facts (turn %d)",
                    saved_count,
                    turn_index,
                )
        except Exception as exc:
            logger.warning("auto_extract_and_store failed: %s", exc)

    async def recall_all_tiers(
        self,
        user_id: str,
        query: str,
        top_k: int = 3,
    ) -> str | None:
        try:
            embedding = await self.embedder.embed(query)
            st_facts = await self.store.recall_facts(
                user_id, embedding, top_k, tier="short"
            )
            lt_facts = await self.store.recall_facts(
                user_id, embedding, top_k, tier="long"
            )
            st_str = "\n".join(st_facts) if st_facts else None
            lt_str = "\n".join(lt_facts) if lt_facts else None
            result = compose_memory_context([], st_str, lt_str, [])
            return result if result else None
        except Exception as exc:
            logger.warning("recall_all_tiers failed: %s", exc)
            return None

    async def save(self, user_id: str, raw_utterance: str) -> str:
        """Strip memory-save prefix, embed, and store.

        Returns the cleaned fact string for confirmation response.
        """
        cleaned_fact = build_memory_fact(raw_utterance)
        category = _infer_category_from_fact(cleaned_fact)

        if self.extractor is not None:
            extracted = await self.extractor.extract(cleaned_fact, "")
            if extracted:
                first = extracted[0]
                fact_candidate = str(first.get("fact", "")).strip()
                if fact_candidate:
                    cleaned_fact = fact_candidate
                    category = _normalize_category(first.get("category", category))

        embedding = await self.embedder.embed(cleaned_fact)
        await self.store.save_fact(
            user_id,
            cleaned_fact,
            embedding,
            category=category,
            priority=2,
            dedupe_by_category=category != "GENERAL",
        )
        logger.info("Memory saved for user %s: %s", user_id, cleaned_fact)
        return cleaned_fact

    async def recall(
        self,
        user_id: str,
        query: str,
        top_k: int = DEFAULT_RECALL_TOP_K,
        threshold: float = DEFAULT_RECALL_THRESHOLD,
    ) -> str | None:
        """Embed query, retrieve top_k facts, return as context string.

        Returns None if no relevant facts are stored.
        """
        facts = await self.retrieve_relevant_facts(
            user_id=user_id,
            query=query,
            top_k=top_k,
            threshold=threshold,
        )
        if not facts:
            return None
        return "\n".join(facts)

    async def retrieve_relevant_facts(
        self,
        user_id: str,
        query: str,
        top_k: int = DEFAULT_RECALL_TOP_K,
        threshold: float = DEFAULT_RECALL_THRESHOLD,
    ) -> list[str]:
        logger.info(
            'Memory retrieval — query: "%s" top_k=%d threshold=%.2f',
            query,
            top_k,
            threshold,
        )
        try:
            embedding = await self.embedder.embed(query)
        except EmbeddingError as exc:
            logger.warning("Embedding failed for recall: %s", exc)
            return []
        return await self.store.recall_facts(
            user_id,
            embedding,
            top_k,
            threshold=threshold,
        )

    async def get_startup_memory_context(
        self,
        user_id: str,
        top_k: int = 5,
    ) -> str | None:
        """
        Returns a formatted string of priority memories for session-start
        injection. Returns None if nothing is found or on any failure.
        Never raises.
        """
        try:
            priority_facts = await self.get_priority_facts(user_id=user_id, top_k=top_k)
            if not priority_facts:
                return None
            lines = [f"- {fact}" for fact in priority_facts]
            return "Remembered context:\n" + "\n".join(lines)
        except Exception as exc:
            logger.warning("get_startup_memory_context failed: %s", exc)
            return None

    async def get_priority_facts(
        self,
        user_id: str,
        top_k: int = 10,
    ) -> list[str]:
        try:
            return await self.store.get_priority_facts(user_id=user_id, top_k=top_k)
        except Exception as exc:
            logger.warning("get_priority_facts failed: %s", exc)
            return []

    async def close(self) -> None:
        if self.extractor is not None:
            await self.extractor.close()
