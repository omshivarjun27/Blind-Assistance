# Memory Subsystem Agent Notes

This file supplements `/core/AGENTS.md` for `core/memory/`.

## Overview
Embedding, extraction, session memory, SQLite persistence, and startup/recall context.

## Where To Look
| Task | Location | Notes |
|------|----------|-------|
| SQLite schema + migration logic | `memory_store.py` | Long/short-term tables, indexes, migration, dedupe |
| Fact extraction contract | `mem0_extractor.py` | JSON-only extractor prompt and failure fallback |
| Orchestration | `memory_manager.py` | Save/recall flow, extractor/embedder/store interaction |
| Session-only memory | `session_memory.py` | Turn-local/session-local state |

## Conventions
- `initialize_all()` owns table creation/migration; keep schema evolution localized here.
- This subtree intentionally mixes different failure styles: extractor returns `[]`, manager logs/falls back, embedder may raise typed errors, store returns persisted results.
- Long-term and short-term memories have different retention semantics; do not flatten them into one generic store.
- Identity/priority handling is special-case logic here, not generic metadata.

## Anti-Patterns
- Do not bypass `initialize_all()` when changing schema-sensitive memory behavior.
- Do not remove the long/short-tier distinction or expiry/cap logic from `memory_store.py`.
- Do not casually rename or repurpose categories without checking store logic and tests; `IDENTITY` handling is special here.
- Do not change extractor JSON shape or “return [] on failure” behavior without updating the whole memory pipeline.
