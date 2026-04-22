# Ally Vision v2 — Agent Rules

## Project
Blind-first voice+vision web assistant.
DashScope only. SQLite only. No local models.
Runs on laptop browser. Voice + camera + memory.

## Two-Agent System

PROMETHEUS (Claude Sonnet 4.6 via Anthropic API direct)
  Role: Writes plan files ONLY. Never executes code.
  Use: Before every new implementation plan.
  Output: One .sisyphus/plans/NN-name.md file.

HEPHAESTUS (GPT-5.4 via ChatGPT Plus OAuth)
  Role: Executes plans ONLY. Never writes plans.
  Use: After Prometheus writes a plan.
  Output: Working code + passing tests + git commit.

## Gate Phrase
Hephaestus MUST NOT advance to next plan until
user physically verifies and types exact phrase:
  real world verified and codebase verified and continue

## Absolute Rules
1. NEVER run: pytest tests/ (all at once)
   ALWAYS run: pytest tests/unit/[file].py -v --timeout=30 -x
2. NEVER commit .env
3. NEVER edit code without reading it first
4. NEVER delete files before verifying zero callers
5. NEVER use .md files as source of truth for code
6. NEVER use Bedrock (caps context, 10x cost)
7. NEVER add always-on processing features
8. ALWAYS run LSP diagnostics after file edits
9. ALWAYS verify DashScope docs with Tavily
10. ALWAYS commit plan files separately from code

## Paths
Project:  C:/ally-vision-v2/
Venv:     C:/ally-vision-v2/.venv/Scripts/
Python:   C:/ally-vision-v2/.venv/Scripts/python.exe
Pytest:   C:/ally-vision-v2/.venv/Scripts/pytest.exe
Plans:    .sisyphus/plans/

## Profile Switch
PROFILE=dev  → qwen3-omni-flash-realtime + qwen3.6-plus
PROFILE=exam → qwen3-omni-flash-realtime  + qwen3.6-plus

## Stack
Backend:  FastAPI + Python 3.11 + aiosqlite
Frontend: Next.js + React + TypeScript + Tailwind
Cloud:    DashScope only (one API key)
Storage:  SQLite only (no FAISS, no vector DB)

## Structure
```text
apps/backend/              FastAPI app, websocket route, DashScope transports
apps/frontend/             Next.js browser UI, camera/mic capture, websocket client
core/                      routing, memory, learning, and vision domain logic
shared/config/             env-driven runtime settings
tests/unit/                primary verification surface
scripts/                   live DashScope diagnostics
./dashscope-sdk-*-ref/     vendored reference SDKs; not primary app source
```

## Where To Look
| Task | Location | Notes |
|------|----------|-------|
| Realtime session flow | `apps/backend/api/routes/realtime.py` | WebSocket turn loop, memory, learning, routing |
| DashScope realtime transport | `apps/backend/services/dashscope/realtime_client.py` | Upstream WS client, reconnect, cancel, protocol contract |
| Heavy vision path | `apps/backend/services/dashscope/multimodal_client.py` | Camera frame + prompt HTTP path |
| Browser voice/camera loop | `apps/frontend/hooks/useRealtimeSession.ts` | Silence detection, playback, barge-in, frame send |
| Runtime config | `shared/config/settings.py` | `.env` loading, PROFILE switch, model selection, SQLite path |
| Routing and prompt logic | `core/orchestrator/` | Classifier, policy router, prompt builder |
| Memory and learning | `core/memory/`, `core/learning/` | Fact extraction/store/recall and replay/reflection |
| Focused verification | `tests/unit/` | Per-file pytest suite |

## Code Map
| Symbol | Location | Role |
|--------|----------|------|
| `app` | `apps/backend/main.py` | FastAPI entrypoint |
| `realtime_endpoint` | `apps/backend/api/routes/realtime.py` | Main WebSocket handler |
| `QwenRealtimeClient` | `apps/backend/services/dashscope/realtime_client.py` | DashScope realtime transport |
| `MultimodalClient` | `apps/backend/services/dashscope/multimodal_client.py` | Vision HTTP transport |
| `IntentClassifier` | `core/orchestrator/intent_classifier.py` | Transcript -> intent classification |
| `route` | `core/orchestrator/policy_router.py` | Intent -> route decision |
| `MemoryManager` | `core/memory/memory_manager.py` | Fact extraction, save, recall orchestration |
| `OfflineReplay` | `core/learning/offline_replay.py` | Learning patch suggestion flow |
| `useRealtimeSession` | `apps/frontend/hooks/useRealtimeSession.ts` | Browser session state + PCM flow |
| `RealtimeWSClient` | `apps/frontend/lib/ws-client.ts` | Browser WebSocket transport |

## Conventions
- Python dependencies live in `requirements*.txt`; `pyproject.toml` is packaging metadata only.
- Backend config is env-driven from `shared/config/settings.py` plus `.env` / `.env.example`.
- Frontend commands run from `apps/frontend`; TypeScript imports use the `@/*` alias.
- Tailwind/shadcn styling flows through `apps/frontend/app/globals.css` and `components.json`; no root `tailwind.config.*` is checked in.
- Root test discovery is `tests/`, but normal verification is file-scoped `tests/unit/test_*.py`.

## Commands
```bash
python -m apps.backend.main
uvicorn apps.backend.main:app

# run in apps/frontend
npm install
npm run dev
npm run build
npm run lint

C:/ally-vision-v2/.venv/Scripts/pytest.exe tests/unit/<file>.py -v --timeout=30 -x
python scripts/check_dashscope_realtime_access.py
```

## Notes
- No root app CI workflow is checked in.
- Frontend has no checked-in test runner; validation is lint/build plus backend/unit tests.
- `shared/config/settings.py` auto-creates the SQLite parent directory; realtime startup bootstraps learning tables.
- `PROFILE=dev|exam` switches the model set.
- Treat `dashscope-sdk-python-ref/` and `dashscope-sdk-java-ref/` as reference material, not primary implementation surface.
