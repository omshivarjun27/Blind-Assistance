"""Persist small prompt/routing/threshold patches for Plan 10."""

from __future__ import annotations

import json
from datetime import datetime, timezone

import aiosqlite

from shared.config import settings

_VALID_STATUSES: frozenset[str] = frozenset({"pending", "active", "rolled_back"})


class PatchStore:
    def __init__(self, db_path: str) -> None:
        self._db_path: str = db_path

    @classmethod
    def from_settings(cls) -> "PatchStore":
        return cls(db_path=settings.MEMORY_DB_PATH)

    @staticmethod
    def _utcnow_iso() -> str:
        return datetime.now(timezone.utc).isoformat()

    @staticmethod
    def _row_to_dict(row: aiosqlite.Row) -> dict[str, object]:
        return {str(key): row[key] for key in row.keys()}

    async def create_patch(
        self,
        scope: str,
        target: str,
        before: dict[str, object],
        after: dict[str, object],
        description: str,
    ) -> int:
        try:
            async with aiosqlite.connect(self._db_path) as db:
                cursor = await db.execute(
                    """
                    INSERT INTO patch_store (
                        scope,
                        target,
                        change_description,
                        before_value,
                        after_value,
                        status,
                        score,
                        created_at,
                        applied_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        scope,
                        target,
                        description,
                        json.dumps(before),
                        json.dumps(after),
                        "pending",
                        0.0,
                        self._utcnow_iso(),
                        None,
                    ),
                )
                await db.commit()
                row_id = cursor.lastrowid
                return int(row_id) if row_id is not None else -1
        except Exception:
            return -1

    async def activate_patch(self, patch_id: int) -> bool:
        try:
            async with aiosqlite.connect(self._db_path) as db:
                cursor = await db.execute(
                    """
                    UPDATE patch_store
                    SET status = ?, applied_at = ?
                    WHERE id = ? AND status = ?
                    """,
                    ("active", self._utcnow_iso(), patch_id, "pending"),
                )
                await db.commit()
                return bool(cursor.rowcount)
        except Exception:
            return False

    async def rollback_patch(self, patch_id: int) -> bool:
        try:
            async with aiosqlite.connect(self._db_path) as db:
                cursor = await db.execute(
                    """
                    UPDATE patch_store
                    SET status = ?
                    WHERE id = ? AND status = ?
                    """,
                    ("rolled_back", patch_id, "active"),
                )
                await db.commit()
                return bool(cursor.rowcount)
        except Exception:
            return False

    async def get_active_patches(
        self,
        target: str | None = None,
    ) -> list[dict[str, object]]:
        try:
            async with aiosqlite.connect(self._db_path) as db:
                db.row_factory = aiosqlite.Row
                if target is None:
                    cursor = await db.execute(
                        """
                        SELECT id, scope, target, change_description,
                               before_value, after_value, status,
                               score, created_at, applied_at
                        FROM patch_store
                        WHERE status = ?
                        ORDER BY created_at DESC
                        """,
                        ("active",),
                    )
                else:
                    cursor = await db.execute(
                        """
                        SELECT id, scope, target, change_description,
                               before_value, after_value, status,
                               score, created_at, applied_at
                        FROM patch_store
                        WHERE status = ? AND target = ?
                        ORDER BY created_at DESC
                        """,
                        ("active", target),
                    )
                rows = await cursor.fetchall()
            return [self._row_to_dict(row) for row in rows]
        except Exception:
            return []

    async def get_patch_history(self) -> list[dict[str, object]]:
        try:
            async with aiosqlite.connect(self._db_path) as db:
                db.row_factory = aiosqlite.Row
                cursor = await db.execute(
                    """
                    SELECT id, scope, target, change_description,
                           before_value, after_value, status,
                           score, created_at, applied_at
                    FROM patch_store
                    ORDER BY created_at DESC
                    """
                )
                rows = await cursor.fetchall()
            return [
                self._row_to_dict(row)
                for row in rows
                if str(self._row_to_dict(row).get("status", "")) in _VALID_STATUSES
            ]
        except Exception:
            return []
