import json
from unittest.mock import AsyncMock

import aiosqlite
import pytest

from core.memory.memory_manager import MemoryManager
from core.memory.memory_store import MemoryStore


async def _insert_long_term(
    db_path: str,
    user_id: str,
    fact: str,
    created_at: str,
    priority: int = 0,
) -> None:
    async with aiosqlite.connect(db_path) as db:
        _ = await db.execute(
            """
            INSERT INTO long_term_memories (
                user_id,
                fact,
                embedding_json,
                category,
                priority,
                created_at,
                updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                user_id,
                fact,
                json.dumps([0.1] * 4),
                "GENERAL",
                priority,
                created_at,
                created_at,
            ),
        )
        await db.commit()


@pytest.mark.asyncio
async def test_mark_priority_facts_marks_matching_rows(tmp_path):
    db_path = str(tmp_path / "memory.sqlite")
    store = MemoryStore(db_path=db_path)
    await store.initialize_all()
    await _insert_long_term(
        db_path=db_path,
        user_id="default",
        fact="Your name is Om.",
        created_at="2026-01-01T00:00:00",
    )

    updated = await store.mark_priority_facts("default", ["name is Om"])

    async with aiosqlite.connect(db_path) as db:
        cursor = await db.execute(
            "SELECT priority FROM long_term_memories WHERE user_id = ?",
            ("default",),
        )
        row = await cursor.fetchone()

    assert updated == 1
    assert row == (1,)


@pytest.mark.asyncio
async def test_get_priority_facts_returns_latest_first(tmp_path):
    db_path = str(tmp_path / "memory.sqlite")
    store = MemoryStore(db_path=db_path)
    await store.initialize_all()
    await _insert_long_term(
        db_path=db_path,
        user_id="default",
        fact="Older fact",
        created_at="2026-01-01T00:00:00",
        priority=1,
    )
    await _insert_long_term(
        db_path=db_path,
        user_id="default",
        fact="Newer fact",
        created_at="2026-01-02T00:00:00",
        priority=1,
    )

    facts = await store.get_priority_facts("default", top_k=2)

    assert facts == ["Newer fact", "Older fact"]


@pytest.mark.asyncio
async def test_get_priority_facts_includes_higher_priorities(tmp_path):
    db_path = str(tmp_path / "memory.sqlite")
    store = MemoryStore(db_path=db_path)
    await store.initialize_all()
    await _insert_long_term(
        db_path=db_path,
        user_id="default",
        fact="Priority 1 fact",
        created_at="2026-01-01T00:00:00",
        priority=1,
    )
    await _insert_long_term(
        db_path=db_path,
        user_id="default",
        fact="Priority 2 fact",
        created_at="2026-01-02T00:00:00",
        priority=2,
    )

    facts = await store.get_priority_facts("default", top_k=5)

    assert facts == ["Priority 2 fact", "Priority 1 fact"]


@pytest.mark.asyncio
async def test_memory_manager_get_startup_memory_context_returns_formatted_lines():
    mock_embedder = AsyncMock()
    mock_store = AsyncMock()
    mock_store.get_priority_facts = AsyncMock(
        return_value=["Your name is Om.", "Your city is Bengaluru."]
    )

    manager = MemoryManager(embedder=mock_embedder, store=mock_store)
    result = await manager.get_startup_memory_context("default")

    assert result == (
        "Remembered context:\n- Your name is Om.\n- Your city is Bengaluru."
    )
