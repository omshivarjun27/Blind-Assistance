import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.memory import EmbeddingClient, EmbeddingError, MemoryManager, MemoryStore


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
