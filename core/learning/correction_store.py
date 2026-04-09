"""Persist transcript history and correction events for Plan 10."""

from __future__ import annotations

from datetime import datetime

import aiosqlite

from shared.config import settings


class CorrectionStore:
    def __init__(self, db_path: str) -> None:
        self._db_path: str = db_path

    @classmethod
    def from_settings(cls) -> "CorrectionStore":
        return cls(db_path=settings.MEMORY_DB_PATH)

    @staticmethod
    def _utcnow_iso() -> str:
        return datetime.utcnow().isoformat()

    @staticmethod
    def _row_to_dict(row: aiosqlite.Row) -> dict[str, object]:
        return {str(key): row[key] for key in row.keys()}

    async def log_turn(
        self,
        session_id: str,
        turn_id: str,
        transcript: str,
        response: str,
        intent: str,
        route_target: str,
    ) -> None:
        try:
            async with aiosqlite.connect(self._db_path) as db:
                _ = await db.execute(
                    """
                    INSERT INTO transcript_log (
                        session_id,
                        turn_id,
                        user_transcript,
                        assistant_response,
                        intent_at_time,
                        route_target,
                        created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        session_id,
                        turn_id,
                        transcript,
                        response,
                        intent,
                        route_target,
                        self._utcnow_iso(),
                    ),
                )
                await db.commit()
        except Exception:
            return None

    async def log_correction(
        self,
        session_id: str,
        turn_id: str,
        transcript: str,
        response: str,
        signal: str,
        intent: str,
    ) -> None:
        try:
            async with aiosqlite.connect(self._db_path) as db:
                _ = await db.execute(
                    """
                    INSERT INTO correction_log (
                        session_id,
                        turn_id,
                        user_transcript,
                        assistant_response,
                        correction_signal,
                        intent_at_time,
                        created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        session_id,
                        turn_id,
                        transcript,
                        response,
                        signal,
                        intent,
                        self._utcnow_iso(),
                    ),
                )
                await db.commit()
        except Exception:
            return None

    async def get_corrections(
        self,
        session_id: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, object]]:
        try:
            async with aiosqlite.connect(self._db_path) as db:
                db.row_factory = aiosqlite.Row
                safe_limit = max(0, limit)
                if session_id is None:
                    cursor = await db.execute(
                        """
                        SELECT id, session_id, turn_id, user_transcript,
                               assistant_response, correction_signal,
                               intent_at_time, created_at
                        FROM correction_log
                        ORDER BY id DESC
                        LIMIT ?
                        """,
                        (safe_limit,),
                    )
                else:
                    cursor = await db.execute(
                        """
                        SELECT id, session_id, turn_id, user_transcript,
                               assistant_response, correction_signal,
                               intent_at_time, created_at
                        FROM correction_log
                        WHERE session_id = ?
                        ORDER BY id DESC
                        LIMIT ?
                        """,
                        (session_id, safe_limit),
                    )
                rows = await cursor.fetchall()
            return [self._row_to_dict(row) for row in rows]
        except Exception:
            return []

    async def correction_count_by_intent(self) -> dict[str, int]:
        try:
            async with aiosqlite.connect(self._db_path) as db:
                cursor = await db.execute(
                    """
                    SELECT intent_at_time, COUNT(*)
                    FROM correction_log
                    GROUP BY intent_at_time
                    """
                )
                raw_rows = await cursor.fetchall()
            counts: dict[str, int] = {}
            for row in raw_rows:
                intent_obj = row[0] if len(row) > 0 else None
                count_obj = row[1] if len(row) > 1 else None
                if (
                    isinstance(intent_obj, str)
                    and intent_obj
                    and isinstance(count_obj, (int, float))
                ):
                    counts[intent_obj] = int(count_obj)
            return counts
        except Exception:
            return {}

    async def get_turn_window(
        self,
        session_id: str,
        turn_id: str,
        before: int = 3,
        after: int = 3,
    ) -> list[dict[str, object]]:
        try:
            async with aiosqlite.connect(self._db_path) as db:
                db.row_factory = aiosqlite.Row
                anchor_cursor = await db.execute(
                    """
                    SELECT id
                    FROM transcript_log
                    WHERE session_id = ? AND turn_id = ?
                    ORDER BY id DESC
                    LIMIT 1
                    """,
                    (session_id, turn_id),
                )
                anchor = await anchor_cursor.fetchone()
                if anchor is None:
                    return []

                anchor_value = self._row_to_dict(anchor).get("id")
                if not isinstance(anchor_value, (int, float, str)):
                    return []
                anchor_id = int(anchor_value)
                before_cursor = await db.execute(
                    """
                    SELECT id, session_id, turn_id, user_transcript,
                           assistant_response, intent_at_time,
                           route_target, created_at
                    FROM transcript_log
                    WHERE session_id = ? AND id < ?
                    ORDER BY id DESC
                    LIMIT ?
                    """,
                    (session_id, anchor_id, max(0, before)),
                )
                before_rows = await before_cursor.fetchall()

                after_cursor = await db.execute(
                    """
                    SELECT id, session_id, turn_id, user_transcript,
                           assistant_response, intent_at_time,
                           route_target, created_at
                    FROM transcript_log
                    WHERE session_id = ? AND id >= ?
                    ORDER BY id ASC
                    LIMIT ?
                    """,
                    (session_id, anchor_id, max(0, after) + 1),
                )
                after_rows = await after_cursor.fetchall()

            ordered_rows = [*list(before_rows)[::-1], *list(after_rows)]
            return [self._row_to_dict(row) for row in ordered_rows]
        except Exception:
            return []
