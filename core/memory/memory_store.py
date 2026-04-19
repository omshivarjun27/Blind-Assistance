"""Ally Vision v2 — SQLite memory store with multi-tier cosine recall."""

from __future__ import annotations

import datetime
import json
import logging

import aiosqlite
import numpy as np

from shared.config import settings

logger = logging.getLogger(__name__)


class MemoryStore:
    def __init__(self, db_path: str) -> None:
        self._db_path: str = db_path

    @classmethod
    def from_settings(cls) -> "MemoryStore":
        return cls(db_path=settings.MEMORY_DB_PATH)

    @staticmethod
    def _utcnow_iso() -> str:
        return datetime.datetime.now(datetime.timezone.utc).isoformat()

    @staticmethod
    def _score_rows(
        rows: list[tuple[str, str]],
        query_embedding: list[float],
    ) -> list[tuple[float, str]]:
        if not rows:
            return []

        q = np.array(query_embedding, dtype=np.float32)
        q_norm = np.linalg.norm(q)
        if q_norm == 0:
            return [(0.0, fact) for fact, _ in rows]

        scored: list[tuple[float, str]] = []
        for fact, emb_json in rows:
            v = np.array(json.loads(emb_json), dtype=np.float32)
            v_norm = np.linalg.norm(v)
            similarity = 0.0 if v_norm == 0 else float(np.dot(q, v) / (q_norm * v_norm))
            scored.append((similarity, fact))
        scored.sort(key=lambda x: x[0], reverse=True)
        return scored

    @staticmethod
    def _looks_like_identity_fact(fact: str) -> bool:
        normalized = fact.strip().rstrip(".")
        if not normalized:
            return False
        return len(normalized.split()) <= 6

    async def initialize_all(self) -> None:
        """Create/migrate long-term and short-term memory tables."""
        async with aiosqlite.connect(self._db_path) as db:
            legacy_cursor = await db.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='memories'"
            )
            has_legacy = await legacy_cursor.fetchone()
            long_cursor = await db.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='long_term_memories'"
            )
            has_long_term = await long_cursor.fetchone()
            if has_legacy and not has_long_term:
                await db.execute("ALTER TABLE memories RENAME TO long_term_memories")

            await db.execute(
                """
                  CREATE TABLE IF NOT EXISTS long_term_memories (
                      id            INTEGER PRIMARY KEY AUTOINCREMENT,
                      user_id       TEXT NOT NULL,
                      fact          TEXT NOT NULL,
                      embedding_json TEXT NOT NULL,
                      category      TEXT NOT NULL DEFAULT 'GENERAL',
                      priority      INTEGER DEFAULT 0,
                      created_at    TEXT NOT NULL,
                      updated_at    TEXT NOT NULL DEFAULT ''
                  )
                """
            )
            schema_cursor = await db.execute("PRAGMA table_info(long_term_memories)")
            schema_rows = await schema_cursor.fetchall()
            columns = {str(row[1]) for row in schema_rows}
            if "category" not in columns:
                await db.execute(
                    "ALTER TABLE long_term_memories ADD COLUMN category TEXT NOT NULL DEFAULT 'GENERAL'"
                )
            if "updated_at" not in columns:
                await db.execute(
                    "ALTER TABLE long_term_memories ADD COLUMN updated_at TEXT NOT NULL DEFAULT ''"
                )
            if "priority" not in columns:
                try:
                    await db.execute(
                        "ALTER TABLE long_term_memories ADD COLUMN priority INTEGER DEFAULT 0"
                    )
                except Exception as exc:
                    logger.info("priority column migration skipped: %s", exc)
            await db.execute(
                """
                  CREATE INDEX IF NOT EXISTS long_term_memories_user_id
                  ON long_term_memories (user_id)
                """
            )
            await db.execute(
                """
                  CREATE TABLE IF NOT EXISTS short_term_memories (
                      id             INTEGER PRIMARY KEY AUTOINCREMENT,
                      user_id        TEXT NOT NULL,
                      fact           TEXT NOT NULL,
                      embedding_json TEXT NOT NULL,
                      category       TEXT NOT NULL DEFAULT 'GENERAL',
                      created_at     TEXT NOT NULL,
                      expires_at     TEXT NOT NULL
                  )
                """
            )
            await db.execute(
                "CREATE INDEX IF NOT EXISTS stm_user_id ON short_term_memories(user_id)"
            )
            await db.commit()
        await self.purge_expired()

    async def initialize(self) -> None:
        """Backward-compatible alias for multi-table initialization."""
        await self.initialize_all()

    async def save_fact(
        self,
        user_id: str,
        fact: str,
        embedding: list[float],
        tier: str = "long",
        category: str = "GENERAL",
    ) -> int:
        """Store a fact + its embedding. Returns the new row id."""
        embedding_json = json.dumps(embedding)
        created_at = self._utcnow_iso()

        if tier == "short":
            expires_at = (
                datetime.datetime.now(datetime.timezone.utc)
                + datetime.timedelta(days=7)
            ).isoformat()
            async with aiosqlite.connect(self._db_path) as db:
                count_cursor = await db.execute(
                    "SELECT COUNT(*) FROM short_term_memories WHERE user_id=?",
                    (user_id,),
                )
                count_row = await count_cursor.fetchone()
                count = int(count_row[0]) if count_row else 0
                if count >= 100:
                    await db.execute(
                        "DELETE FROM short_term_memories WHERE id IN "
                        "(SELECT id FROM short_term_memories WHERE user_id=? "
                        "ORDER BY created_at ASC LIMIT 1)",
                        (user_id,),
                    )
                cursor = await db.execute(
                    "INSERT INTO short_term_memories "
                    "(user_id, fact, embedding_json, category, created_at, expires_at) "
                    "VALUES (?, ?, ?, ?, ?, ?)",
                    (user_id, fact, embedding_json, category, created_at, expires_at),
                )
                await db.commit()
                row_id = cursor.lastrowid
                if row_id is None:
                    raise RuntimeError("SQLite insert did not return a row id")
                return row_id

        async with aiosqlite.connect(self._db_path) as db:
            cursor = await db.execute(
                "SELECT id, fact, embedding_json, category FROM long_term_memories WHERE user_id=?",
                (user_id,),
            )
            raw_rows = await cursor.fetchall()

        rows = raw_rows if isinstance(raw_rows, list) else []
        q = np.array(embedding, dtype=float)
        q_norm = np.linalg.norm(q)
        best_id: int | None = None
        best_sim = 0.0
        identity_fallback_id: int | None = None
        for row_id, existing_fact, emb_json, existing_category in rows:
            e = np.array(json.loads(str(emb_json)), dtype=float)
            e_norm = np.linalg.norm(e)
            if q_norm > 0 and e_norm > 0:
                similarity = float(np.dot(q, e) / (q_norm * e_norm))
                if similarity > best_sim:
                    best_sim = similarity
                    best_id = int(row_id)
            if (
                category.upper() == "IDENTITY"
                and str(existing_category).upper() == "IDENTITY"
                and self._looks_like_identity_fact(str(existing_fact))
                and self._looks_like_identity_fact(fact)
                and identity_fallback_id is None
            ):
                identity_fallback_id = int(row_id)

        if identity_fallback_id is not None and best_sim <= 0.92:
            best_id = identity_fallback_id
            best_sim = 1.0

        updated_at = created_at
        async with aiosqlite.connect(self._db_path) as db:
            if best_id is not None and best_sim > 0.92:
                await db.execute(
                    "UPDATE long_term_memories SET fact=?, embedding_json=?, category=?, updated_at=? WHERE id=?",
                    (fact, embedding_json, category, updated_at, best_id),
                )
                await db.commit()
                return best_id

            cursor = await db.execute(
                "INSERT INTO long_term_memories "
                "(user_id, fact, embedding_json, category, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (user_id, fact, embedding_json, category, created_at, updated_at),
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
        tier: str = "long",
        threshold: float | None = None,
    ) -> list[str]:
        """Return top_k facts most similar to query_embedding."""
        now = self._utcnow_iso()

        def _select_facts(scored_rows: list[tuple[float, str]]) -> list[str]:
            if threshold is not None:
                scored_rows = [
                    (score, fact)
                    for score, fact in scored_rows
                    if score >= threshold
                ]
            return [fact for _, fact in scored_rows[:top_k]]

        async with aiosqlite.connect(self._db_path) as db:
            if tier == "short":
                cursor = await db.execute(
                    "SELECT fact, embedding_json FROM short_term_memories "
                    "WHERE user_id = ? AND expires_at > ?",
                    (user_id, now),
                )
                raw_rows = await cursor.fetchall()
                rows = [(str(row[0]), str(row[1])) for row in raw_rows]
                scored = self._score_rows(rows, query_embedding)
                return _select_facts(scored)

            if tier == "all":
                long_cursor = await db.execute(
                    "SELECT fact, embedding_json FROM long_term_memories WHERE user_id = ?",
                    (user_id,),
                )
                short_cursor = await db.execute(
                    "SELECT fact, embedding_json FROM short_term_memories "
                    "WHERE user_id = ? AND expires_at > ?",
                    (user_id, now),
                )
                long_rows = list(await long_cursor.fetchall())
                short_rows = list(await short_cursor.fetchall())
                rows = [(str(row[0]), str(row[1])) for row in [*long_rows, *short_rows]]
            else:
                cursor = await db.execute(
                    "SELECT fact, embedding_json FROM long_term_memories WHERE user_id = ?",
                    (user_id,),
                )
                raw_rows = await cursor.fetchall()
                rows = [(str(row[0]), str(row[1])) for row in raw_rows]

        scored = self._score_rows(rows, query_embedding)
        if tier == "all":
            deduped: dict[str, float] = {}
            for score, fact in scored:
                deduped[fact] = max(score, deduped.get(fact, float("-inf")))
            scored = sorted(
                ((score, fact) for fact, score in deduped.items()),
                key=lambda x: x[0],
                reverse=True,
            )
        return _select_facts(scored)

    async def purge_expired(self) -> int:
        now = self._utcnow_iso()
        async with aiosqlite.connect(self._db_path) as db:
            cursor = await db.execute(
                "DELETE FROM short_term_memories WHERE expires_at < ?",
                (now,),
            )
            await db.commit()
            return cursor.rowcount if cursor.rowcount is not None else 0

    async def mark_priority_facts(
        self,
        user_id: str,
        facts: list[str],
    ) -> int:
        """Mark matching facts as priority=1. Returns count updated. Never raises."""
        try:
            updated = 0
            async with aiosqlite.connect(self._db_path) as db:
                for fact in facts:
                    cursor = await db.execute(
                        """
                        UPDATE long_term_memories
                        SET priority = 1
                        WHERE user_id = ? AND fact LIKE ?
                        """,
                        (user_id, f"%{fact}%"),
                    )
                    updated += cursor.rowcount or 0
                await db.commit()
            return updated
        except Exception:
            return 0

    async def get_priority_facts(
        self,
        user_id: str,
        top_k: int = 5,
    ) -> list[str]:
        """Return top_k priority facts for user_id. Never raises."""
        try:
            async with aiosqlite.connect(self._db_path) as db:
                cursor = await db.execute(
                    """
                    SELECT fact
                    FROM long_term_memories
                    WHERE user_id = ? AND priority = 1
                    ORDER BY created_at DESC
                    LIMIT ?
                    """,
                    (user_id, top_k),
                )
                rows = await cursor.fetchall()
            return [str(row[0]) for row in rows]
        except Exception:
            return []
