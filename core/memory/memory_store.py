"""Ally Vision v2 — SQLite memory store with cosine similarity recall."""

from __future__ import annotations

import datetime
import json

import aiosqlite
import numpy as np

from shared.config import settings


class MemoryStore:
    def __init__(self, db_path: str) -> None:
        self._db_path: str = db_path

    @classmethod
    def from_settings(cls) -> "MemoryStore":
        return cls(db_path=settings.MEMORY_DB_PATH)

    async def initialize(self) -> None:
        """Create the memories table and index if not exists."""
        async with aiosqlite.connect(self._db_path) as db:
            await db.execute(
                """
                  CREATE TABLE IF NOT EXISTS memories (
                      id            INTEGER PRIMARY KEY AUTOINCREMENT,
                      user_id       TEXT NOT NULL,
                      fact          TEXT NOT NULL,
                      embedding_json TEXT NOT NULL,
                      created_at    TEXT NOT NULL
                  )
                """
            )
            await db.execute(
                """
                  CREATE INDEX IF NOT EXISTS memories_user_id
                  ON memories (user_id)
                """
            )
            await db.commit()

    async def save_fact(
        self,
        user_id: str,
        fact: str,
        embedding: list[float],
    ) -> int:
        """Store a fact + its embedding. Returns the new row id."""
        embedding_json = json.dumps(embedding)
        created_at = datetime.datetime.now(datetime.timezone.utc).isoformat()
        async with aiosqlite.connect(self._db_path) as db:
            cursor = await db.execute(
                (
                    "INSERT INTO memories "
                    "(user_id, fact, embedding_json, created_at) "
                    "VALUES (?, ?, ?, ?)"
                ),
                (user_id, fact, embedding_json, created_at),
            )
            await db.commit()
            row_id = cursor.lastrowid
            if row_id is None:
                raise RuntimeError("SQLite insert did not return a row id")
            return row_id

    async def recall_facts(
        self,
        user_id: str,
        query_embedding: list[float],
        top_k: int = 3,
    ) -> list[str]:
        """Return top_k facts most similar to query_embedding."""
        async with aiosqlite.connect(self._db_path) as db:
            cursor = await db.execute(
                "SELECT fact, embedding_json FROM memories WHERE user_id = ?",
                (user_id,),
            )
            raw_rows = await cursor.fetchall()

        rows = [(str(row[0]), str(row[1])) for row in raw_rows]

        if not rows:
            return []

        q = np.array(query_embedding, dtype=np.float32)
        q_norm = np.linalg.norm(q)
        if q_norm == 0:
            return [row[0] for row in rows[:top_k]]

        scored: list[tuple[float, str]] = []
        for fact, emb_json in rows:
            v = np.array(json.loads(emb_json), dtype=np.float32)
            v_norm = np.linalg.norm(v)
            if v_norm == 0:
                similarity = 0.0
            else:
                similarity = float(np.dot(q, v) / (q_norm * v_norm))
            scored.append((similarity, fact))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [fact for _, fact in scored[:top_k]]
