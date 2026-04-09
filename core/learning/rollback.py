"""Evaluate whether active learning patches remain useful."""

from __future__ import annotations

import json
from importlib import import_module
from typing import Literal
from typing import Protocol
from typing import cast

from shared.config import settings

from core.learning.correction_store import CorrectionStore


class _PatchStoreProtocol(Protocol):
    async def rollback_patch(self, patch_id: int) -> bool: ...

    async def get_active_patches(
        self,
        target: str | None = None,
    ) -> list[dict[str, object]]: ...


class Rollback:
    def __init__(
        self,
        db_path: str,
        monitor_turns: int = 10,
        patch_store: _PatchStoreProtocol | None = None,
        correction_store: CorrectionStore | None = None,
    ) -> None:
        self._db_path: str = db_path
        self._monitor_turns: int = monitor_turns
        if patch_store is None:
            patch_store_module = import_module("core.learning.patch_store")
            patch_store = cast(
                _PatchStoreProtocol,
                patch_store_module.PatchStore(db_path=db_path),
            )
        self._patch_store: _PatchStoreProtocol = patch_store
        self._correction_store: CorrectionStore = correction_store or CorrectionStore(
            db_path=db_path
        )

    @classmethod
    def from_settings(cls) -> "Rollback":
        return cls(
            db_path=settings.MEMORY_DB_PATH,
            monitor_turns=getattr(settings, "LEARNING_PATCH_MONITOR_TURNS", 10),
        )

    async def evaluate_patch(
        self,
        patch_id: int,
        corrections_before: int,
        corrections_after: int,
    ) -> Literal["stable", "rollback", "monitoring"]:
        try:
            decay_score = corrections_after / max(1, corrections_before)
            if decay_score >= 1.0:
                await self._patch_store.rollback_patch(patch_id)
                return "rollback"
            if decay_score < 0.5:
                return "stable"
            return "monitoring"
        except Exception:
            return "monitoring"

    async def auto_rollback_weak_patches(self) -> list[int]:
        try:
            active_patches = await self._patch_store.get_active_patches()
            correction_counts = (
                await self._correction_store.correction_count_by_intent()
            )
            rolled_back: list[int] = []

            for patch in active_patches:
                patch_id_obj = patch.get("id")
                target_obj = patch.get("target")
                before_value_obj = patch.get("before_value")
                if not isinstance(patch_id_obj, int):
                    continue

                target = str(target_obj or "")
                corrections_after = correction_counts.get(target, 0)
                if corrections_after < self._monitor_turns:
                    continue

                corrections_before = 0
                if isinstance(before_value_obj, str):
                    try:
                        before_data = json.loads(before_value_obj)
                        if isinstance(before_data, dict):
                            before_count_obj = before_data.get("correction_count")
                            if isinstance(before_count_obj, int):
                                corrections_before = before_count_obj
                    except Exception:
                        corrections_before = 0

                verdict = await self.evaluate_patch(
                    patch_id=patch_id_obj,
                    corrections_before=corrections_before,
                    corrections_after=corrections_after,
                )
                if verdict == "rollback":
                    rolled_back.append(patch_id_obj)

            return rolled_back
        except Exception:
            return []
