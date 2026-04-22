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
    "less",
    "summarize",
    "quick",
    "concise",
    "just tell me",
    "keep it short",
    "short answer",
    "in brief",
    "ಚಿಕ್ಕದಾಗಿ",
    "ಸಂಕ್ಷಿಪ್ತ",
    "संक्षेप में",
    "कम",
)

_VERBOSE_SIGNALS: tuple[str, ...] = (
    "explain more",
    "tell me more",
    "explain in detail",
    "what else",
    "more detail",
    "expand",
    "verbose",
    "elaborate",
    "go on",
    "विस्तार से",
    "विस्तार",
    "ಇನ್ನಷ್ಟು ಹೇಳು",
    "ಇನ್ನಷ್ಟು",
    "ವಿಸ್ತರಿಸು",
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
        self._session_failure_scores: dict[tuple[str, str], float] = {}
        self._verbosity_modes: dict[str, Literal["COMPACT", "NORMAL", "VERBOSE"]] = {}
        self._turns_since_correction: dict[tuple[str, str], int] = {}

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
                        self.get_failure_score(session_id, intent),
                        self.get_verbosity_mode(session_id),
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
            session_key = (session_id, intent)
            if was_corrected:
                _ = turns_since_last_correction
                next_score = min(
                    self._session_failure_scores.get(session_key, 0.0) + 0.34,
                    1.0,
                )
                self._session_failure_scores[session_key] = next_score
                self._failure_scores[intent] = next_score
                self._turns_since_correction[session_key] = 0
            else:
                self._turns_since_correction[session_key] = (
                    self._turns_since_correction.get(session_key, 0) + 1
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
            return self._failure_scores.get(intent, 0.0) >= self._failure_threshold
        except Exception:
            return False

    def get_session_intent_penalty(self, session_id: str, intent: str) -> bool:
        try:
            return self.get_failure_score(session_id, intent) >= self._failure_threshold
        except Exception:
            return False

    def get_failure_score(self, session_id: str, intent: str) -> float:
        try:
            return self._session_failure_scores.get(
                (session_id, intent),
                self._failure_scores.get(intent, 0.0),
            )
        except Exception:
            return 0.0

    def get_verbosity_mode(
        self, session_id: str
    ) -> Literal["COMPACT", "NORMAL", "VERBOSE"]:
        try:
            return self._verbosity_modes.get(session_id, "NORMAL")
        except Exception:
            return "NORMAL"

    def update_verbosity(self, session_id: str, signal: str) -> None:
        try:
            cleaned = signal.lower()
            if any(token in cleaned for token in _COMPACT_SIGNALS):
                self._verbosity_modes[session_id] = "COMPACT"
            elif any(token in cleaned for token in _VERBOSE_SIGNALS):
                self._verbosity_modes[session_id] = "VERBOSE"
        except Exception as exc:
            logger.warning("update_verbosity failed: %s", exc)
