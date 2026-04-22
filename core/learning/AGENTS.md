# Learning Subsystem Agent Notes

This file supplements `/core/AGENTS.md` for `core/learning/`.

## Overview
Correction logging, replay analysis, patch persistence, rollback, and online reflection.

## Where To Look
| Task | Location | Notes |
|------|----------|-------|
| Replay analysis contract | `offline_replay.py` | Correction window, JSON response schema, patch suggestion flow |
| Patch lifecycle | `patch_store.py` | `pending` / `active` / `rolled_back` state machine |
| Correction persistence | `correction_store.py` | Logged correction records |
| Reflection/verbosity | `online_reflection.py` | Failure scores, verbosity mode, async persistence |
| Rollback evaluation | `rollback.py` | Patch safety/rollback heuristics |

## Conventions
- Replay output is a small JSON contract, not free-form text; keep that contract stable.
- Patch status values are fixed and local to this subsystem.
- Several store APIs intentionally return sentinel values or booleans instead of raising.
- Reflection persistence is best-effort/background-oriented; protect the live path first.

## Anti-Patterns
- Do not change patch statuses or replay JSON keys casually; other learning code assumes them.
- Do not convert best-effort persistence helpers into hard-fail APIs without tracing the callers.
- Do not move rollback/patch policy into unrelated modules; this subtree owns that lifecycle.
- Do not let learning-side background work become an always-on thread or hot-path blocker.
