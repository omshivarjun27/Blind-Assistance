"""Bootstrap learning-layer SQLite tables for Ally Vision v2."""

from __future__ import annotations

import logging

import aiosqlite

logger = logging.getLogger(__name__)

_TRANSCRIPT_LOG = """
CREATE TABLE IF NOT EXISTS transcript_log (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id   TEXT    NOT NULL,
    turn_id      TEXT,
    user_transcript    TEXT,
    assistant_response TEXT,
    intent_at_time     TEXT,
    route_target       TEXT,
    created_at   TEXT    NOT NULL
)
"""

_CORRECTION_LOG = """
CREATE TABLE IF NOT EXISTS correction_log (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id       TEXT NOT NULL,
    turn_id          TEXT,
    user_transcript  TEXT,
    assistant_response TEXT,
    correction_signal TEXT,
    intent_at_time   TEXT,
    created_at       TEXT NOT NULL
)
"""

_REFLECTION_LOG = """
CREATE TABLE IF NOT EXISTS reflection_log (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id     TEXT NOT NULL,
    turn_id        TEXT,
    intent         TEXT,
    failure_score  REAL DEFAULT 0.0,
    verbosity_mode TEXT DEFAULT 'NORMAL',
    created_at     TEXT NOT NULL
)
"""

_PATCH_STORE = """
CREATE TABLE IF NOT EXISTS patch_store (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    scope              TEXT NOT NULL,
    target             TEXT,
    change_description TEXT,
    before_value       TEXT,
    after_value        TEXT,
    status             TEXT DEFAULT 'pending',
    score              REAL DEFAULT 0.0,
    created_at         TEXT NOT NULL,
    applied_at         TEXT
)
"""


async def bootstrap_learning_tables(db_path: str) -> None:
    """Create all 4 learning tables. Never raises."""
    try:
        async with aiosqlite.connect(db_path) as db:
            _ = await db.execute(_TRANSCRIPT_LOG)
            _ = await db.execute(_CORRECTION_LOG)
            _ = await db.execute(_REFLECTION_LOG)
            _ = await db.execute(_PATCH_STORE)
            await db.commit()
        logger.info("Learning tables bootstrapped at %s", db_path)
    except Exception as exc:  # pragma: no cover
        logger.error("bootstrap_learning_tables failed: %s", exc)
