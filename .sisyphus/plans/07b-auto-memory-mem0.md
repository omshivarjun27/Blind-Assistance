# Plan 07b — Auto Memory Upgrade with Mem0-Style Extraction, Three-Tier Memory, and text-embedding-v4

## 0. Repo audit findings before planning (source of truth)

This section records the required file reads and exact line-number findings before any plan content.

### 0.1 Locked environment and current settings truth

- `shared/config/settings.py:27-44` confirms the repo is already configured for:
  - `PROFILE` default `dev`
  - `DASHSCOPE_REGION`
  - `DASHSCOPE_HTTP_BASE = https://dashscope-intl.aliyuncs.com/api/v1`
  - `DASHSCOPE_REALTIME_URL = wss://dashscope-intl.aliyuncs.com/api-ws/v1/realtime`
  - `DASHSCOPE_COMPAT_BASE = https://dashscope-intl.aliyuncs.com/compatible-mode/v1`
- `shared/config/settings.py:47-55` confirms current derived model selection is already:
  - realtime = `qwen3-omni-flash-realtime`
  - heavy vision = `qwen3.6-plus`
  - transcription = `gummy-realtime-v1`
- `shared/config/settings.py:57-61` confirms current embedding config is already:
  - `EMBEDDING_MODEL = text-embedding-v4`
  - `EMBEDDING_DIMENSIONS = 1024`
  - `MEMORY_DB_PATH = data/sqlite/memory.db`
- `shared/config/settings.py:61-64` confirms the DB parent directory is created at settings load time.
- `shared/config/settings.py:77-89` confirms `get_config()` already surfaces realtime / vision / embedding values.
- `.env:1-19` matches the locked environment values in this prompt, including:
  - `PROFILE=dev`
  - `DASHSCOPE_REGION=singapore`
  - `DASHSCOPE_HTTP_BASE=https://dashscope-intl.aliyuncs.com/api/v1`
  - `DASHSCOPE_REALTIME_URL=wss://dashscope-intl.aliyuncs.com/api-ws/v1/realtime`
  - `DASHSCOPE_COMPAT_BASE=https://dashscope-intl.aliyuncs.com/compatible-mode/v1`
  - `QWEN_REALTIME_DEV=qwen3-omni-flash-realtime`
  - `QWEN_REALTIME_EXAM=qwen3-omni-flash-realtime`
  - `QWEN_REALTIME_MODEL=qwen3-omni-flash-realtime`
  - `QWEN_OMNI_VOICE=Cherry`
  - `QWEN_VISION_DEV=qwen3.6-plus`
  - `QWEN_VISION_EXAM=qwen3.6-plus`
  - `QWEN_TRANSCRIPTION_MODEL=gummy-realtime-v1`
  - `EMBEDDING_MODEL=text-embedding-v4`
  - `EMBEDDING_DIMENSIONS=1024`
  - `EMBEDDING_OUTPUT_TYPE=dense`
  - `APP_HOST=127.0.0.1`
  - `APP_PORT=8000`
  - `DEBUG=true`
- `apps/frontend/.env.local:1` contains only `NEXT_PUBLIC_WS_URL=ws://127.0.0.1:8000/ws/realtime`.

### 0.2 Current routing and prompt-builder truth

- `core/orchestrator/policy_router.py:23-30` defines route targets including `MEMORY_WRITE` and `MEMORY_READ`.
- `core/orchestrator/policy_router.py:41-44` marks only `WEB_SEARCH` and `DOCUMENT_QA` as unimplemented fallback targets.
- `core/orchestrator/policy_router.py:68-77` confirms `MEMORY_SAVE -> MEMORY_WRITE` and `MEMORY_RECALL -> MEMORY_READ` are already treated as implemented.
- `core/orchestrator/policy_router.py:83-91` confirms `TRANSLATE` currently routes to `REALTIME_CHAT`.
- `core/orchestrator/prompt_builder.py:23-37` confirms `build_system_prompt()` already accepts `memory_context` and `document_context`.
- `core/orchestrator/prompt_builder.py:49-55` confirms `build_memory_fact()` still strips manual prefixes (`remember that`, `save this`, etc.).

### 0.3 Current realtime route truth

- `apps/backend/api/routes/realtime.py:45-72` confirms `_PAST_TENSE_TRIGGERS` already exists.
- `apps/backend/api/routes/realtime.py:75-80` confirms `_is_memory_query()` already exists.
- `apps/backend/api/routes/realtime.py:96-99` confirms `_make_silent_pcm`-equivalent helper exists as `make_silent_pcm()`.
- `apps/backend/api/routes/realtime.py:152` declares `last_user_transcript` as websocket-session local state.
- `apps/backend/api/routes/realtime.py:155-156` shows the route currently calls `memory_manager.store.initialize()`, not a multi-table initializer.
- `apps/backend/api/routes/realtime.py:157-161` defines current per-turn state:
  - `pending_classification_task`
  - `pending_classification_image_b64`
  - `queued_classification_input`
  - `pending_image_b64`
  - `pending_instructions`
- `apps/backend/api/routes/realtime.py:179-227` confirms previous-turn classifier lookahead is still the main routing path.
- `apps/backend/api/routes/realtime.py:224-227` confirms first-turn image fallback already exists:
  - if `predicted_intent is None and pending_image_b64`, route defaults to `SCENE_DESCRIBE`.
- `apps/backend/api/routes/realtime.py:238-282` shows classifier-routed memory save/recall still use the manual Plan 07 `memory_manager.save()` / `memory_manager.recall()` flow.
- `apps/backend/api/routes/realtime.py:283-339` shows the current heavy-vision branch already exists and must be preserved structurally.
- `apps/backend/api/routes/realtime.py:360-434` shows same-turn memory detection still uses manual prefix/phrase logic:
  - `build_memory_fact(current_user_transcript)`
  - `_RECALL_PHRASES`
  - override turn with `make_silent_pcm(0.5)`
- `apps/backend/api/routes/realtime.py:388, 398, 401, 427, 430, 433, 440` show the current `_skip_classifier` guard points.
- `apps/backend/api/routes/realtime.py:439-455` shows previous-turn classification scheduling still happens after the turn and already logs `_is_memory_query(last_user_transcript or "")` for future Plan 07 use.
- `apps/backend/api/routes/realtime.py:458-459` resets `pending_image_b64` and `pending_instructions` per turn.
- `apps/backend/api/routes/realtime.py:543-551` shows disconnect/finally cleanup currently only closes the client; no session-memory cleanup exists yet.

### 0.4 Current memory layer truth

- `core/memory/__init__.py:5-15` exports only `EmbeddingClient`, `EmbeddingError`, `MemoryStore`, and `MemoryManager`.
- `core/memory/embedding_client.py:24-30` confirms `EmbeddingClient.from_settings()` already reads `DASHSCOPE_COMPAT_BASE`, `EMBEDDING_MODEL`, and `EMBEDDING_DIMENSIONS` dynamically from settings.
- `core/memory/embedding_client.py:39-45` confirms the embedder already calls `/embeddings` with:
  - `model`
  - `input`
  - `dimensions`
  - `encoding_format = "float"`
  - and does **not** send `output_type`.
- `core/memory/memory_store.py:22-42` confirms there is only one current table: `memories`.
- `core/memory/memory_store.py:27-33` confirms current schema is:
  - `id`
  - `user_id`
  - `fact`
  - `embedding_json`
  - `created_at`
- `core/memory/memory_store.py:44-66` confirms `save_fact()` currently only inserts into `memories`.
- `core/memory/memory_store.py:68-103` confirms `recall_facts()` currently only searches `memories` and ranks cosine similarity in Python.
- `core/memory/memory_manager.py:32-41` confirms `save()` still performs manual prefix stripping via `build_memory_fact()` and then stores one long-lived fact.
- `core/memory/memory_manager.py:43-61` confirms `recall()` still embeds the query and returns a joined string from the single-table store.

### 0.5 Current dependency and test truth

- `requirements.txt:1-12` confirms `mem0ai` is **absent**.
- `core/orchestrator/intent_classifier.py:1-154` confirms `qwen-turbo` is already used in code as the classifier model default (`:85`) and described in the module/class docstrings (`:2`, `:78`).
- `tests/unit/test_memory.py:9-150` confirms there are currently **8** memory tests.
- `tests/unit/test_realtime_route.py:807-862` confirms `_is_memory_query` tests already exist at route-test level.

### 0.6 Audit corrections to the prompt itself

The following prompt assumptions are stale and must be corrected in this revision plan:

- The repo is **not** on `text-embedding-v3`; `shared/config/settings.py:58` and `.env:14` already show `text-embedding-v4`.
- The current route test file is **not** at 19 tests anymore; `tests/unit/test_realtime_route.py` now contains 30 tests after Plan 05 additions.
- `_is_memory_query` is **present**, not absent (`realtime.py:75-80`).
- `_PAST_TENSE_TRIGGERS` is **present**, not absent (`realtime.py:48-72`).
- The first-turn image fallback is already implemented (`realtime.py:224-227`).

## 1. External doc verification (CONFIRMED vs UNCONFIRMED)

### 1.1 Mem0 open-source / mem0ai

1. **pip package: `mem0ai`**
   - **CONFIRMED**
   - Evidence:
     - `docs.mem0.ai/open-source/python-quickstart` shows `pip install mem0ai`.
     - The same quickstart shows `from mem0 import Memory` and `m = Memory()`.

2. **`Memory()` local / open-source mode with no Mem0 cloud key required**
   - **CONFIRMED WITH NUANCE**
   - Evidence:
     - Mem0 open-source docs distinguish `Memory` (OSS/self-hosted) from `MemoryClient` (hosted platform).
     - Open-source quickstart uses `Memory()` and not `MemoryClient(api_key=...)`.
   - Nuance:
     - This confirms no **Mem0 platform/cloud key** is required for OSS `Memory`.
     - It does **not** mean no model/embedder key is required at all. The quickstart explicitly says `Memory()` defaults to OpenAI unless reconfigured.

3. **`m.add(messages, user_id=...)` and `m.search(query, user_id=...)` APIs**
   - **CONFIRMED**
   - Evidence:
     - `docs.mem0.ai/open-source/python-quickstart` shows:
       - `m.add(messages, user_id="alex")`
       - `m.search("What do you know about me?", user_id="alex")`
     - `mem0ai/mem0` `AGENTS.md` also lists `add(messages, ..., user_id, ...)` and `search(query, ..., user_id, ...)`.

4. **Custom LLM config pointing to OpenAI-compatible endpoints**
   - **CONFIRMED WITH DASHSCOPE-SPECIFIC CAUTION**
   - Confirmed:
     - Mem0 docs support `Memory.from_config(...)`.
     - Mem0 config docs and repo config types expose `openai_base_url` for OpenAI-compatible providers.
   - Caution:
     - I still did not find an official Mem0 Python quickstart that explicitly names DashScope as the provider example.
   - Planning consequence:
     - It is safe to say Mem0 OSS can target OpenAI-compatible endpoints by config.
     - This plan still keeps the repo-local `Mem0Extractor` wrapper as the locked implementation surface to minimize architecture churn against the current SQLite-based memory design.

### 1.2 DashScope embeddings via compatible mode

1. **Model name exactly `text-embedding-v4`**
   - **CONFIRMED**
   - Evidence:
     - Alibaba Cloud text embedding docs explicitly show `model: "text-embedding-v4"`.

2. **`encoding_format: "float"` on the compatible endpoint**
   - **CONFIRMED**
   - Evidence:
     - Alibaba Cloud text embedding docs explicitly show `encoding_format: "float"`.

3. **1024 dimensions supported**
   - **CONFIRMED**
   - Evidence:
     - Alibaba Cloud docs list `1024` as a valid dimension for `text-embedding-v4`.

4. **Compatible endpoint is `POST https://dashscope-intl.aliyuncs.com/compatible-mode/v1/embeddings`**
   - **CONFIRMED**
   - Evidence:
     - Alibaba Cloud docs show the Singapore-region compatible endpoint exactly as `.../compatible-mode/v1/embeddings`.

5. **Do not send `output_type` on compatible mode**
   - **CONFIRMED BY CURRENT REPO + DOC SHAPE**
   - Evidence:
     - Official compatible examples show `model`, `input`, `dimensions`, and `encoding_format`, with no `output_type`.
     - Current repo embedder already matches this shape (`embedding_client.py:39-45`).

### 1.3 DashScope text generation via compatible mode

1. **Endpoint: `POST https://dashscope-intl.aliyuncs.com/compatible-mode/v1/chat/completions`**
   - **CONFIRMED**
   - Evidence:
     - Alibaba Cloud Model Studio text generation docs explicitly show the compatible chat completions endpoint.

2. **Response format: `choices[0].message.content`**
   - **CONFIRMED**
   - Evidence:
     - Alibaba Cloud docs explicitly show `choices[0].message.content` in compatible chat completions responses.

3. **Exact model ID `qwen-turbo` on compatible chat completions**
   - **CONFIRMED**
   - Evidence:
     - Alibaba compatibility docs confirm `qwen-turbo` is supported on the compatible `/chat/completions` surface.
   - Planning consequence:
     - Keep `qwen-turbo` as the extractor model exactly as locked in this prompt.

## 2. Purpose

This is a **revision and upgrade** to Plan 07, not a greenfield memory build.

Plan 07 (`cd1cf7a`) introduced a manual memory layer around:

- explicit `remember that...` save commands,
- explicit recall phrase routing,
- a single SQLite `memories` table,
- embedding-based semantic recall,
- and same-turn override replies using silent audio.

Plan 07b upgrades that baseline to **automatic memory** with three tiers:

1. **Session memory** — in-memory, recent turns + recent objects seen
2. **Short-term memory** — SQLite, TTL 7 days
3. **Long-term memory** — SQLite, persistent facts with contradiction-aware update behavior

The plan keeps the current repo’s strengths intact:

- existing realtime websocket route
- existing heavy-vision route branch
- existing DashScope embedder
- existing prompt builder
- existing route test surface

and replaces only the **manual memory ingestion / recall behavior** with **automatic extraction + automatic past-tense recall routing**.

## 3. Locked environment config (must not drift)

Use these exact environment values as plan source of truth:

- `PROFILE = dev`
- `DASHSCOPE_REGION = singapore`
- `DASHSCOPE_HTTP_BASE = https://dashscope-intl.aliyuncs.com/api/v1`
- `DASHSCOPE_REALTIME_URL = wss://dashscope-intl.aliyuncs.com/api-ws/v1/realtime`
- `DASHSCOPE_COMPAT_BASE = https://dashscope-intl.aliyuncs.com/compatible-mode/v1`
- `QWEN_REALTIME_DEV = qwen3-omni-flash-realtime`
- `QWEN_REALTIME_EXAM = qwen3-omni-flash-realtime`
- `QWEN_REALTIME_MODEL = qwen3-omni-flash-realtime`
- `QWEN_OMNI_VOICE = Cherry`
- `QWEN_VISION_DEV = qwen3.6-plus`
- `QWEN_VISION_EXAM = qwen3.6-plus`
- `QWEN_TRANSCRIPTION_MODEL = gummy-realtime-v1`
- `EMBEDDING_MODEL = text-embedding-v4`
- `EMBEDDING_DIMENSIONS = 1024`
- `EMBEDDING_OUTPUT_TYPE = dense`
- `APP_HOST = 127.0.0.1`
- `APP_PORT = 8000`
- `DEBUG = true`

Derived model assignments to use verbatim in code and plan language:

- Realtime audio model: `qwen3-omni-flash-realtime`
- Heavy vision model: `qwen3.6-plus`
- Embedding model: `text-embedding-v4`
- Embedding response shape: `encoding_format: "float"` on the compatible endpoint
- Transcription model: `gummy-realtime-v1`
- Mem0 extraction LLM: `qwen-turbo`
- Voice: `Cherry`

## 4. What is true now

### 4.1 Current repo state relevant to Plan 07b

- Plans `00` through `06b` and `07` already exist.
- The repo has progressed beyond `cd1cf7a`; that commit remains the historical Plan 07 anchor, not the current HEAD.
- Current manual memory implementation still exists in the route and store layers.
- The realtime route already has:
  - previous-turn classifier lookahead,
  - first-turn image fallback,
  - manual same-turn memory save/recall overrides,
  - heavy-vision routing,
  - `_is_memory_query` helper and `_PAST_TENSE_TRIGGERS`,
  - `_skip_classifier` coordination,
  - and a route-level regression suite that already exercises image, memory, interrupt, and heavy-vision interactions.
- The embedder is already on `text-embedding-v4` and already uses the correct compatible-mode field set.
- `requirements.txt` still lacks `mem0ai`.
- The store is still a single-table design and is the main thing that must expand structurally.

### 4.2 Scope correction vs the user prompt

Because the repo audit is authoritative, this plan intentionally corrects a few prompt assumptions:

- **No v3 → v4 embedding migration is needed in settings**; the repo already uses `text-embedding-v4`.
- **`_is_memory_query` is not a new invention for 07b**; it already exists and must be expanded / repurposed, not recreated from scratch.
- **The realtime route already has first-turn image fallback**; 07b should preserve it and build automatic memory around it.

## 5. Architecture target for Plan 07b

### 5.1 Goal

Replace the manual memory command flow with a fully automatic three-tier memory system:

- **automatic fact extraction after every turn**
- **automatic natural-language recall routing for past-tense questions**
- **session-scoped recent turn/object memory**
- **short-term expiring SQLite memory**
- **long-term persistent SQLite memory with contradiction-aware update behavior**

### 5.2 Design principles

1. **No explicit user command required** for save or recall.
2. **Do not restructure `realtime.py`**; make targeted additions only.
3. **Keep the current heavy-vision path intact** and piggyback automatic object capture on it.
4. **Never block browser response on extraction** — extraction must run in a background task.
5. **Preserve backward compatibility** for the existing `MemoryManager.save()` and `MemoryManager.recall()` interfaces.
6. **Use Mem0-inspired extraction semantics without forcing a risky direct Mem0 runtime dependency into the existing SQLite architecture.**

### 5.3 Three-tier memory design

#### Tier 1 — Session memory

Create `core/memory/session_memory.py`.

Purpose:

- in-memory only
- last 20 turns
- last objects seen from heavy vision
- cleared on websocket disconnect
- used for very recent queries like:
  - “what did I just show you?”
  - “what was the last thing you said?”

Class: `SessionMemory`

- `__init__(max_turns=20)`
- `add_turn(user_transcript, assistant_response, vision_objects=None)`
- `get_recent(n=5) -> list[dict]`
- `get_objects_seen() -> list[dict]`
- `clear()`

Storage rules:

- store turn entries in a `collections.deque(maxlen=max_turns)`
- object list may also be a bounded deque or append-only list pruned to the same window size
- timestamps stored as ISO strings or UTC datetimes converted at read time

#### Tier 2 — Short-term memory

Extend the SQLite layer with `short_term_memories`.

Schema:

- `id INTEGER PRIMARY KEY AUTOINCREMENT`
- `user_id TEXT NOT NULL`
- `fact TEXT NOT NULL`
- `embedding_json TEXT NOT NULL`
- `category TEXT NOT NULL DEFAULT 'GENERAL'`
- `created_at TEXT NOT NULL`
- `expires_at TEXT NOT NULL`

Behavior:

- TTL = 7 days
- purge expired rows on startup / initialization
- max 100 rows per user
- evict oldest overflow rows
- used for recent observations, temporary states, recent object sightings, and ephemeral conversation context

#### Tier 3 — Long-term memory

Promote the current `memories` table to `long_term_memories`.

Schema:

- `id INTEGER PRIMARY KEY AUTOINCREMENT`
- `user_id TEXT NOT NULL`
- `fact TEXT NOT NULL`
- `embedding_json TEXT NOT NULL`
- `category TEXT NOT NULL`
- `created_at TEXT NOT NULL`
- `updated_at TEXT NOT NULL`

Behavior:

- never auto-deleted
- contradiction / near-duplicate handling via cosine > 0.92
- update existing row rather than insert duplicate when same semantic fact reappears

Target long-term categories:

- `IDENTITY`
- `LOCATION`
- `HEALTH`
- `PREFERENCE`
- `RELATIONSHIP`

### 5.4 Automatic extraction design

#### Important implementation choice

Although this plan is Mem0-inspired and adds `mem0ai` to dependencies, the **locked runtime implementation** should use a repo-local `Mem0Extractor` wrapper that calls DashScope-compatible `/chat/completions` directly.

Reason:

- the repo already has a working SQLite + DashScope architecture,
- direct Mem0 OSS runtime integration would introduce undocumented Python config risks and broader storage churn,
- the goal is automatic extraction semantics with low architectural disruption.

#### New file: `core/memory/mem0_extractor.py`

Class: `Mem0Extractor`

- uses `httpx.AsyncClient`
- model = `qwen-turbo`
- endpoint = `DASHSCOPE_COMPAT_BASE/chat/completions`
- timeout = 8s
- `from_settings()` constructor
- method:
  - `async extract(user_transcript: str, assistant_transcript: str) -> list[dict]`

Micro-prompt contract:

> Extract persistent user facts from this exchange only.
> Return JSON array `[{fact, category, tier}]` or `[]`.
> Categories: `IDENTITY`, `LOCATION`, `HEALTH`, `PREFERENCE`, `RELATIONSHIP`, `CONVERSATION`, `OBSERVATION`.
> `tier=long` for persistent facts.
> `tier=short` for temporary observations and recent state.
> Never extract assistant statements as user facts.
> Return only `[]` if nothing is extractable.

Parsing rule:

- never raise
- JSON parse failure returns `[]`
- upstream HTTP failure returns `[]`
- malformed entries are skipped, not fatal

### 5.5 Automatic recall routing design

Expand the existing `_is_memory_query` function rather than creating a parallel helper.

Target trigger coverage:

- English:
  - `what is my`
  - `who is my`
  - `where is my`
  - `what was`
  - `what did i`
  - `do you remember`
  - `what did i tell you`
  - `recall`
  - `earlier`
  - `before`
  - `last time`
  - `previously`
  - `what did i show you`
- Kannada transliteration:
  - `nanna hesaru`
  - `nanna`
  - `neevu`
  - `hinde`
  - `mundhe`
- Hindi transliteration:
  - `mera naam`
  - `meri`
  - `tumhe yaad hai`
  - `pehle`
  - `aage`
- generic English past-tense heuristic:
  - detect leading past-tense helper forms such as `was`, `were`, `had`, `did`
  - and common past-tense verbs such as `showed`, `told`, `said`

Routing order after a turn result is received:

1. derive `current_user_transcript`
2. `is_recall = is_memory_query(current_user_transcript)`
3. if recall:
   - query session memory
   - query short-term memory
   - query long-term memory
   - compose memory context in priority order:
     1. session memory
     2. recent objects seen
     3. short-term facts
     4. long-term facts
   - run override turn with `make_silent_pcm(0.5)`
   - use `build_system_prompt(..., memory_context=combined)`
   - set `result = override_result`
   - set `skip_classifier = True`

### 5.6 Object-seen auto-storage from heavy vision

When the heavy-vision branch produces a successful result, also push a compact object/observation summary into session memory and short-term memory.

Do **not** change the heavy-vision route structure.

Use a small observation such as:

- `Object/text seen: {vision_result.text[:120]}`

This lets the app answer questions like:

- “What did I show you earlier?”

even when the observation is session-local and not yet promoted to durable long-term memory.

## 6. Files to create

### 6.1 `core/memory/session_memory.py`

Create an in-memory ring buffer module.

Implementation details:

- use `collections.deque(maxlen=max_turns)`
- normalize blank transcripts to empty strings
- store dictionaries shaped like:
  - `{user, assistant, timestamp}`
- `vision_objects` should be optional list input and appended with timestamps
- `get_recent(n=5)` returns oldest-to-newest within the selected tail window
- `clear()` empties both turn and object buffers

### 6.2 `core/memory/mem0_extractor.py`

Create the automatic extraction wrapper around DashScope-compatible chat completions.

Implementation details:

- constructor takes `api_key`, `base_url`, `model`
- `from_settings()` reads:
  - `settings.get_api_key()`
  - `settings.DASHSCOPE_COMPAT_BASE`
  - `settings.QWEN_TURBO_MODEL`
- request body shape:
  - `model`
  - `messages`
  - maybe low-temperature generation params if needed
- response parse path:
  - `choices[0].message.content`
- wrap the extractor output to `list[dict]` with only:
  - `fact`
  - `category`
  - `tier`

### 6.3 `core/memory/memory_context_composer.py`

Create a pure function module:

- `compose_memory_context(session_turns, st_facts, lt_facts, objects_seen) -> str`

Output order:

1. `From this session:`
2. `From recent memory:`
3. `From long-term memory:`

Rules:

- if everything is empty, return `""`
- avoid blank headers when a section is empty
- session context must be listed before durable tiers

## 7. Files to edit

### 7.1 `requirements.txt`

Add:

- `mem0ai`

Do not remove existing dependencies.

### 7.2 `shared/config/settings.py`

Edits:

- keep `EMBEDDING_MODEL = text-embedding-v4` unchanged because it is already correct
- keep `EMBEDDING_DIMENSIONS = 1024` unchanged because it is already correct
- add `QWEN_TURBO_MODEL: str = _get("QWEN_TURBO_MODEL", "qwen-turbo")` if missing

Do not rewrite other model-selection logic.

### 7.3 `core/memory/embedding_client.py`

Expected status:

- no transport rewrite needed
- keep:
  - endpoint = `DASHSCOPE_COMPAT_BASE/embeddings`
  - `model = settings.EMBEDDING_MODEL`
  - `dimensions = settings.EMBEDDING_DIMENSIONS`
  - `encoding_format = "float"`

Only edit if dynamic settings usage or payload shape is found broken during implementation.

### 7.4 `core/memory/memory_store.py`

This is the main structural upgrade.

Required changes:

1. Add `initialize_all()`
   - create / migrate both durable tiers
   - rename legacy `memories` table to `long_term_memories` if needed
   - create `short_term_memories`
   - create indexes
   - call `purge_expired()` as part of startup path

2. Preserve `initialize()` as backward-compatible alias
   - it should call `initialize_all()` or otherwise keep old callers working

3. Extend `save_fact()`
   - signature becomes:
     - `save_fact(user_id, fact, embedding, tier="long", category="GENERAL") -> int`
   - tier rules:
     - `long`: update-or-insert via cosine > 0.92
     - `short`: insert with 7-day expiry and enforce per-user cap 100

4. Extend `recall_facts()`
   - signature becomes:
     - `recall_facts(user_id, query_embedding, top_k=3, tier="long") -> list[str]`
   - tier options:
     - `long`
     - `short`
     - `all`
   - `short` must ignore expired rows
   - `all` must deduplicate returned facts before truncating to `top_k`

5. Add `purge_expired() -> int`
   - delete expired rows from `short_term_memories`
   - return deleted count

6. Add long-term update behavior
   - select candidate rows by user
   - compute cosine similarity in Python as current code already does
   - when similarity > 0.92:
     - update `fact`, `embedding_json`, `category`, `updated_at`
     - return existing id

### 7.5 `core/memory/memory_manager.py`

Required changes:

1. Add `session_memory` property in `__init__`
   - `self.session_memory = SessionMemory()`

2. Add extractor dependency
   - constructor accepts `extractor`
   - `from_settings()` instantiates `Mem0Extractor.from_settings()`

3. Add `auto_extract_and_store(user_id, user_transcript, assistant_transcript)`
   - call extractor
   - embed each fact
   - save each fact with tier + category
   - swallow failures, log warnings, never raise

4. Add `recall_all_tiers(user_id, query, top_k=3) -> str | None`
   - embed query
   - fetch short + long tiers
   - compose via `compose_memory_context([], st, lt, [])`
   - return `None` if all empty

5. Preserve current `save()` / `recall()`
   - do not break existing callers
   - these may remain thin aliases to long-term / all-tier logic as appropriate

### 7.6 `core/memory/__init__.py`

Export:

- `SessionMemory`
- `Mem0Extractor`
- `compose_memory_context`

Do not remove existing exports.

### 7.7 `apps/backend/api/routes/realtime.py`

Make targeted additions only.

Required changes:

1. Imports
   - import `SessionMemory`
   - import `compose_memory_context`

2. Session init
   - after current `memory_manager` initialization, create:
     - `session_memory = SessionMemory()`
   - change startup init call from `memory_manager.store.initialize()` to a backward-compatible initializer that covers both tables (`initialize_all()` or alias via `initialize()`)

3. Expand `_is_memory_query()`
   - preserve current helper name
   - expand trigger coverage to the full English / Kannada / Hindi / generic past-tense list from this plan
   - the generic past-tense heuristic must be conservative and non-destructive

4. After `result = await client.async_send_audio_turn(...)`
   - derive `current_user_transcript`
   - fire-and-forget:
     - `asyncio.create_task(memory_manager.auto_extract_and_store(...))`
   - add current turn to `session_memory`

5. Replace manual same-turn recall trigger logic
   - use `is_memory_query(current_user_transcript)` rather than the current `_RECALL_PHRASES`-only pattern
   - query all relevant tiers and session data
   - compose context
   - run override turn using `make_silent_pcm(0.5)`
   - set `skip_classifier = True`

6. Preserve manual memory save alias behavior temporarily
   - keep old `remember that...` compatibility working if possible
   - but the new default path must not require any explicit save phrase

7. Heavy-vision result capture
   - when heavy vision succeeds, store a brief observation into session memory
   - also let auto-extraction convert durable facts from that exchange into short/long-term memory asynchronously

8. Disconnect cleanup
   - call `session_memory.clear()` on disconnect / final cleanup

Guardrails:

- do not change websocket message shapes
- do not change audio send/receive behavior
- do not change `pending_image_b64` lifecycle
- do not restructure the heavy-vision branch
- user id remains hardcoded `"default"`

### 7.8 `core/orchestrator/prompt_builder.py`

No functional change planned unless implementation discovers that `build_system_prompt()` cannot accept the planned composed memory context shape. Current audit shows it already can (`prompt_builder.py:23-37`).

### 7.9 Task-level QA map (must be executed task-by-task, not inferred)

This section closes the review gap from Momus: every implementation task below has an explicit QA scenario with tool, steps, and expected result.

#### Task QA — `core/memory/session_memory.py`

- Tool: `pytest`
- Steps:
  1. Run `test_session_memory_add_and_recall`
  2. Run `test_session_memory_objects_seen`
  3. Run `test_session_memory_ring_buffer_max`
- Expected result:
  - recent turns return in correct order
  - object list includes captured vision objects
  - ring buffer retains only max 20 turns

#### Task QA — `core/memory/mem0_extractor.py`

- Tool: `pytest`
- Steps:
  1. Run `test_mem0_extractor_returns_facts`
  2. Run `test_mem0_extractor_returns_empty_on_no_facts`
  3. Run `test_mem0_extractor_returns_empty_on_failure`
- Expected result:
  - extractor returns parsed fact dicts on mocked JSON
  - returns `[]` on empty extraction
  - returns `[]` on HTTP / parse failure without raising

#### Task QA — `core/memory/memory_context_composer.py`

- Tool: `pytest`
- Steps:
  1. Run `test_recall_all_tiers_returns_combined_context`
  2. Run `test_compose_memory_context_empty_inputs`
- Expected result:
  - combined context includes session, short, and long-term sections in order
  - empty inputs return exactly `""`

#### Task QA — `requirements.txt`

- Tool: Python import smoke
- Steps:
  1. Sync/install deps in the project venv
  2. Run `.venv/Scripts/python.exe -c "import mem0; print('mem0 import ok')"`
- Expected result:
  - `mem0` imports without error

#### Task QA — `shared/config/settings.py`

- Tool: Python import smoke
- Steps:
  1. Run `.venv/Scripts/python.exe -c "from shared.config import settings; print(settings.EMBEDDING_MODEL, settings.EMBEDDING_DIMENSIONS, getattr(settings, 'QWEN_TURBO_MODEL', None))"`
- Expected result:
  - outputs `text-embedding-v4`
  - outputs `1024`
  - outputs `qwen-turbo`

#### Task QA — `core/memory/embedding_client.py`

- Tool: `pytest`
- Steps:
  1. Re-run existing embedding tests in `tests/unit/test_memory.py`
- Expected result:
  - embedding client still calls compatible `/embeddings`
  - still enforces 1024-dim output
  - still uses `encoding_format="float"`

#### Task QA — `core/memory/memory_store.py`

- Tool: `pytest`
- Steps:
  1. Run `test_memory_store_short_term_save`
  2. Run `test_memory_store_long_term_dedup`
  3. Run `test_memory_store_purge_expired`
  4. Re-run existing `test_save_fact_calls_insert`, `test_recall_facts_returns_top_k`, and `test_recall_facts_returns_empty_when_no_facts`
- Expected result:
  - short-term facts land only in `short_term_memories`
  - long-term duplicate fact updates rather than double-inserts
  - expired short-term rows are purged
  - legacy save/recall behavior still passes unchanged for default tier

#### Task QA — `core/memory/memory_manager.py`

- Tool: `pytest`
- Steps:
  1. Run `test_memory_manager_auto_extract_stores_facts`
  2. Run `test_recall_all_tiers_returns_combined_context`
  3. Re-run existing `test_memory_manager_save_strips_prefix`, `test_memory_manager_recall_returns_context`, and `test_memory_manager_recall_returns_none_when_empty`
- Expected result:
  - auto extraction stores facts with correct tier/category
  - multi-tier recall returns composed context
  - old `save()` and `recall()` remain backward-compatible

#### Task QA — `core/memory/__init__.py`

- Tool: Python import smoke
- Steps:
  1. Run `.venv/Scripts/python.exe -c "from core.memory import SessionMemory, Mem0Extractor, compose_memory_context; print('memory exports ok')"`
- Expected result:
  - all new exports import successfully

#### Task QA — `apps/backend/api/routes/realtime.py`

- Tool: `pytest` + manual gates
- Steps:
  1. Add explicit route tests for session-memory clear, auto-extract background task launch, and multi-tier recall composition if implementation requires new assertions
  2. Re-run `tests/unit/test_realtime_route.py`
  3. Run manual gates 0-6 in this plan
- Expected result:
  - route still preserves pending image/instructions lifecycle
  - recall overrides use composed memory context
  - heavy-vision object observations are session-visible
  - disconnect clears session memory

#### Task QA — `core/orchestrator/prompt_builder.py`

- Tool: existing tests only if file changes
- Steps:
  1. Re-run `tests/unit/test_prompt_builder.py` only if implementation edits this file
- Expected result:
  - `build_system_prompt()` still composes memory/document context correctly

## 8. Test plan

### 8.1 Extend `tests/unit/test_memory.py`

Preserve all existing 8 tests.

Add the following tests, bringing the total to 20:

9. `test_session_memory_add_and_recall`
10. `test_session_memory_objects_seen`
11. `test_session_memory_ring_buffer_max`
12. `test_mem0_extractor_returns_facts`
13. `test_mem0_extractor_returns_empty_on_no_facts`
14. `test_mem0_extractor_returns_empty_on_failure`
15. `test_memory_store_short_term_save`
16. `test_memory_store_long_term_dedup`
17. `test_memory_store_purge_expired`
18. `test_memory_manager_auto_extract_stores_facts`
19. `test_recall_all_tiers_returns_combined_context`
20. `test_compose_memory_context_empty_inputs`

Testing rules:

- all use mocks
- zero real network calls
- zero persistent disk dependency beyond temp / mocked DB handles
- preserve old tests untouched

### 8.2 Extend `tests/unit/test_realtime_route.py`

Add route-level regressions only if required by implementation, with focus on:

- session memory cleared on disconnect
- auto extraction launched via `asyncio.create_task`
- recall override uses session + short + long-term context
- heavy-vision observations flow into session memory
- existing image/memory/interrupt behavior remains intact

### 8.3 Exact automated test commands

Run exactly:

```powershell
C:/ally-vision-v2/.venv/Scripts/pytest.exe tests/unit/test_memory.py -v --timeout=30 -x
C:/ally-vision-v2/.venv/Scripts/pytest.exe tests/unit/test_realtime_route.py -v --timeout=30 -x
C:/ally-vision-v2/.venv/Scripts/pytest.exe tests/unit/test_policy_router.py -v --timeout=30 -x
C:/ally-vision-v2/.venv/Scripts/pytest.exe tests/unit/test_intent_classifier.py -v --timeout=30 -x
C:/ally-vision-v2/.venv/Scripts/pytest.exe tests/unit/test_heavy_vision.py -v --timeout=30 -x
```

## 9. Manual gate checks

### Gate 0 — Backend starts clean

```powershell
.venv/Scripts/uvicorn.exe apps.backend.main:app --host 127.0.0.1 --port 8000 --reload
```

PASS:

- startup completes
- no ImportError
- health returns 200

### Gate 1 — Auto memory save with zero command

Say naturally:

- `My name is Om`

After a short delay, inspect SQLite:

```powershell
.venv/Scripts/python.exe -c "import sqlite3; c = sqlite3.connect('data/sqlite/memory.db'); rows = c.execute('SELECT fact, category FROM long_term_memories').fetchall(); [print(r) for r in rows]; c.close()"
```

PASS:

- a name fact appears in `long_term_memories`

### Gate 2 — Auto recall with natural past-tense speech

Say:

- `What is my name?`

PASS:

- Ally replies `Om` without any explicit memory command

### Gate 3 — Object-seen recall from session memory

Show an object.
Then ask:

- `What did I show you earlier?`

PASS:

- Ally recalls the recent object from session memory

### Gate 4 — Long-term persistence across restart

Restart backend, refresh browser, ask:

- `Do you remember my name?`

PASS:

- Ally still replies from persisted long-term memory

### Gate 5 — Correct tier routing

Say:

- `I am reading a medicine bottle right now`
- `My home city is Bengaluru`

Inspect DB:

- medicine-bottle observation should land in `short_term_memories`
- Bengaluru identity fact should land in `long_term_memories`

### Gate 6 — No duplicate on contradiction

Say:

- `My name is Om`
- `Actually my name is Omkar`

PASS:

- one long-term identity row remains after update/dedup

## 10. Non-goals

- Do not replace the current realtime route structure wholesale.
- Do not rework heavy vision or capture coach architecture.
- Do not make Mem0 OSS internals a hard runtime dependency for the core extraction path unless Python configuration details are re-proven.
- Do not remove backward compatibility for existing `MemoryManager.save()` / `recall()` callers.
- Do not change frontend contracts.
- Do not broaden this into unrelated reflection, web search, or document-QA work.

## 11. Implementation order for Hephaestus

1. Add dependency and settings constant
2. Create `SessionMemory`, `Mem0Extractor`, `memory_context_composer`
3. Expand `MemoryStore` schema and migration logic
4. Expand `MemoryManager`
5. Update exports in `core/memory/__init__.py`
6. Integrate targeted additions into `realtime.py`
7. Extend `test_memory.py`
8. Add route regressions only if needed
9. Run exact test files one by one
10. Run gates 0–6 in order

## 12. Quality self-check

Before implementation is claimed complete, verify all of the following:

- `EMBEDDING_MODEL = text-embedding-v4`
- realtime model remains `qwen3-omni-flash-realtime`
- heavy vision model remains `qwen3.6-plus`
- extraction model remains `qwen-turbo`
- no explicit save command required
- `_is_memory_query` covers English + Kannada + Hindi + generic past-tense
- session memory is in-memory only and cleared on disconnect
- short-term memory TTL is 7 days and purged on initialize path
- long-term memory uses cosine > 0.92 update behavior
- extraction runs under `asyncio.create_task`
- all memory tests are mock-based
- `realtime.py` changes remain targeted
- old `save()` and `recall()` still work
- existing Plan 07 tests still pass
- settings continue reading model IDs from env vars

## 13. Commit rule

If this plan file is committed, commit only:

```powershell
git add .sisyphus/plans/07b-auto-memory-mem0.md
git commit -m "plan: write plan 07b auto-memory — Mem0 qwen-turbo extraction, three-tier memory, text-embedding-v4, auto past-tense recall routing"
```

## 14. Stop rule

STOP. Say PLAN 07b PROMETHEUS COMPLETE. Wait for instruction.
