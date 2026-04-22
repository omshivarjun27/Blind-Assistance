# Realtime Route Agent Notes

This file supplements `/apps/backend/AGENTS.md` for `apps/backend/api/routes/`.

## Overview
Main `/ws/realtime` route: browser websocket grammar, turn coordination, routing, memory, and learning side effects.

## Where To Look
| Task | Location | Notes |
|------|----------|-------|
| WebSocket message grammar | `realtime.py` | Binary audio turns vs JSON control frames |
| Intent/routing timing | `realtime.py` | Deferred classification, heavy-vision branch, prompt assembly |
| Background side effects | `realtime.py` | Memory save/recall, correction logging, replay/reflection tasks |

## Conventions
- Binary websocket frames represent complete PCM turns; text frames are control messages like `image`, `instructions`, `ping`, and `interrupt`.
- Route-local queued state such as pending image/instructions is next-turn state, not session-global history.
- The route intentionally mixes low-latency response flow with deferred intent resolution; avoid “simplifying” that timing without running realtime route tests.
- Fire-and-forget helpers in this file should log failures rather than break the live session.

## Anti-Patterns
- Do not change control-message shapes or names without updating `tests/unit/test_realtime_route.py`.
- Do not move route-owned heuristics like memory-query detection, correction detection, or short-fragment handling into unrelated modules unless the full route behavior is preserved.
- Do not make background memory/learning work block the hot path.
- Do not break the `[Camera sees]` / heavy-vision handoff logic by rearranging prompt or turn-state updates casually.
