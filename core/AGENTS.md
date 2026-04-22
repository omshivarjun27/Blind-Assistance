# Core Agent Notes

This file supplements `/AGENTS.md` for `core/`.

## Overview
Shared domain logic: orchestrator, memory, learning, and vision helpers that back the backend route.

## Structure
- `orchestrator/` — intent classification, routing, prompt shaping, capture coaching
- `memory/` — embeddings, extraction, storage, recall, session memory
- `learning/` — correction logging, replay, patch tracking, reflection, rollback
- `vision/` — page reading, scene reading, framing guidance

## Where To Look
| Task | Location | Notes |
|------|----------|-------|
| Intent -> route decision | `orchestrator/intent_classifier.py`, `orchestrator/policy_router.py` | Main routing policy |
| Prompt assembly | `orchestrator/prompt_builder.py` | Memory/document/verbosity prompt composition |
| Long/short-term memory | `memory/memory_store.py`, `memory/memory_manager.py` | SQLite persistence and recall orchestration |
| Fact extraction | `memory/mem0_extractor.py` | DashScope-compatible extraction path |
| Learning and replay | `learning/offline_replay.py`, `learning/online_reflection.py` | Corrections, replay, verbosity, patches |
| Vision helpers | `vision/page_reader.py`, `vision/live_scene_reader.py` | OCR-style and scene helper logic |

## Conventions
- Put reusable domain logic here instead of growing `apps/backend/api/routes/realtime.py` further.
- Load settings via `shared.config.settings`, not ad-hoc environment reads spread across modules.
- Memory and learning persistence follow `aiosqlite` + log-and-fallback patterns.
- Public thresholds/defaults should live close to the domain module that owns them.

## Anti-Patterns
- Do not put HTTP/WebSocket transport code here; that belongs under `apps/backend/services/`.
- Do not make routine classifier/memory/learning helpers raise on recoverable failures when the current module pattern is log + fallback.
- Do not duplicate routing or prompt logic across modules; extend orchestrator utilities instead.
- Do not add new core behavior without matching focused coverage in `tests/unit/`.

## Commands
```bash
C:/ally-vision-v2/.venv/Scripts/pytest.exe tests/unit/test_intent_classifier.py -v --timeout=30 -x
C:/ally-vision-v2/.venv/Scripts/pytest.exe tests/unit/test_memory.py -v --timeout=30 -x
C:/ally-vision-v2/.venv/Scripts/pytest.exe tests/unit/test_learning.py -v --timeout=30 -x
```
