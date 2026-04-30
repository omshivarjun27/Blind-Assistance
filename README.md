# Ally Vision v2

![Python](https://img.shields.io/badge/Python-3.11%2B-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-runtime-green)
![Next.js](https://img.shields.io/badge/Next.js-16.2.2-black)
![License](https://img.shields.io/badge/License-MIT-yellow)
![Platform](https://img.shields.io/badge/Platform-Windows-0078D6)

Blind-first real-time voice + vision assistant built with FastAPI, Next.js, SQLite, and Alibaba DashScope Qwen models.

Ally Vision v2 is a browser-based assistant designed for blind and visually impaired users.
It combines microphone input, camera capture, live WebSocket turns, heavy vision analysis, persistent memory, and a lightweight self-correction layer.
The current codebase is optimized around DashScope-only inference, SQLite-only storage, and a laptop-browser workflow with a single `/ws/realtime` backend session loop.

## Features

### 🎤 Voice-first interaction

- 🎙️ **Real-time microphone capture** — the browser captures mono PCM audio with an `AudioWorklet`, then batches it into full user turns instead of sending raw recorder fragments.
- 🗣️ **Speech-to-speech replies** — assistant replies are streamed back as PCM audio over the same WebSocket session.
- ✋ **Barge-in interruption** — the frontend can interrupt active assistant playback and the backend forwards `response.cancel` to DashScope when the user starts speaking again.
- 📶 **Reconnect-aware transport** — the frontend WebSocket client supports reconnecting state and the backend route sends heartbeat `ping` messages to keep long turns alive.
- 🧾 **Per-turn transcript ordering** — user transcript bubbles are emitted before assistant transcript bubbles using a shared `turn_id`.

### 👁️ Vision capabilities

- 📷 **Camera frame capture** — the frontend captures JPEG frames from a live `<video>` stream and compresses them before upload.
- 🧭 **Capture coaching** — a lightweight pixel-quality gate rejects frames that are too dark, too small, or too uniform before heavy vision runs.
- 🔍 **Scene description** — heavy vision calls can describe rooms, visible objects, text, people, and layout for blind users.
- 📖 **Read text from images** — OCR-style prompts extract visible text directly from images.
- 📄 **Page summarization** — document pages can be summarized with page-aware prompts.
- 🔁 **Scene repetition reduction** — the route keeps a rolling buffer of recent scene descriptions so repeated vision turns can avoid verbatim repetition.

### 🧠 Memory system

- 📝 **Explicit memory save** — direct user requests such as “remember”, “store”, or “save permanently” are normalized and written to SQLite.
- 🧪 **LLM fact extraction** — the backend uses `qwen-turbo` in compatible mode to extract structured personal facts from conversation turns.
- 🗂️ **Long-term + short-term tiers** — persistent facts live in `long_term_memories`, while capped expiring facts can live in `short_term_memories`.
- 🔎 **Embedding-based recall** — memory recall uses cosine similarity over stored embeddings to retrieve relevant facts.
- 🚀 **Startup preload** — priority facts are injected into the session instructions when a new real-time session starts.
- 🧷 **Category-aware deduplication** — memory writes can overwrite the latest fact in the same semantic category instead of endlessly duplicating records.

### 🛡️ Reliability and safety

- ♻️ **Shared HTTP clients** — the FastAPI lifespan creates persistent `httpx.AsyncClient` instances for vision and compatible-mode traffic.
- ⏱️ **Transcript timeout isolation** — realtime transcript waiting is decoupled from audio playback so the user still hears replies even if ASR is delayed.
- 🔌 **Recoverable turn failures** — commit failures and “none active response” session errors trigger reconnect logic instead of killing the browser session.
- 🔒 **Safe send wrappers** — backend WebSocket sends are wrapped so disconnects degrade gracefully.
- 🧠 **Memory DB bootstrap** — startup logs the resolved SQLite path and bootstraps learning tables before use.

### 🌍 Multilingual and accessibility support

- 🇮🇳 **Kannada / Hindi / English oriented flow** — prompts and transcript guards are explicitly tuned for Kannada, Hindi, and English usage.
- 🧹 **Wrong-language transcript cleanup** — suspicious Chinese, Thai, or Vietnamese ASR output can be discarded before routing.
- 🔤 **Indic font support** — the frontend loads Noto Sans fonts for Kannada, Devanagari, Tamil, and Telugu rendering.
- ♿ **Blind-first response design** — prompts favor concise spoken answers, explicit guidance, and camera-grounded answers over verbose screen-centric UX.

### 📚 Learning and self-correction

- ❌ **Correction signal detection** — phrases like “that’s wrong”, “ತಪ್ಪು”, or “गलत है” are detected and logged.
- 📈 **Failure score accumulation** — each correction adds `0.34` for the `(session_id, intent)` pair until the score caps at `1.0`.
- ✂️ **Verbosity adaptation** — `COMPACT`, `NORMAL`, and `VERBOSE` modes are stored per session and influence prompts.
- ⚠️ **Cautious prefix injection** — once an intent’s session-scoped failure score crosses the threshold, prompts can prepend “Let me be careful here…”.
- 🔁 **Offline replay** — corrections are replayed through `qwen-turbo` to suggest small prompt/routing/threshold patches.
- 🏷️ **Priority memory promotion** — repeated recall topics can be promoted to priority facts for future session preloading.

## Architecture

```text
┌──────────────────────────────┐
│ Browser / Next.js frontend   │
│ - useMicStream               │
│ - useCameraCapture           │
│ - useRealtimeSession         │
│ - RealtimeWSClient           │
└──────────────┬───────────────┘
               │  WSS /ws/realtime
               ▼
┌──────────────────────────────────────────────────────────────┐
│ FastAPI backend                                              │
│ apps.backend.api.routes.realtime: realtime_endpoint          │
│ - accepts PCM audio + JSON control messages                  │
│ - emits audio bytes + ordered transcripts + status/error     │
│ - heartbeats browser with ping                               │
└──────────────┬───────────────────────────────┬───────────────┘
               │                               │
               │                               │
               ▼                               ▼
┌───────────────────────────┐      ┌───────────────────────────┐
│ IntentClassifier          │      │ Policy Router             │
│ qwen-turbo via compat API │      │ RouteTarget decision      │
│ 8 intent categories       │      │ frame-needed vs chat path │
└──────────────┬────────────┘      └──────────────┬────────────┘
               │                                   │
               │                                   │
      ┌────────▼────────┐                 ┌────────▼────────────┐
      │ REALTIME_CHAT   │                 │ HEAVY_VISION        │
      │ / MEMORY paths  │                 │ qwen3.6-plus        │
      └────────┬────────┘                 └────────┬────────────┘
               │                                   │
               │ [Camera sees] / exact text        │ VisionRequest
               ▼                                   ▼
┌──────────────────────────────────────────────────────────────┐
│ QwenRealtimeClient                                           │
│ DashScope realtime WebSocket                                 │
│ - session.update                                             │
│ - audio append/commit                                        │
│ - response.create                                            │
│ - response.cancel                                            │
│ - transcript cleanup + reconnect logic                       │
└──────────────┬───────────────────────────────────────────────┘
               │
               ▼
┌──────────────────────────────────────────────────────────────┐
│ DashScope Realtime Model                                     │
│ qwen3.5-omni-plus-realtime                                   │
│ - speech input                                               │
│ - speech output                                              │
│ - final spoken response                                      │
└──────────────────────────────────────────────────────────────┘

┌──────────────────────────────┐
│ MemoryManager                │
│ - explicit save              │
│ - fact extraction            │
│ - embedding recall           │
│ - startup preload            │
└──────────────┬───────────────┘
               │
      ┌────────▼─────────────┐
      │ EmbeddingClient      │
      │ text-embedding-v4    │
      └────────┬─────────────┘
               │
               ▼
┌──────────────────────────────────────────────────────────────┐
│ SQLite DB (6 active tables)                                  │
│ - long_term_memories                                         │
│ - short_term_memories                                        │
│ - transcript_log                                             │
│ - correction_log                                             │
│ - reflection_log                                             │
│ - patch_store                                                │
└──────────────────────────────────────────────────────────────┘

┌──────────────────────────────┐
│ Learning / correction        │
│ - CorrectionStore            │
│ - OnlineReflection           │
│ - OfflineReplay              │
│ - PatchStore / Rollback      │
└──────────────────────────────┘
```

### Request flow in plain English

1. The browser records raw microphone audio and silence-batches it into a single turn.
2. The browser optionally sends a JPEG frame for the next turn.
3. `/ws/realtime` prepares the audio turn with `QwenRealtimeClient`.
4. The route classifies or heuristically routes the turn.
5. Vision turns call `qwen3.6-plus`; memory turns call the memory stack; everything ultimately replies through the realtime model.
6. The backend returns streamed PCM audio plus transcript events keyed by `turn_id`.
7. Memory, correction, reflection, and replay side effects are recorded asynchronously in SQLite.

## Intent Routing Table

| Intent | Trigger Example | Route | Model Used |
|--------|-----------------|-------|------------|
| `SCENE_DESCRIBE` | “what do you see” / short visual fragment with image | `HEAVY_VISION` | `qwen3.6-plus` for analysis, then `qwen3.5-omni-plus-realtime` for spoken reply |
| `READ_TEXT` | “read this” / visible text request | `HEAVY_VISION` | `qwen3.6-plus` for OCR-style analysis, then `qwen3.5-omni-plus-realtime` |
| `SCAN_PAGE` | “scan this page” | `HEAVY_VISION` | `qwen3.6-plus` for page analysis, then `qwen3.5-omni-plus-realtime` |
| `MEMORY_SAVE` | “remember this”, “store in permanent memory”, “my name is …” | `MEMORY_WRITE` | `qwen-turbo` fact extraction + `text-embedding-v4` + SQLite; confirmation is spoken through realtime |
| `MEMORY_RECALL` | “what is my name”, “do you remember” | `MEMORY_READ` | `text-embedding-v4` similarity recall + SQLite + realtime spoken reply |
| `DOCUMENT_QA` | “answer from the scanned document” | Fallback to `REALTIME_CHAT` today | Currently unimplemented as a distinct route; router falls back to realtime chat |
| `TRANSLATE` | “translate this to English/Hindi” | `REALTIME_CHAT` | `qwen3.5-omni-plus-realtime` |
| `GENERAL_CHAT` | “how are you”, normal conversation | `REALTIME_CHAT` | `qwen3.5-omni-plus-realtime` |

### Important routing details

- Image presence matters.
- Acknowledgement words such as `ok`, `ಹೌದು`, or `ठीक है` do **not** force heavy vision.
- Very short non-ack visual utterances with an image can still force `SCENE_DESCRIBE`.
- Chinese/Thai/Vietnamese-looking ASR output can be discarded before routing.
- `DOCUMENT_QA` is defined in the intent set but not yet implemented as its own runtime branch.

## Tech Stack

| Layer | Technology | Version |
|-------|-----------|---------|
| Language | Python | `>=3.11` |
| Backend framework | FastAPI | unpinned in `requirements.txt` |
| ASGI server | Uvicorn | unpinned in `requirements.txt` |
| Validation | Pydantic | unpinned in `requirements.txt` |
| Async HTTP | httpx | unpinned in `requirements.txt` |
| Realtime WS client | websocket-client | unpinned in `requirements.txt` |
| Async WebSocket support | websockets | unpinned in `requirements.txt` |
| DB | aiosqlite | unpinned in `requirements.txt` |
| Imaging | Pillow | unpinned in `requirements.txt` |
| Numerical ops | NumPy | unpinned in `requirements.txt` |
| Cloud AI SDK | dashscope | unpinned in `requirements.txt` |
| Frontend framework | Next.js | `16.2.2` |
| UI library | React | `19.2.4` |
| DOM renderer | react-dom | `19.2.4` |
| Type system | TypeScript | `^5` |
| Styling | Tailwind CSS | `^4` |
| UI primitives | @base-ui/react | `^1.3.0` |
| Component generator | shadcn | `^4.1.2` |
| Icons | lucide-react | `^1.7.0` |
| Linting | ESLint | `^9` |
| Next lint preset | eslint-config-next | `16.2.2` |
| Testing | pytest | unpinned in `requirements-dev.txt` |
| Async testing | pytest-asyncio | unpinned in `requirements-dev.txt` |
| Timeout testing | pytest-timeout | unpinned in `requirements-dev.txt` |

## Project Structure

The tree below shows the logical source structure used by the app.
Local caches, virtual environments, `.next`, runtime `data/`, and other audit candidates are intentionally omitted.

```text
ally-vision-v2/
├── .env.example                        # Safe environment template for local setup
├── .gitignore                          # Ignore rules for secrets, caches, DBs, and build output
├── AGENTS.md                           # Project-specific engineering and runtime rules
├── LICENSE                             # MIT license text
├── pyproject.toml                      # Python package metadata and Python version floor
├── pyrightconfig.json                  # Static typing configuration
├── pytest.ini                          # Root pytest discovery configuration
├── requirements.txt                    # Backend/runtime Python dependencies
├── requirements-dev.txt                # Dev/test Python dependencies
├── apps/
│   ├── __init__.py                     # Package marker for app modules
│   ├── backend/
│   │   ├── AGENTS.md                   # Backend-local rules
│   │   ├── __init__.py                 # Package marker
│   │   ├── main.py                     # FastAPI app, lifespan, CORS, health/config endpoints
│   │   ├── api/
│   │   │   ├── __init__.py             # Package marker
│   │   │   └── routes/
│   │   │       ├── AGENTS.md           # Realtime route notes
│   │   │       ├── __init__.py         # Package marker
│   │   │       └── realtime.py         # Main WebSocket turn loop, routing, memory, learning
│   │   ├── db/
│   │   │   ├── __init__.py             # Package marker
│   │   │   └── bootstrap.py            # Creates learning-side SQLite tables
│   │   └── services/
│   │       ├── __init__.py             # Package marker
│   │       ├── shared_http.py          # Shared AsyncClient handles for vision/compat traffic
│   │       ├── capture/
│   │       │   └── __init__.py         # Reserved capture service namespace
│   │       ├── response/
│   │       │   └── __init__.py         # Reserved response service namespace
│   │       └── dashscope/
│   │           ├── AGENTS.md           # DashScope transport notes
│   │           ├── __init__.py         # Package marker
│   │           ├── multimodal_client.py # Heavy vision HTTP client for qwen3.6-plus
│   │           └── realtime_client.py  # Realtime WS client for qwen3.5-omni-plus-realtime
│   └── frontend/
│       ├── AGENTS.md                   # Frontend-local rules
│       ├── .gitignore                  # Frontend-local ignore rules
│       ├── components.json             # shadcn component configuration
│       ├── eslint.config.mjs           # ESLint config for Next.js + TypeScript
│       ├── next.config.ts             # Next.js config (`reactCompiler: true`)
│       ├── package.json                # Frontend dependencies and scripts
│       ├── package-lock.json           # npm lockfile
│       ├── postcss.config.mjs          # Tailwind PostCSS config
│       ├── tsconfig.json               # TypeScript config with app aliases
│       ├── next-env.d.ts               # Next-generated TS env types
│       ├── app/
│       │   ├── favicon.ico             # Browser favicon
│       │   ├── globals.css             # Global styles, theme vars, Indic font support
│       │   ├── layout.tsx              # Root HTML/body wrapper
│       │   └── page.tsx                # Main UI screen with camera, status, and chat transcript
│       ├── components/
│       │   ├── camera-view.tsx         # Live camera video container
│       │   ├── control-bar.tsx         # Start/stop/capture controls
│       │   ├── status-pill.tsx         # Top status indicator
│       │   └── ui/
│       │       └── button.tsx          # Shared button primitive wrapper
│       ├── hooks/
│       │   ├── AGENTS.md               # Hook-specific notes
│       │   ├── useCameraCapture.ts     # Browser camera stream and JPEG frame capture
│       │   ├── useMicStream.ts         # AudioWorklet-based PCM microphone capture
│       │   └── useRealtimeSession.ts   # Main browser session state machine
│       ├── lib/
│       │   ├── audio-utils.ts          # PCM helpers and RMS calculation
│       │   ├── utils.ts                # Shared UI utility helpers
│       │   └── ws-client.ts            # Browser WebSocket client with reconnect support
│       └── public/
│           └── worklets/
│               ├── AGENTS.md           # Worklet notes
│               └── mic-processor.js    # AudioWorklet processor for 16 kHz PCM chunks
├── core/
│   ├── AGENTS.md                       # Core-domain rules
│   ├── __init__.py                     # Package marker
│   ├── session/
│   │   └── __init__.py                 # Reserved session namespace
│   ├── orchestrator/
│   │   ├── __init__.py                 # Package marker
│   │   ├── capture_coach.py            # Lightweight frame usability gate
│   │   ├── intent_classifier.py        # qwen-turbo intent classification
│   │   ├── policy_router.py            # Intent -> RouteTarget mapping
│   │   └── prompt_builder.py           # Prompt assembly and prefix stripping
│   ├── memory/
│   │   ├── AGENTS.md                   # Memory subsystem notes
│   │   ├── __init__.py                 # Public memory exports
│   │   ├── embedding_client.py         # Embedding API wrapper
│   │   ├── mem0_extractor.py           # qwen-turbo personal fact extractor
│   │   ├── memory_context_composer.py  # Structured memory-context formatting
│   │   ├── memory_manager.py           # Save/recall/preload orchestration
│   │   ├── memory_store.py             # SQLite memory persistence and recall
│   │   └── session_memory.py           # In-memory session turn/object memory
│   ├── learning/
│   │   ├── AGENTS.md                   # Learning subsystem notes
│   │   ├── __init__.py                 # Public learning exports
│   │   ├── correction_store.py         # Transcript/correction persistence
│   │   ├── offline_replay.py           # Replay-based patch suggestion and priority promotion
│   │   ├── online_reflection.py        # Failure scores and verbosity tracking
│   │   ├── patch_store.py              # Suggested patch persistence
│   │   └── rollback.py                 # Patch rollback evaluation
│   └── vision/
│       ├── __init__.py                 # Package marker
│       ├── framing_judge.py            # Model-based frame quality helper
│       ├── live_scene_reader.py        # Scene description helper
│       └── page_reader.py              # OCR-style page reading and page summary helper
├── scripts/
│   └── check_dashscope_realtime_access.py # Live connectivity diagnostic for DashScope realtime access
├── shared/
│   ├── __init__.py                     # Package marker
│   ├── config/
│   │   ├── __init__.py                 # Package marker
│   │   └── settings.py                 # Environment-driven runtime settings
│   └── schemas/
│       └── __init__.py                 # Reserved schema namespace
└── tests/
    ├── AGENTS.md                       # Test-suite notes
    ├── __init__.py                     # Package marker
    ├── conftest.py                     # Shared offline-friendly env defaults for tests
    └── unit/
        ├── __init__.py                 # Package marker
        ├── test_heavy_vision.py        # Heavy vision client + helper coverage
        ├── test_intent_classifier.py   # Intent classification coverage
        ├── test_learning.py            # Reflection, replay, and patch lifecycle coverage
        ├── test_memory.py              # Memory manager + extractor coverage
        ├── test_memory_store.py        # SQLite store coverage
        ├── test_policy_router.py       # RouteTarget mapping coverage
        ├── test_prompt_builder.py      # Prompt builder coverage
        ├── test_realtime_client.py     # DashScope realtime transport coverage
        ├── test_realtime_route.py      # End-to-end mocked route coverage
        └── test_settings.py            # Settings/env coverage
```

## Prerequisites

- Python `3.11+`
- Node.js `18+`
- npm `9+`
- A DashScope account and API key
- A Windows development environment is the primary documented setup in this repo
- A browser with support for `getUserMedia`, `AudioContext`, and `AudioWorklet`

### External services

- DashScope realtime WebSocket endpoint
- DashScope compatible-mode chat endpoint
- DashScope multimodal HTTP endpoint
- No local model runtime is expected or documented in the current code

## Installation & Setup

### 1. Clone the repository

```bash
git clone https://github.com/omshivarjun27/Blind-Assistance.git ally-vision-v2
cd ally-vision-v2
```

### 2. Backend setup

```bash
python -m venv .venv
```

Windows:

```bash
.venv\Scripts\activate
```

macOS / Linux:

```bash
source .venv/bin/activate
```

Install Python dependencies:

```bash
pip install -r requirements.txt
```

### 3. Frontend setup

```bash
cd apps/frontend
npm install
cd ../..
```

### 4. Environment variables

Windows PowerShell:

```bash
Copy-Item .env.example .env
```

macOS / Linux:

```bash
cp .env.example .env
```

Fill in your real DashScope API key in `.env`.

### 5. Run the backend

```bash
.venv\Scripts\python.exe -m uvicorn apps.backend.main:app --host 127.0.0.1 --port 8000 --reload
```

Alternative backend command from the repo:

```bash
python -m apps.backend.main
```

### 6. Run the frontend

```bash
cd apps/frontend
npm run dev
```

### 7. Open the app

```bash
http://localhost:3000
```

### 8. First session checklist

- Allow microphone access
- Allow camera access
- Start the session from the UI
- Speak naturally
- Use the Capture button before vision-heavy questions when needed

## Environment Variables

The table below documents every variable currently present in `.env.example`.

| Variable | Required | Description | Default |
|----------|----------|-------------|---------|
| `PROFILE` | Yes | Selects dev vs exam profile-specific model keys | `dev` |
| `QWEN_REALTIME_MODEL` | No | Informational top-level realtime model entry shown in `.env.example`; runtime code actually selects from `QWEN_REALTIME_DEV` / `QWEN_REALTIME_EXAM` | `qwen3.5-omni-plus-realtime` |
| `DASHSCOPE_REGION` | Yes | Region label used in config and docs | `singapore` |
| `DASHSCOPE_API_KEY` | Yes | DashScope API key used for realtime, compatible-mode, embeddings, and heavy vision | `your_dashscope_api_key_here` |
| `DASHSCOPE_HTTP_BASE` | Yes | Base URL for native DashScope HTTP APIs | `https://dashscope-intl.aliyuncs.com/api/v1` |
| `DASHSCOPE_REALTIME_URL` | Yes | DashScope realtime WebSocket URL | `wss://dashscope-intl.aliyuncs.com/api-ws/v1/realtime` |
| `DASHSCOPE_COMPAT_BASE` | Yes | DashScope compatible-mode base URL | `https://dashscope-intl.aliyuncs.com/compatible-mode/v1` |
| `QWEN_REALTIME_DEV` | Yes | Realtime model used when `PROFILE=dev` | `qwen3.5-omni-plus-realtime` |
| `QWEN_REALTIME_EXAM` | Yes | Realtime model used when `PROFILE=exam` | `qwen3.5-omni-plus-realtime` |
| `QWEN_HEAVY_VISION_MODEL` | Yes | Preferred heavy vision override used by the runtime | `qwen3.6-plus` |
| `QWEN_OMNI_VOICE` | Yes | Voice ID for realtime audio responses | `Tina` |
| `QWEN_VISION_DEV` | Yes | Profile-specific vision model for `dev` if override is absent | `qwen3.6-plus` |
| `QWEN_VISION_EXAM` | Yes | Profile-specific vision model for `exam` if override is absent | `qwen3.6-plus` |
| `QWEN_TRANSCRIPTION_MODEL` | Yes | Configured input transcription model; runtime currently wire-maps `gummy-realtime-v1` to `qwen3-asr-flash-realtime` for DashScope session compatibility | `gummy-realtime-v1` |
| `EMBEDDING_MODEL` | Yes | Embedding model used for memory retrieval | `text-embedding-v4` |
| `EMBEDDING_DIMENSIONS` | Yes | Embedding vector size | `1024` |
| `EMBEDDING_OUTPUT_TYPE` | Yes | Embedding output mode | `dense` |
| `APP_HOST` | Yes | Backend bind host | `127.0.0.1` |
| `APP_PORT` | Yes | Backend bind port | `8000` |
| `DEBUG` | Yes | Enables debug/reload behavior for local development | `true` |

### Additional runtime envs used by code but not listed in `.env.example`

- `QWEN_TURBO_MODEL` — used by the intent classifier, memory extractor, and offline replay; defaults to `qwen-turbo` in `settings.py`
- `MEMORY_DB_PATH` — overrides the default SQLite path; defaults to `<repo>/data/sqlite/memory.db`
- `NEXT_PUBLIC_WS_URL` — optional frontend override used by `useRealtimeSession`; defaults to `ws://127.0.0.1:8000/ws/realtime`

## Running Tests

Broad suite command:

```bash
python -m pytest tests/ -v
```

Current unit-test surface in `tests/unit/`:

- 10 unit test files
- 221 test functions discovered from the current checked-in test files

Focused commands that match the project’s own agent rules:

```bash
.venv\Scripts\pytest.exe tests/unit/test_realtime_route.py -v --timeout=30 -x
.venv\Scripts\pytest.exe tests/unit/test_realtime_client.py -v --timeout=30 -x
.venv\Scripts\pytest.exe tests/unit/test_memory.py -v --timeout=30 -x
.venv\Scripts\pytest.exe tests/unit/test_learning.py -v --timeout=30 -x
```

Expected output shape:

```bash
============================= test session starts =============================
platform win32 -- Python 3.11.x, pytest-9.x.x
collecting ... collected N items

tests/unit/test_realtime_route.py::test_health_endpoint_still_works PASSED
...

============================= N passed in X.XXs ==============================
```

### What is covered today

- realtime route behavior
- realtime transport behavior
- memory extraction and persistence
- prompt builder logic
- policy routing
- learning / reflection / rollback / replay behavior
- settings and model/env defaults
- heavy vision request/response helpers

## Models Used

| Model | Purpose | Profile |
|-------|---------|---------|
| `qwen3.5-omni-plus-realtime` | Primary realtime speech/chat model used for live replies over DashScope WebSocket | `dev`, `exam` |
| `qwen3.6-plus` | Heavy vision model used for scene reading, OCR-style reads, and page summaries | `dev`, `exam` |
| `gummy-realtime-v1` | Configured transcription model in settings/env; runtime maps it to a DashScope-compatible wire model | all profiles |
| `qwen3-asr-flash-realtime` | Internal wire-level transcription model used when `gummy-realtime-v1` is configured | internal transport behavior |
| `qwen-turbo` | Intent classification, personal fact extraction, and offline replay patch analysis | backend support model |
| `text-embedding-v4` | Memory embedding generation for similarity recall | backend support model |

### Voice configuration

- Voice ID: `Tina`
- Source of truth: `QWEN_OMNI_VOICE`
- Used by: realtime session update in `QwenRealtimeClient`

## Memory System

### Overview

The memory system is split into explicit memory writes, automatic fact extraction, similarity-based recall, and session-start preload.
It is orchestrated by `MemoryManager`, persisted by `MemoryStore`, and grounded in SQLite plus DashScope embeddings.

### 1. Explicit memory save

- User text is normalized with `build_memory_fact()`.
- Memory-save phrases like `remember`, `save permanently`, `store in permanent memory`, and similar multilingual phrases are stripped.
- `MemoryManager.save()` optionally calls the extractor to turn raw speech into a normalized fact.
- The final fact is embedded and written with priority `2`.

Example behavior from code:

- “remember that my doctor is Dr. Sharma” becomes a saved fact
- category inference can mark it as `MEDICAL`
- the spoken confirmation is built from the exact stored fact

### 2. Automatic fact extraction

- `realtime.py` decides whether a turn is worth extracting from.
- Only personal-fact-like transcripts are forwarded to `_defer_auto_extract()`.
- `Mem0Extractor` calls `qwen-turbo` through DashScope compatible mode.
- The extractor outputs JSON objects with:
  - `fact`
  - `category`
  - `tier`

The extraction prompt explicitly tells the model to:

- extract only user facts
- ignore scene descriptions
- ignore questions
- normalize multilingual statements into English fact strings

### 3. Storage layout

Memory tables in SQLite:

- `long_term_memories`
- `short_term_memories`

Learning/correction tables in the same SQLite database:

- `transcript_log`
- `correction_log`
- `reflection_log`
- `patch_store`

That means the live system uses one SQLite file for both memory and the learning layer.

### 4. Recall path

- A recall query is embedded with `text-embedding-v4`.
- `MemoryStore.recall_facts()` computes cosine similarity over stored embedding JSON blobs.
- The route injects matching facts into the live session prompt.
- Name recall gets an extra exact-name instruction so the spoken response uses the stored value instead of re-transcribing the name loosely.

### 5. Pre-load at session start

- On WebSocket connect, the route loads priority facts with `get_priority_facts()`.
- Those facts are formatted into a memory block.
- The block is appended to the default realtime instructions before the DashScope session starts.
- The backend logs how many facts were injected.

### 6. Deduplication and updates

- `save_fact()` can deduplicate by category for non-`GENERAL` facts.
- The latest fact in a matching category can be updated instead of inserted again.
- There is also similarity-based update behavior using cosine similarity above `0.92`.
- Priority facts are ordered by `priority DESC, created_at DESC` when preloaded.

### 7. Session memory vs persistent memory

The code keeps two layers separate:

- `SessionMemory`
  - recent conversation turns
  - recently seen objects from heavy vision turns
- `MemoryStore`
  - durable long-term and short-term memory in SQLite

Heavy-vision turns can store `vision_objects` in session memory for immediate context.

## Self-Correction System

### 1. Correction detection

The realtime route looks for explicit correction phrases such as:

- English: `that's wrong`, `incorrect`, `try again`, `not what I asked`
- Kannada: `ತಪ್ಪು`, `ಸರಿಯಿಲ್ಲ`, `ತಪ್ಪಾಗಿದೆ`
- Hindi: `गलत है`, `गलत`, `यह सही नहीं`

When a correction is detected:

- the turn is written to `correction_log`
- the turn is also written to `transcript_log`
- `OnlineReflection.record_turn()` updates per-session failure state

### 2. Failure score accumulation

- Failure scores are tracked per `(session_id, intent)` pair.
- Each correction adds `0.34`.
- Scores cap at `1.0`.
- The configured threshold is `1.0`.

So a series of three corrections on the same intent is enough to cross the caution threshold.

### 3. Verbosity modes

The code supports three modes:

- `NORMAL`
- `COMPACT`
- `VERBOSE`

`OnlineReflection.update_verbosity()` switches mode from user phrases like:

- compact: `shorter`, `brief`, `concise`, `ಚಿಕ್ಕದಾಗಿ`, `संक्षेप में`
- verbose: `explain more`, `more detail`, `verbose`, `विस्तार`, `ಇನ್ನಷ್ಟು`

The mode is stored per session, not globally.

### 4. Prompt impact

`build_system_prompt()` changes behavior in two ways:

- `COMPACT` adds `Keep your answer under 2 sentences.`
- `VERBOSE` adds `Give a thorough, detailed explanation.`

If intent penalty is active, it prepends:

`Let me be careful here… The user has corrected this type of answer before.`

### 5. Offline replay and patch lifecycle

After a session closes, the route schedules:

- `offline_replay.run_replay(session_id)`
- `offline_replay.promote_priority_memories(session_id)`

`OfflineReplay`:

- reads correction windows from `CorrectionStore`
- sends the turn window to `qwen-turbo`
- asks for a tiny JSON root-cause + fix suggestion
- stores suggested patches in `patch_store`

`PatchStore` persists patch state transitions:

- `pending`
- `active`
- `rolled_back`

`Rollback` can roll back weak patches when correction trends do not improve.

## Multilingual Support

### Primary spoken-language path

The code is clearly optimized for:

- Kannada
- Hindi
- English

These languages appear directly in:

- realtime instructions
- routing heuristics
- correction phrases
- memory extraction prompt

### Transcript cleanup

`detect_and_clean_transcript()` explicitly:

- keeps Kannada script (`kn`)
- keeps Hindi / Devanagari (`hi`)
- keeps Tamil (`ta`)
- treats suspicious Chinese / Thai / Vietnamese-style output as wrong-language ASR and drops it

That helps prevent the assistant from answering in the wrong language after mis-transcription.

### UI rendering support

The frontend imports and uses fonts for:

- Kannada
- Devanagari
- Tamil
- Telugu

That means the transcript UI is better prepared for Indic scripts than a default English-only font stack.

### Translation intent

`TRANSLATE` is part of the classifier and router.
When triggered, the system stays on the realtime chat path and asks the model to translate speech or visible text to the requested language.

### Explicitly rejected languages in prompts

The realtime prompt specifically instructs the assistant not to assume the user speaks:

- Chinese
- Vietnamese
- Thai
- Japanese

unless that language is clearly intended.

## Contributing

Contributions are welcome.

Suggested workflow:

1. Fork the repository.
2. Create a feature branch.
3. Keep changes small and focused.
4. Run the relevant unit tests before opening a PR.
5. Preserve the existing architecture split between:
   - backend transport
   - frontend browser loop
   - core memory/learning/orchestration modules
6. Follow the project’s source-of-truth rule:
   document what the code actually does.

## License

MIT License — see the `LICENSE` file.

## Acknowledgements

- Alibaba DashScope for the Qwen Omni, compatible-mode, and embedding APIs
- The FastAPI community
- The Next.js and React communities
- The Tailwind and shadcn ecosystems
- Built for the blind and visually impaired community
