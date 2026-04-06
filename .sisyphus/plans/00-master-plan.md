---

# Plan 00 — Master Plan
# Ally Vision Assistant v2

---

## 1. Project Overview
Ally Vision Assistant v2 is a blind-first, camera-first laptop web assistant where the user speaks naturally and points the laptop camera at the world or a document, and the system answers with spoken guidance and grounded visual understanding. The product is DashScope-only and SQLite-only, uses no file-upload-first workflow, runs in a browser on a normal laptop, and is explicitly voice-first and camera-first rather than smart-glasses-first.

---

## 2. Current Repo State
- **Already present and working**
  - `shared/config/settings.py` is implemented and reads environment configuration, PROFILE switching, DashScope endpoints, model defaults, embedding settings, app host/port, `get_api_key()`, and `get_config()`.
  - `apps/backend/main.py` is implemented and exposes `GET /health` and `GET /config`, configures logging from settings, and enables CORS for `http://localhost:3000` and `http://127.0.0.1:3000`.
  - `tests/unit/test_settings.py` exists and passes.
  - Verified pass count: **7 passed**.
  - Root project/config files already exist: `requirements.txt`, `requirements-dev.txt`, `pyproject.toml`, `pyrightconfig.json`, `pytest.ini`, `.env.example`, `AGENTS.md`.
  - Data scaffolding already exists: `data/captures/`, `data/docsessions/`, `data/reflections/`, `data/sqlite/`, `data/transcripts/`, plus a pre-existing `data/memory.db` file.

- **Present but scaffold-only / package-only**
  - Backend directories: `apps/backend/api/routes/`, `apps/backend/db/`, `apps/backend/services/capture/`, `apps/backend/services/dashscope/`, `apps/backend/services/response/`.
  - Core directories: `core/orchestrator/`, `core/vision/`, `core/memory/`, `core/session/`, `core/search/`, `core/learning/`.
  - Frontend directories: `apps/frontend/app/`, `apps/frontend/hooks/`, `apps/frontend/lib/`, `apps/frontend/components/ui/`, `apps/frontend/public/worklets/`.
  - Tests scaffold: `tests/integration/` exists but is empty except package marker.
  - Shared schema scaffold: `shared/schemas/` exists but contains only package marker.

- **Not yet created in real implementation form**
  - No `/ws/realtime` route.
  - No `/document-session` route.
  - No `/memory` route.
  - No realtime client implementation.
  - No heavy vision client implementation.
  - No embedding client implementation.
  - No search manager/service implementation.
  - No document-session manager implementation.
  - No memory retrieval/store implementation.
  - No frontend page, camera view, control bar, transcript drawer, or browser hooks.
  - No SQLite bootstrap/schema code for the planned tables below.

- **Current test status**
  - `tests/unit/test_settings.py` covers profile defaults, realtime model presence, vision model presence, embedding defaults, DashScope endpoint strings, `get_config()` shape, and `get_api_key()` failure behavior.
  - Current verified total: **7/7 passing**.

---

## 3. Locked Scope

### In Scope
- live voice conversation (STT+TTS via Qwen Omni Realtime)
- scene description from laptop camera
- read text from what camera sees (OCR-style via heavy vision)
- scan single page by voice command
- scan multi-page document by voice
- ask questions about current page
- ask questions about scanned document
- summarize page or document
- compare two pages or captured views
- web search via DashScope search
- remember user facts in SQLite
- recall user memory
- optional live transcript (gummy-realtime-v1, reference-only)
- online self-improvement (prompt/routing adaptation per session)
- offline replay-based improvement

### Out of Scope
- LiveKit, Deepgram, ElevenLabs, Ollama
- YOLO, MiDaS, SAM, local OCR engine
- biometric face recognition
- FAISS, pgvector, Qdrant, vector DBs
- Docker, deployment pipelines
- file-picker upload UI in main workflow
- safety-critical navigation
- local AI models of any kind

---

## 4. Core User Flows
1. **"What is in front of me?" — realtime scene description**  
   User says "What is in front of me?" → browser streams mic PCM to backend and attaches the current live frame or controlled frame sample; backend routes the turn to the realtime DashScope path for fast voice+image response → user hears a short spoken scene description.

2. **"Read this" — camera OCR via heavy vision, with capture coach**  
   User says "Read this" while pointing camera at text → orchestrator pauses fast dialogue mode, checks frame quality, sends a strong snapshot to heavy vision for OCR-style extraction, and falls back to capture coach if the frame is weak → user hears either the extracted text or spoken framing guidance.

3. **"Scan this page" — capture + internal storage + confirmation**  
   User says "Scan this page" → capture coach verifies a usable page image, backend stores the page image plus raw text/summary metadata into the active session store, and increments page count → user hears that the page was captured and stored.

4. **"Start document / next page / finish document" — multi-page session**  
   User says "Start document" to open a document session, then "Next page" for each new capture, then "Finish document" to close it → backend manages session state, page order, and stored page assets in SQLite-backed metadata + disk-backed captures → user hears session start, page-count confirmations, and final completion status.

5. **"Summarize this document" — document QA from stored pages**  
   User says "Summarize this document" after scanning pages → backend assembles the stored page pack, summaries, OCR text, and ordering context, then sends grounded document context to the heavy vision/document path → user hears a spoken document summary grounded in the captured pages.

6. **"Ask this document: [question]" — grounded document answer**  
   User asks a document question after a page or document scan → backend retrieves the current-page pack or full document pack, routes the question with only stored evidence, and rejects unsupported guessing if evidence is weak → user hears a grounded answer or a request to rescan unclear pages.

7. **"Search [topic]" — DashScope web search path**  
   User says "Search [topic]" → intent router sends the request to the backend search service, which calls DashScope search explicitly, ranks results, and feeds a concise grounded summary back into the answer builder → user hears a spoken search answer with clear grounding.

8. **"Remember [fact]" — SQLite memory write**  
   User says "Remember my doctor is Dr. Sharma" or similar → backend normalizes the fact, writes it into SQLite memory tables, and creates an embedding record for future retrieval → user hears a spoken confirmation that the fact was saved.

9. **"Recall [fact]" — SQLite memory read with embedding retrieval**  
   User says "Who is my doctor?" or similar → backend embeds the query, searches stored dense vectors inside SQLite-backed retrieval logic, selects the best fact record, and returns the grounded memory result → user hears the recalled fact or a clear "I don't have that saved yet" response.

10. **Capture coach flow — bad frame → spoken guidance → retry**  
    User asks to read or scan but the frame is blurred, cut off, dark, or too angled → capture coach blocks weak interpretation, produces spoken guidance such as "move closer," "hold still," or "tilt down slightly," then retries after a new frame → user hears guidance instead of a hallucinated answer.

---

## 5. Runtime Architecture
**Target runtime architecture; current repo only implements settings + `/health` + `/config`.**

**Layer 1: Browser**  
`getUserMedia()`, `requestVideoFrameCallback()`, backend WebSocket relay, optional `AudioWorklet`, and a Next.js + React + TypeScript + Tailwind + shadcn/ui frontend. Browser capture remains explicit and user-driven; no always-on background processing is assumed.

**Layer 2: FastAPI backend**  
`/ws/realtime` is the main browser-facing WebSocket endpoint; `/document-session` manages scan sessions; `/memory` handles memory read/write; `/health` and `/config` expose status/config. This layer owns the session manager, frame buffer, document session manager, memory manager, search manager, transcript manager, and API-key-safe relay/proxy behavior so the browser never holds the long-lived DashScope key directly.

**Layer 3: Orchestrator**  
The orchestrator classifies intent, decides whether the turn belongs to realtime dialogue, heavy vision, search, or memory, runs capture coach before expensive visual work, and applies verification/recapture rules when confidence is weak or the frame is unusable.

**Layer 4: DashScope API layer**  
- **4A: Realtime** — `qwen3.5-omni-plus-realtime` in exam mode and corrected flash-path dev mode over WebSocket for audio in/out, quick image turns, and live dialogue. `gummy-realtime-v1` stays transcript-only and reference-only.  
- **4B: Heavy vision** — `qwen3.5-flash` as the doc-confirmed visual-understanding baseline over HTTP for scene analysis, OCR, page understanding, comparison, and grounded document QA; `qwen3.6-plus` remains the configured exam override for heavier multimodal reasoning where enabled.  
- **4C: Search + memory** — DashScope web search and `text-embedding-v3` are called by backend services explicitly. Search is not treated as the source of truth for state or memory, and memory retrieval is not delegated to the realtime session itself.

**Layer 5: Evidence + session layer**  
This layer stores the latest live frames, captured page images, page order, page summaries, search results, user memory, and transcript records. It produces the current-page pack, document pack, and final grounded context bundle that answer generation consumes.

**Layer 6: Learning**  
Online learning judges corrected turns during a live session, adapts prompts/routing, and can roll back weak patches. Offline learning replays hard sessions, compares quality signals, and promotes only stable improvements.

---

## 6. Model Plan

| Use case | PROFILE=dev | PROFILE=exam |
|---|---|---|
| Realtime voice+image | qwen3-omni-flash-realtime | qwen3.5-omni-plus-realtime |
| Heavy vision/document | qwen3.5-flash | qwen3.6-plus |
| Transcription | gummy-realtime-v1 (fixed) | gummy-realtime-v1 (fixed) |
| Memory embeddings | text-embedding-v3 1024 dense | text-embedding-v3 1024 dense |

Note: `gummy-realtime-v1` is fixed by DashScope, transcript is reference-only, and may differ from the omni model's own interpretation.

Note: `text-embedding-v3` uses the DashScope native endpoint:  
`https://dashscope-intl.aliyuncs.com/api/v1/services/embeddings/text-embedding/text-embedding`

Note: DashScope 2026 realtime docs confirm `qwen3.5-omni-plus-realtime`, PCM audio, `gummy-realtime-v1`, and a 120-minute WebSocket cap. The repo currently names the dev realtime model as `qwen3.5-omni-flash-realtime`, but the doc-backed correction for the flash realtime path is `qwen3-omni-flash-realtime`, so the plan uses the corrected name.

Note: `qwen3.5-flash` is the doc-confirmed heavy-vision baseline. `qwen3.6-plus` is a valid configured exam-path model with official Alibaba launch-material multimodal evidence, but execution should make the full document path work on `qwen3.5-flash` first and treat `qwen3.6-plus` as the exam/high-accuracy override.

---

## 7. Data and Storage Plan
**Target storage design; this schema is not implemented yet.**

SQLite tables (all in `data/sqlite/ally_vision_v2.db`):
- `memory_records` — user facts, preferences, corrections
- `embedding_index` — text chunks + vector JSON (1024-dim)
- `document_sessions` — session id, title, page count, timestamps
- `page_store` — session_id, page_number, image_path, summary, raw_text
- `transcript_log` — session_id, turn_id, user_text, assistant_text, timestamp
- `correction_store` — turn_id, original, corrected, patch applied
- `reflection_store` — session_id, turn_id, quality_score, notes
- `patch_store` — patch_id, patch_type, content, status, score

Files on disk:
- `data/captures/` — live frame snapshots for vision queries
- `data/docsessions/` — captured page image files per session
- `data/transcripts/` — optional full transcript files per session
- `data/reflections/` — offline replay records

Implementation note: retrieval stays SQLite-only; embeddings are stored as dense vectors in SQLite-backed records and compared in app logic. No FAISS, pgvector, Qdrant, or external vector DB is introduced.

---

## 8. Implementation Phases

**Phase 01 — Scaffold + Config**  
Goal: working settings, health endpoint, tests passing  
Status: **ALREADY DONE** (`shared/config/settings.py`, `apps/backend/main.py`, `tests/unit/test_settings.py`, 7 tests passing, `/health` works)  
Key files:  
`shared/config/settings.py`, `apps/backend/main.py`  
Remaining: none — this phase is complete

**Phase 02 — DashScope Realtime Client**  
Goal: `QwenRealtimeClient` connecting to DashScope WebSocket, sending audio + image, receiving audio + transcript  
Key files:  
`apps/backend/services/dashscope/realtime_client.py`  
Success criteria:  
- Unit tests pass with WebSocket mock  
- `send_audio_turn()` and `send_image_turn()` implemented  
- reconnect on 120-minute session expiry  
- gummy transcript events parsed

**Phase 03 — FastAPI WebSocket Endpoint + Basic Audio**  
Goal: `/ws/realtime` endpoint receives browser audio, routes to `QwenRealtimeClient`, returns audio back  
Key files:  
`apps/backend/api/routes/realtime.py`  
`apps/backend/services/capture/frame_buffer.py`  
Success criteria:  
- Browser connects via WebSocket  
- Audio round-trip confirmed manually

**Phase 04 — Browser Camera + Mic Capture**  
Goal: Next.js frontend captures mic + camera frame, streams audio to backend, plays returned audio  
Key files:  
`apps/frontend/app/page.tsx`  
`apps/frontend/app/layout.tsx`  
`apps/frontend/components/camera-view.tsx`  
`apps/frontend/components/control-bar.tsx`  
`apps/frontend/components/status-pill.tsx`  
`apps/frontend/hooks/useCameraCapture.ts`  
`apps/frontend/hooks/useMicStream.ts`  
`apps/frontend/hooks/useRealtimeSession.ts`  
`apps/frontend/lib/ws-client.ts`  
`apps/frontend/lib/audio-utils.ts`  
Success criteria:  
- Open browser, see camera feed  
- Speak and hear Cherry voice respond  
- Status pill shows: Listening / Thinking / Speaking

**Phase 05 — Orchestrator + Intent Router**  
Goal: classify user intent, route to correct handler  
Key files:  
`core/orchestrator/intent_classifier.py`  
`core/orchestrator/policy_router.py`  
`core/orchestrator/verification.py`  
`core/orchestrator/prompt_builder.py`  
`apps/backend/services/capture/capture_coach.py`  
Success criteria:  
- `"read this"` routes to heavy vision  
- `"what is in front of me"` routes to realtime  
- `"search X"` routes to search  
- `"remember X"` routes to memory  
- Blurry frame triggers capture coach guidance

**Phase 06 — Heavy Vision + Document Path**  
Goal: send camera frame to `qwen3.5-flash` for OCR, scene analysis, page understanding  
Key files:  
`apps/backend/services/dashscope/multimodal_client.py`  
`core/vision/live_scene_reader.py`  
`core/vision/page_reader.py`  
`core/vision/framing_judge.py`  
`core/vision/compare_service.py`  
`apps/backend/services/capture/page_capture_service.py`  
Success criteria:  
- `"read this"` returns text from camera  
- Blurry frame returns capture guidance, not a guess  
- Two frames can be compared

**Phase 07 — Memory + Embeddings**  
Goal: store/retrieve user memory using `text-embedding-v3`  
Key files:  
`apps/backend/services/dashscope/embedding_client.py`  
`core/memory/memory_store.py`  
`core/memory/embedding_store.py`  
`core/memory/correction_store.py`  
`core/memory/retrieval.py`  
`apps/backend/api/routes/memory.py`  
`apps/backend/db/sqlite.py`  
`apps/backend/db/bootstrap.py`  
Success criteria:  
- `"remember my doctor is Dr. Sharma"` stored  
- `"who is my doctor"` retrieves correctly  
- `text-embedding-v3` returns 1024-dim vectors

**Phase 08 — Web Search**  
Goal: DashScope search enabled as an explicit routed backend step and optionally available to realtime response composition  
Key files:  
`apps/backend/services/dashscope/search_client.py`  
`core/search/web_search.py`  
`core/search/query_planner.py`  
`core/search/result_ranker.py`  
Success criteria:  
- `"search latest news about X"` returns web result  
- Result injected into spoken response

**Phase 09 — Document Sessions**  
Goal: scan multi-page document, ask questions over it  
Key files:  
`core/session/document_session.py`  
`core/session/page_store.py`  
`core/session/transcript_store.py`  
`core/session/session_state.py`  
`apps/backend/api/routes/document_session.py`  
`apps/frontend/components/document-session-panel.tsx`  
`apps/frontend/hooks/useDocumentSession.ts`  
Success criteria:  
- `"start document"` opens session  
- `"next page"` captures and stores page  
- `"finish document"` closes session  
- `"summarize this document"` answers from stored pages

**Phase 10 — Self-Improvement**  
Goal: log corrections, adapt prompts, replay offline  
Key files:  
`core/learning/online_reflection.py`  
`core/learning/patch_store.py`  
`core/learning/rollback.py`  
`core/learning/offline_replay.py`  
Success criteria:  
- Corrected turns logged in `correction_store`  
- Prompts adapted within session  
- Weak patches rolled back automatically

**Phase 11 — Transcript + Polish**  
Goal: gummy transcript events surfaced in UI, all status messages working, edge cases handled  
Key files:  
`apps/backend/services/dashscope/transcript_client.py`  
`core/session/transcript_store.py`  
`apps/frontend/components/transcript-drawer.tsx`  
`apps/backend/api/routes/debug.py`  
Success criteria:  
- Transcript drawer shows reference transcript  
- All 10 core user flows work end-to-end  
- Status pill shows all states correctly  
- No crashes on bad frames or empty audio

---

## 9. Testing Strategy
Rules:
- NEVER run: `pytest tests/` (all at once)
- ALWAYS run: `pytest tests/unit/[file].py -v --timeout=30 -x`
- One file at a time
- Fix all failures before proceeding to next plan

Unit tests per phase:
- Phase 02: `test_realtime_client.py` (WebSocket mock)
- Phase 03: `test_realtime_route.py`
- Phase 05: `test_intent_classifier.py`, `test_policy_router.py`, `test_capture_coach.py`, `test_prompt_builder.py`
- Phase 06: `test_heavy_vision.py`, `test_framing_judge.py`
- Phase 07: `test_memory_store.py`, `test_embedding_store.py`
- Phase 08: `test_web_search.py`
- Phase 09: `test_document_session.py`, `test_page_store.py`
- Phase 10: `test_online_reflection.py`, `test_patch_store.py`

Integration tests:
- `test_realtime_route.py` — WebSocket round trip
- `test_memory_route.py` — memory read/write via API
- `test_document_flow.py` — scan + ask full flow
- `test_search_flow.py` — search + answer flow

Physical gate checks (human verified):
- Phase 04: speak hello → hear Cherry voice
- Phase 06: point at text → hear it read aloud
- Phase 07: remember fact → recall it later
- Phase 09: scan 3 pages → ask about page 2

Execution note: browser-facing work should also receive Playwright-based verification for permission prompts, UI states, transcript display, and retry/capture-coach behavior, while API and storage work should receive targeted pytest and HTTP assertions.

---

## 10. Risks and Constraints
- Laptop webcam has limited framing control for blind users  
  Mitigation: capture coach with spoken guidance before capture

- `gummy-realtime-v1` transcript is reference-only  
  Mitigation: never use it as definitive truth, log only

- DashScope realtime session max 120 minutes  
  Mitigation: detect near-expiry, reconnect as full new session

- DashScope free quota is expected to expire 2026-07-03  
  Mitigation: use dev profile for most testing, switch exam profile only for final demo

- `text-embedding-v3` stored as JSON in SQLite is simple, not ANN-optimized  
  Mitigation: acceptable for college-project scale, no vector DB needed

- Browser camera requires secure context (HTTPS or localhost)  
  Mitigation: use `localhost:3000` during development

- Browser audio capture is not natively PCM in many environments  
  Mitigation: normalize or transcode to the PCM format DashScope requires before sending

- Browser must not expose the long-lived DashScope API key  
  Mitigation: keep the backend as the only DashScope-authenticated relay/proxy

- Blind-first UX can only be validated by real testing  
  Mitigation: physical gate checks required at each phase

---

## 11. Definition of Done
Project is complete when ALL of these are true:
- ✅ All 10 core user flows work end-to-end physically
- ✅ Tests pass: unit + integration, 0 failures
- ✅ DashScope native endpoint confirmed working
- ✅ Cherry voice responds to voice in browser
- ✅ Camera reads text correctly on good frames
- ✅ Bad frames trigger capture guidance, not hallucination
- ✅ Memory stores and retrieves correctly
- ✅ Document scan + QA works for 3+ pages
- ✅ Web search returns spoken answer
- ✅ Self-improvement logs corrections without crashing
- ✅ No `localhost:11434` or local model references anywhere
- ✅ `.env` not committed
- ✅ Academic report section `Working of the System` complete

---

## 12. Next Plan Files
- `01-scaffold.md`          ← ALREADY DONE (rename to reflect status)
- `02-realtime-client.md`   ← DashScope WS client (Phase 02)
- `03-websocket-route.md`   ← FastAPI WS route (Phase 03)
- `04-frontend-capture.md`  ← Browser camera+mic (Phase 04)
- `05-orchestrator.md`      ← Intent routing (Phase 05)
- `06-heavy-vision.md`      ← Heavy vision path (Phase 06)
- `07-memory.md`            ← SQLite + embeddings (Phase 07)
- `08-search.md`            ← Web search (Phase 08)
- `09-document-sessions.md` ← Scan + QA (Phase 09)
- `10-learning.md`          ← Self-improvement (Phase 10)
- `11-polish.md`            ← Transcript + polish (Phase 11)
