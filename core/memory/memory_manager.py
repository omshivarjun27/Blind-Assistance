"""Ally Vision v2 — MemoryManager: composes embedder + store."""

from __future__ import annotations

import logging
from importlib import import_module
from typing import Any

from .embedding_client import EmbeddingClient, EmbeddingError
from core.orchestrator.prompt_builder import build_memory_fact

logger = logging.getLogger(__name__)


class MemoryManager:
    def __init__(
        self,
        embedder: EmbeddingClient,
        store: Any,
    ) -> None:
        self.embedder: EmbeddingClient = embedder
        self.store: Any = store

    @classmethod
    def from_settings(cls) -> "MemoryManager":
        memory_store_cls = import_module("core.memory.memory_store").MemoryStore
        return cls(
            embedder=EmbeddingClient.from_settings(),
            store=memory_store_cls.from_settings(),
        )

    async def save(self, user_id: str, raw_utterance: str) -> str:
        """Strip memory-save prefix, embed, and store.

        Returns the cleaned fact string for confirmation response.
        """
        cleaned_fact = build_memory_fact(raw_utterance)
        embedding = await self.embedder.embed(cleaned_fact)
        await self.store.save_fact(user_id, cleaned_fact, embedding)
        logger.info("Memory saved for user %s: %s", user_id, cleaned_fact)
        return cleaned_fact

    async def recall(
        self,
        user_id: str,
        query: str,
        top_k: int = 3,
    ) -> str | None:
        """Embed query, retrieve top_k facts, return as context string.

        Returns None if no relevant facts are stored.
        """
        try:
            embedding = await self.embedder.embed(query)
        except EmbeddingError as exc:
            logger.warning("Embedding failed for recall: %s", exc)
            return None
        facts = await self.store.recall_facts(user_id, embedding, top_k)
        if not facts:
            return None
        return "\n".join(facts)
