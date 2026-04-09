"""Online per-session reflection and verbosity adaptation for Plan 10."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Literal

import aiosqlite

from shared.config import settings

logger = logging.getLogger(__name__)

_COMPACT_SIGNALS: tuple[str, ...] = (
    "shorter",
    "brief",
    "just tell me",
    "keep it short",
    "short answer",
    "in brief",
)

_VERBOSE_SIGNALS: tuple[str, ...] = (
    "explain more",
    "tell me more",
    "what else",
    "more detail",
    "elaborate",
    "go on",
)


class OnlineReflection:
    def __init__(
        self,
        db_path: str,
        decay_factor: float = 0.3,
        failure_threshold: float = 1.5,
    ) -> None:
        self._db_path: str = db_path
        self._decay_factor: float = decay_factor
        self._failure_threshold: float = failure_threshold
        self._failure_scores: dict[str, float] = {}
        self._verbosity_mode: Literal["COMPACT", "NORMAL", "VERBOSE"] = "NORMAL"
        self._turns_since_correction: dict[str, int] = {}

    @classmethod
    def from_settings(cls) -> "OnlineReflection":
        return cls(
            db_path=settings.MEMORY_DB_PATH,
            decay_factor=getattr(settings, "LEARNING_DECAY_FACTOR", 0.3),
            failure_threshold=getattr(settings, "LEARNING_FAILURE_THRESHOLD", 1.5),
        )

    @staticmethod
    def _utcnow_iso() -> str:
        return datetime.now(timezone.utc).isoformat()

    async def _persist_reflection(
        self,
        session_id: str,
        turn_id: str,
        intent: str,
    ) -> None:
        try:
            async with aiosqlite.connect(self._db_path) as db:
                _ = await db.execute(
                    """
                    INSERT INTO reflection_log (
                        session_id,
                        turn_id,
                        intent,
                        failure_score,
                        verbosity_mode,
                        created_at
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        session_id,
                        turn_id,
                        intent,
                        self._failure_scores.get(intent, 0.0),
                        self._verbosity_mode,
                        self._utcnow_iso(),
                    ),
                )
                await db.commit()
        except Exception as exc:
            logger.warning("_persist_reflection failed: %s", exc)

    def record_turn(
        self,
        session_id: str,
        turn_id: str,
        intent: str,
        was_corrected: bool,
        turns_since_last_correction: int,
    ) -> None:
        try:
            if was_corrected:
                weight = 1.0 / (1 + self._decay_factor * turns_since_last_correction)
                self._failure_scores[intent] = (
                    self._failure_scores.get(intent, 0.0) + weight
                )
                self._turns_since_correction[intent] = 0
            else:
                self._turns_since_correction[intent] = (
                    self._turns_since_correction.get(intent, 0) + 1
                )

            try:
                loop = asyncio.get_running_loop()
                _ = loop.create_task(
                    self._persist_reflection(
                        session_id=session_id,
                        turn_id=turn_id,
                        intent=intent,
                    )
                )
            except RuntimeError as exc:
                logger.warning("record_turn create_task failed: %s", exc)
        except Exception as exc:
            logger.warning("record_turn failed: %s", exc)

    def get_intent_penalty(self, intent: str) -> bool:
        try:
            return self._failure_scores.get(intent, 0.0) > self._failure_threshold
        except Exception:
            return False

    def get_verbosity_mode(
        self, session_id: str
    ) -> Literal["COMPACT", "NORMAL", "VERBOSE"]:
        _ = session_id
        try:
            return self._verbosity_mode
        except Exception:
            return "NORMAL"

    def update_verbosity(self, session_id: str, signal: str) -> None:
        _ = session_id
        try:
            cleaned = signal.lower()
            if any(token in cleaned for token in _COMPACT_SIGNALS):
                self._verbosity_mode = "COMPACT"
            elif any(token in cleaned for token in _VERBOSE_SIGNALS):
                self._verbosity_mode = "VERBOSE"
        except Exception as exc:
            logger.warning("update_verbosity failed: %s", exc)
