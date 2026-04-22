# Test Agent Notes

This file supplements `/AGENTS.md` for `tests/`.

## Overview
Root verification suite. Active tests are under `tests/unit/`; `tests/integration/` is present but currently empty.

## Structure
- `conftest.py` — shared env defaults for offline-friendly unit tests
- `unit/test_realtime_route.py` — websocket route regressions and end-to-end mocked session flow
- `unit/test_realtime_client.py` — realtime transport/config contract tests
- `unit/test_memory*.py` — memory persistence/recall behavior
- `unit/test_learning.py` — replay/reflection/patch flow
- `unit/test_*` — focused functional regressions per module

## Where To Look
| Task | Location | Notes |
|------|----------|-------|
| Websocket route regressions | `unit/test_realtime_route.py` | Largest mocked end-to-end backend verification surface |
| Realtime transport contract | `unit/test_realtime_client.py` | Session/config/cancel/reconnect behavior |
| Memory behavior | `unit/test_memory.py`, `unit/test_memory_store.py` | Embeddings, recall, SQLite persistence |
| Learning behavior | `unit/test_learning.py` | Replay, correction, reflection, patch flow |
| Shared test env defaults | `conftest.py` | Fake/default env vars for offline runs |

## Conventions
- Add new root tests as `tests/unit/test_<module>.py`.
- Keep unit tests offline-friendly; `tests/conftest.py` seeds fake/default env vars.
- Reuse the current testing style: `AsyncMock`, `MagicMock`, `TestClient`, `tmp_path`, focused helpers per file.
- Normal verification is file-scoped pytest, not full-suite pytest.

## Anti-Patterns
- Do not add live DashScope or live websocket requirements to the unit suite.
- Do not skip `test_realtime_route.py` or `test_realtime_client.py` when changing protocol, session, or config behavior.
- Do not put integration-only assumptions into `tests/unit/`.
- Do not treat vendored SDK test trees as part of the root app suite; root `pytest.ini` targets `tests/`.

## Commands
```bash
C:/ally-vision-v2/.venv/Scripts/pytest.exe tests/unit/<file>.py -v --timeout=30 -x
C:/ally-vision-v2/.venv/Scripts/pytest.exe tests/unit/test_realtime_route.py -v --timeout=30 -x
C:/ally-vision-v2/.venv/Scripts/pytest.exe tests/unit/test_realtime_client.py -v --timeout=30 -x
```
