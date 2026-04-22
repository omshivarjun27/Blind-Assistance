# Backend Agent Notes

This file supplements `/AGENTS.md` for `apps/backend/`.

## Overview
FastAPI backend: app entry, realtime WebSocket route, DashScope transports, SQLite bootstrap.

## Structure
- `main.py` — FastAPI app, CORS, `/health`, `/config`
- `api/routes/realtime.py` — main session loop, routing, memory, learning
- `services/dashscope/realtime_client.py` — DashScope realtime WebSocket client
- `services/dashscope/multimodal_client.py` — heavy vision HTTP client
- `db/bootstrap.py` — learning-table bootstrap helper

## Where To Look
| Task | Location | Notes |
|------|----------|-------|
| Session turn lifecycle | `api/routes/realtime.py` | Accepts audio/image/control messages and coordinates the turn |
| Upstream websocket protocol | `services/dashscope/realtime_client.py` | Session update, reconnect, cancel, transcript/audio handling |
| Vision fallback / OCR path | `services/dashscope/multimodal_client.py` | Camera frame analysis |
| App-level smoke endpoints | `main.py` | `/health` and `/config` |
| SQLite learning bootstrap | `db/bootstrap.py` | Tables created on startup path |

## Conventions
- Keep runtime config in `shared.config.settings`; do not hardcode model names, endpoints, or ports here.
- One browser websocket session maps to one backend client/session lifecycle.
- Recoverable failures should log and fall back to structured error/result state instead of crashing the route.
- Any realtime protocol change should be reflected in `tests/unit/test_realtime_route.py` and `tests/unit/test_realtime_client.py`.

## Anti-Patterns
- Do not add shared module-level realtime client state.
- Do not casually change `pending_image_b64` or instruction timing semantics inside `realtime.py`.
- Do not bypass `QwenRealtimeConfig.from_settings()` or `MultimodalClient.from_settings()` in normal app flow.
- Do not introduce live-network requirements into the unit-test-covered backend path; keep that in `scripts/check_dashscope_realtime_access.py`.

## Commands
```bash
python -m apps.backend.main
uvicorn apps.backend.main:app
C:/ally-vision-v2/.venv/Scripts/pytest.exe tests/unit/test_realtime_route.py -v --timeout=30 -x
C:/ally-vision-v2/.venv/Scripts/pytest.exe tests/unit/test_realtime_client.py -v --timeout=30 -x
```
