import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.memory import (
    EmbeddingClient,
    EmbeddingError,
    Mem0Extractor,
    MemoryManager,
    MemoryStore,
    SessionMemory,
    compose_memory_context,
)


@pytest.mark.asyncio
async def test_embed_returns_list_of_floats():
    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {"data": [{"embedding": [0.1] * 1024}]}
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)
        client = EmbeddingClient(
            api_key="test",
            base_url="https://example.com",
            model="text-embedding-v4",
            dimensions=1024,
        )
        result = await client.embed("hello")
        assert isinstance(result, list)
        assert len(result) == 1024
        assert all(isinstance(x, float) for x in result)


@pytest.mark.asyncio
async def test_embed_raises_on_error():
    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(side_effect=Exception("connection refused"))
        mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)
        client = EmbeddingClient(
            api_key="test",
            base_url="https://example.com",
            model="text-embedding-v4",
            dimensions=1024,
        )
        with pytest.raises(EmbeddingError):
            await client.embed("hello")


@pytest.mark.asyncio
async def test_save_fact_calls_insert():
    mock_cursor = AsyncMock()
    mock_cursor.lastrowid = 1
    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(return_value=mock_cursor)
    mock_db.commit = AsyncMock()

    with patch("aiosqlite.connect") as mock_connect:
        mock_connect.return_value.__aenter__ = AsyncMock(return_value=mock_db)
        mock_connect.return_value.__aexit__ = AsyncMock(return_value=False)
        store = MemoryStore(db_path=":memory:")
        row_id = await store.save_fact("u1", "my name is Om", [0.1] * 1024)
        assert row_id == 1
        call_args = mock_db.execute.call_args
        sql = call_args[0][0]
        params = call_args[0][1]
        assert "INSERT" in sql.upper()
        assert "my name is Om" in params


@pytest.mark.asyncio
async def test_recall_facts_returns_top_k():
    query = [1.0] + [0.0] * 1023
    fact_a_emb = [1.0] + [0.0] * 1023
    fact_b_emb = [0.0, 1.0] + [0.0] * 1022
    fact_c_emb = [0.7071] * 2 + [0.0] * 1022

    rows = [
        ("fact A", json.dumps(fact_a_emb)),
        ("fact B", json.dumps(fact_b_emb)),
        ("fact C", json.dumps(fact_c_emb)),
    ]

    mock_cursor = AsyncMock()
    mock_cursor.fetchall = AsyncMock(return_value=rows)
    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(return_value=mock_cursor)
    mock_db.__aenter__ = AsyncMock(return_value=mock_db)
    mock_db.__aexit__ = AsyncMock(return_value=False)

    with patch("aiosqlite.connect", return_value=mock_db):
        store = MemoryStore(db_path=":memory:")
        results = await store.recall_facts("u1", query, top_k=2)
        assert len(results) == 2
        assert results[0] == "fact A"


@pytest.mark.asyncio
async def test_recall_facts_returns_empty_when_no_facts():
    mock_cursor = AsyncMock()
    mock_cursor.fetchall = AsyncMock(return_value=[])
    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(return_value=mock_cursor)
    mock_db.__aenter__ = AsyncMock(return_value=mock_db)
    mock_db.__aexit__ = AsyncMock(return_value=False)

    with patch("aiosqlite.connect", return_value=mock_db):
        store = MemoryStore(db_path=":memory:")
        results = await store.recall_facts("u1", [0.1] * 1024)
        assert results == []


@pytest.mark.asyncio
async def test_memory_manager_save_strips_prefix():
    mock_embedder = AsyncMock()
    mock_embedder.embed = AsyncMock(return_value=[0.1] * 1024)
    mock_store = AsyncMock()
    mock_store.save_fact = AsyncMock(return_value=1)

    manager = MemoryManager(embedder=mock_embedder, store=mock_store)
    result = await manager.save("u1", "remember that my doctor is Dr. Sharma")
    assert result == "my doctor is Dr. Sharma"
    mock_store.save_fact.assert_called_once_with(
        "u1", "my doctor is Dr. Sharma", [0.1] * 1024
    )


@pytest.mark.asyncio
async def test_memory_manager_recall_returns_context():
    mock_embedder = AsyncMock()
    mock_embedder.embed = AsyncMock(return_value=[0.1] * 1024)
    mock_store = AsyncMock()
    mock_store.recall_facts = AsyncMock(
        return_value=["my doctor is Dr. Sharma", "my city is Bengaluru"]
    )

    manager = MemoryManager(embedder=mock_embedder, store=mock_store)
    result = await manager.recall("u1", "who is my doctor")
    assert result is not None
    assert "Dr. Sharma" in result


@pytest.mark.asyncio
async def test_memory_manager_recall_returns_none_when_empty():
    mock_embedder = AsyncMock()
    mock_embedder.embed = AsyncMock(return_value=[0.1] * 1024)
    mock_store = AsyncMock()
    mock_store.recall_facts = AsyncMock(return_value=[])

    manager = MemoryManager(embedder=mock_embedder, store=mock_store)
    result = await manager.recall("u1", "who is my doctor")
    assert result is None


def test_session_memory_add_and_recall():
    session = SessionMemory()
    session.add_turn("u1", "a1")
    session.add_turn("u2", "a2")
    session.add_turn("u3", "a3")

    recent = session.get_recent(2)
    assert [turn["user"] for turn in recent] == ["u2", "u3"]
    assert [turn["assistant"] for turn in recent] == ["a2", "a3"]


def test_session_memory_objects_seen():
    session = SessionMemory()
    session.add_turn(
        "show this", "It looks like medicine.", vision_objects=["medicine bottle"]
    )

    objects_seen = session.get_objects_seen()
    assert len(objects_seen) == 1
    assert objects_seen[0]["object_desc"] == "medicine bottle"


def test_session_memory_ring_buffer_max():
    session = SessionMemory(max_turns=5)
    for idx in range(8):
        session.add_turn(f"u{idx}", f"a{idx}")

    recent = session.get_recent(10)
    assert len(recent) == 5
    assert recent[0]["user"] == "u3"
    assert recent[-1]["user"] == "u7"


@pytest.mark.asyncio
async def test_mem0_extractor_returns_facts():
    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {
            "choices": [
                {
                    "message": {
                        "content": '[{"fact": "user name is Om", "category": "IDENTITY", "tier": "long"}]'
                    }
                }
            ]
        }
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        extractor = Mem0Extractor(
            api_key="test",
            base_url="https://example.com/compatible-mode/v1",
            model="qwen-turbo",
        )
        result = await extractor.extract("My name is Om", "Nice to meet you Om")

    assert result == [
        {"fact": "user name is Om", "category": "IDENTITY", "tier": "long"}
    ]


@pytest.mark.asyncio
async def test_mem0_extractor_returns_empty_on_no_facts():
    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {"choices": [{"message": {"content": "[]"}}]}
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        extractor = Mem0Extractor(
            api_key="test",
            base_url="https://example.com/compatible-mode/v1",
            model="qwen-turbo",
        )
        result = await extractor.extract("Hello", "Hi")

    assert result == []


@pytest.mark.asyncio
async def test_mem0_extractor_returns_empty_on_failure():
    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(side_effect=Exception("boom"))
        mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        extractor = Mem0Extractor(
            api_key="test",
            base_url="https://example.com/compatible-mode/v1",
            model="qwen-turbo",
        )
        result = await extractor.extract("Hello", "Hi")

    assert result == []


@pytest.mark.asyncio
async def test_memory_store_short_term_save():
    count_cursor = AsyncMock()
    count_cursor.fetchone = AsyncMock(return_value=(0,))
    insert_cursor = AsyncMock()
    insert_cursor.lastrowid = 7
    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(side_effect=[count_cursor, insert_cursor])
    mock_db.commit = AsyncMock()

    with patch("aiosqlite.connect") as mock_connect:
        mock_connect.return_value.__aenter__ = AsyncMock(return_value=mock_db)
        mock_connect.return_value.__aexit__ = AsyncMock(return_value=False)
        store = MemoryStore(db_path=":memory:")
        row_id = await store.save_fact(
            user_id="u1",
            fact="reading now",
            embedding=[0.1] * 1024,
            tier="short",
            category="OBSERVATION",
        )

    assert row_id == 7
    insert_sql, insert_params = mock_db.execute.await_args_list[1].args
    assert "INSERT INTO short_term_memories" in insert_sql
    assert insert_params[0] == "u1"
    assert insert_params[1] == "reading now"
    assert insert_params[3] == "OBSERVATION"
    assert insert_params[5]


@pytest.mark.asyncio
async def test_memory_store_long_term_dedup():
    existing_embedding = [1.0] + [0.0] * 1023
    select_cursor = AsyncMock()
    select_cursor.fetchall = AsyncMock(
        return_value=[(1, "Om", json.dumps(existing_embedding), "IDENTITY")]
    )
    update_cursor = AsyncMock()
    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(side_effect=[select_cursor, update_cursor])
    mock_db.commit = AsyncMock()
    mock_db.__aenter__ = AsyncMock(return_value=mock_db)
    mock_db.__aexit__ = AsyncMock(return_value=False)

    with patch("aiosqlite.connect", return_value=mock_db):
        store = MemoryStore(db_path=":memory:")
        row_id = await store.save_fact(
            user_id="u1",
            fact="my name is Omkar",
            embedding=existing_embedding,
            tier="long",
            category="IDENTITY",
        )

    assert row_id == 1
    executed_sql = [call.args[0] for call in mock_db.execute.await_args_list]
    assert any("UPDATE long_term_memories" in sql for sql in executed_sql)
    assert not any("INSERT INTO long_term_memories" in sql for sql in executed_sql)


@pytest.mark.asyncio
async def test_memory_store_purge_expired():
    delete_cursor = AsyncMock()
    delete_cursor.rowcount = 2
    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(return_value=delete_cursor)
    mock_db.commit = AsyncMock()
    mock_db.__aenter__ = AsyncMock(return_value=mock_db)
    mock_db.__aexit__ = AsyncMock(return_value=False)

    with patch("aiosqlite.connect", return_value=mock_db):
        store = MemoryStore(db_path=":memory:")
        deleted = await store.purge_expired()

    assert deleted == 2
    sql = mock_db.execute.await_args.args[0]
    assert "DELETE FROM short_term_memories WHERE expires_at < ?" == sql


@pytest.mark.asyncio
async def test_memory_manager_auto_extract_stores_facts():
    mock_embedder = AsyncMock()
    mock_embedder.embed = AsyncMock(return_value=[0.2] * 1024)
    mock_store = AsyncMock()
    mock_store.save_fact = AsyncMock(return_value=1)
    mock_extractor = MagicMock()
    mock_extractor.extract = AsyncMock(
        return_value=[{"fact": "Om", "category": "IDENTITY", "tier": "long"}]
    )

    manager = MemoryManager(
        embedder=mock_embedder,
        store=mock_store,
        extractor=mock_extractor,
    )
    await manager.auto_extract_and_store("default", "My name is Om", "Hello Om")

    mock_store.save_fact.assert_called_once_with(
        "default",
        "Om",
        [0.2] * 1024,
        tier="long",
        category="IDENTITY",
    )


@pytest.mark.asyncio
async def test_no_facts_extracted_does_not_write_db(caplog):
    caplog.set_level("INFO")
    mock_embedder = AsyncMock()
    mock_embedder.embed = AsyncMock(return_value=[0.2] * 1024)
    mock_store = AsyncMock()
    mock_store.save_fact = AsyncMock(return_value=1)
    mock_extractor = MagicMock()
    mock_extractor.extract = AsyncMock(return_value=[])

    manager = MemoryManager(
        embedder=mock_embedder,
        store=mock_store,
        extractor=mock_extractor,
    )
    await manager.auto_extract_and_store(
        "default",
        "Hello! How can I help you today?",
        "Hello! How can I help you today?",
        turn_index=0,
    )

    mock_store.save_fact.assert_not_called()
    assert "Memory extraction: no facts found — nothing saved (turn 0)" in caplog.text


@pytest.mark.asyncio
async def test_recall_all_tiers_returns_combined_context():
    mock_embedder = AsyncMock()
    mock_embedder.embed = AsyncMock(return_value=[0.1] * 1024)
    mock_store = AsyncMock()
    mock_store.recall_facts = AsyncMock(side_effect=[["fact A"], ["fact B"]])

    manager = MemoryManager(embedder=mock_embedder, store=mock_store)
    result = await manager.recall_all_tiers("default", "test query")

    assert result is not None
    assert "fact A" in result
    assert "fact B" in result


def test_compose_memory_context_empty_inputs():
    result = compose_memory_context([], None, None, [])
    assert result == ""
