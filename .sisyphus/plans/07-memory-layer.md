# Plan 07 — Memory Layer

## Section 1 — Context (what is true now)

Plans complete:
  00 — master plan
  01 — scaffold + settings
  02 — DashScope realtime client
  03 — FastAPI WebSocket route
  04 — browser camera + mic capture
  05 — orchestrator + intent classifier + policy router
  06 — heavy vision path
  06b — reconciliation + regression hardening

Last commit: `a31b3e2 feat(plan06b): reconciliation + regression hardening`

What is passing right now:
  `tests/unit/test_intent_classifier.py`   → 8 passed / 0 failed
  `tests/unit/test_policy_router.py`       → 7 passed / 0 failed
  `tests/unit/test_realtime_route.py`      → 15 passed / 0 failed
  `tests/unit/test_heavy_vision.py`        → 9 passed / 0 failed

What is live:
  - `TRANSLATE`, `SCENE_DESCRIBE`, `READ_TEXT`, `SCAN_PAGE` → fully routed
  - `MEMORY_SAVE`, `MEMORY_RECALL` currently fall back to `REALTIME_CHAT`
    because `policy_router.py` still keeps `MEMORY_WRITE` and `MEMORY_READ`
    inside `_UNIMPLEMENTED`
  - No SQLite memory layer exists yet
  - No embedding client exists yet
  - `core/memory/` exists but is empty

Critical design correction for Plan 07:
  The current orchestrator classifies **previous-turn** transcripts because
  `result.user_transcript` only exists after `client.async_send_audio_turn(...)`
  returns. If Plan 07 were implemented exactly as the stale draft suggests,
  `MEMORY_SAVE` / `MEMORY_RECALL` would execute one turn late and fail the live
  gate checks.

  Therefore Plan 07 must support **same-turn memory behavior** by:
  1. sending the current audio turn to Omni as usual,
  2. reading `result.user_transcript` from that same turn,
  3. performing memory save/recall immediately,
  4. replacing the generic assistant reply with a second short silent-audio
     Omni turn carrying the final confirmation / recall answer.

  This keeps the current browser contract intact and avoids introducing a new
  frontend text channel just for memory.

What Plan 07 must deliver:
  - SQLite memory store: create, store fact, retrieve by similarity
  - DashScope `text-embedding-v3` client
  - Wire `MEMORY_SAVE` → save fact + embedding to SQLite
  - Wire `MEMORY_RECALL` → embed query → cosine similarity → retrieve
  - Inject retrieved memory context into the system prompt before the final
    spoken answer is generated
  - Remove `MEMORY_WRITE` and `MEMORY_READ` from `_UNIMPLEMENTED`
  - Add explicit tests proving same-turn memory save/recall behavior

## Section 2 — Step 1: Read Before Planning

Files read completely:
  - `C:/ally-vision-v2/shared/config/settings.py`
  - `C:/ally-vision-v2/core/orchestrator/policy_router.py`
  - `C:/ally-vision-v2/core/orchestrator/prompt_builder.py`
  - `C:/ally-vision-v2/apps/backend/api/routes/realtime.py`
  - `C:/ally-vision-v2/core/memory/__init__.py`
  - `C:/ally-vision-v2/tests/unit/test_realtime_route.py`
  - `C:/ally-vision-v2/requirements.txt`

Symbol and repo findings with exact line numbers:

### `shared/config/settings.py`
- Embedding config already exists:
  - `57`: `EMBEDDING_MODEL = "text-embedding-v3"`
  - `58`: `EMBEDDING_DIMENSIONS = 1024`
  - `59`: `EMBEDDING_OUTPUT_TYPE = "dense"`
- No `MEMORY_DB_PATH` exists yet.

### `core/orchestrator/policy_router.py`
- `_UNIMPLEMENTED` definition starts at:
  - `41`: `_UNIMPLEMENTED = {`
- Current unimplemented route targets are:
  - `42`: `RouteTarget.WEB_SEARCH`
  - `43`: `RouteTarget.MEMORY_WRITE`
  - `44`: `RouteTarget.MEMORY_READ`
  - `45`: `RouteTarget.DOCUMENT_QA`
- `MEMORY_SAVE` routing table entry:
  - `70-74`: routes to `RouteTarget.MEMORY_WRITE`
- `MEMORY_RECALL` routing table entry:
  - `75-79`: routes to `RouteTarget.MEMORY_READ`

### `core/orchestrator/prompt_builder.py`
- `build_system_prompt` exact signature:
  - `23-27`: `build_system_prompt(base_instructions: str, memory_context: str = "", document_context: str = "")`
- Memory-context injection already exists at:
  - `33-34`: `Relevant memory:\n{memory_context.strip()}`
- Memory prefix stripping already exists at:
  - `17-20`: `_MEMORY_PREFIXES = re.compile(...)`
  - `49-55`: `build_memory_fact(transcript: str) -> str`

### `apps/backend/api/routes/realtime.py`
- `MEMORY_SAVE` search result:
  - **No matches found**
- `MEMORY_RECALL` search result:
  - **No matches found**
- `pending_image_b64` exact locations:
  - `99`: declaration
  - `161-163`: first-turn image fallback to `SCENE_DESCRIBE`
  - `176`: consumed into `vision_image_b64`
  - `221`: frame-required fallback branch
  - `242`: passed to `client.async_send_audio_turn(...)`
  - `249`: copied to `turn_image_b64`
  - `266`: reset to `None`
  - `325-327`: assigned from `{"type":"image"}` control message
- `effective_instructions` exact locations:
  - `120`: initial assignment from `pending_instructions`
  - `179`: capture-coach guidance
  - `199`: heavy-vision success response
  - `208`: heavy-vision error response
  - `217`: missing-image guidance
  - `225`: generic frame-required guidance
  - `230`: routing decision system instructions
  - `243`: passed into `client.async_send_audio_turn(...)`

Critical realtime-route behavior relevant to Plan 07:
- Current route logic determines intent from **previous-turn** classifier state:
  - `118-120`: comment and setup
  - `126-154`: pending classification task result consumption
  - `251-263`: new classification task queued after current turn returns
- Because of that timing, memory cannot be same-turn if it only uses the current
  previous-turn routing architecture.

### `core/memory/__init__.py`
- `1`: file contains only `# Ally Vision v2`

### `tests/unit/test_realtime_route.py`
- Existing route tests already cover:
  - `190-225`: first-turn image fallback to `SCENE_DESCRIBE`
  - `328-369`: non-blocking classifier behavior
- No memory-route coverage exists yet.

### `requirements.txt`
- `7`: `aiosqlite` is already declared
- `numpy` is **not** declared in repo requirements

Additional environment finding:
- Active venv currently has `numpy 2.4.4` installed, but this is not a committed
  dependency contract because `requirements.txt` does not declare it.

## Section 3 — Step 2: Verify Docs

### 1) DashScope `text-embedding-v3`

Compatible-mode endpoint URL:
- **CONFIRMED**: `POST https://dashscope-intl.aliyuncs.com/compatible-mode/v1/embeddings`

Model name:
- **CONFIRMED**: `text-embedding-v3`

Default dimension:
- **CONFIRMED**: `1024`

`dense` output type parameter:
- **CONFIRMED (native API only)**: native DashScope embedding docs explicitly document `output_type: "dense"`
- **UNCONFIRMED (compatible mode)**: compatible-mode examples show `dimensions` and `encoding_format: "float"`, not `output_type`

Compatible-mode request body shape:
- **CONFIRMED**:
  - `model`
  - `input` (string or list of strings)
  - optional `dimensions`
  - optional `encoding_format: "float"`

Response format:
- **CONFIRMED**: `data[0].embedding` is a list of floats

Plan decision from docs:
- Use the **compatible-mode** embeddings endpoint
- Send `model`, `input`, `dimensions`, and `encoding_format="float"`
- Do **not** send `output_type` on the compatible endpoint in Plan 07
- Treat dense float embedding as the compatible-mode default behavior

### 2) aiosqlite

`async with aiosqlite.connect(path) as db` pattern:
- **CONFIRMED**

`execute()` and `fetchall()` awaitability:
- **CONFIRMED**: cursor-level `execute()` and `fetchall()` are awaitable / async methods

### 3) Cosine similarity

Formula:
- **CONFIRMED**: `similarity = np.dot(a, b) / (norm(a) * norm(b))`

No external vector DB needed for `< 10,000` memories:
- **UNCONFIRMED by docs**
- **Applied engineering decision** for Plan 07: a Python-side brute-force cosine scan over a small SQLite table is sufficient for this project scale and avoids premature vector DB complexity

Additional dependency correction:
- Because repo requirements do not declare `numpy`, Plan 07 must add it explicitly to committed requirements if cosine similarity is implemented with NumPy.

## Section 4 — Plan Requirements

### A) Goal
Add a persistent SQLite memory layer so Ally can store
and retrieve user facts across turns using
`text-embedding-v3` semantic similarity search.

Critical implementation correction:
Plan 07 must support **same-turn** memory save/recall despite the current
previous-turn classifier architecture. The route must use the current turn’s
`result.user_transcript` immediately after the first Omni call returns, then
perform save/recall and replace the generic reply with a second short silent-audio
Omni turn that speaks the final memory-aware answer.

### B) FILES TO CREATE

1. `core/memory/embedding_client.py`
   - Class: `EmbeddingClient`
   - Method: `async embed(text: str) -> list[float]`
     - POST to DashScope compatible-mode embeddings endpoint
     - endpoint: `{settings.DASHSCOPE_COMPAT_BASE}/embeddings`
     - model: `settings.EMBEDDING_MODEL` (default `text-embedding-v3`)
     - dimensions: `settings.EMBEDDING_DIMENSIONS` (default `1024`)
     - request body fields:
       - `model`
       - `input` (single string)
       - `dimensions`
       - `encoding_format: "float"`
     - parse `response["data"][0]["embedding"]`
     - validate length equals configured dimensions
     - returns `list[float]`
     - raises `EmbeddingError` on failure (never silently returns empty)
   - Class: `EmbeddingError(Exception)`
   - Uses `settings.get_api_key()`, `settings.DASHSCOPE_COMPAT_BASE`,
     `settings.EMBEDDING_MODEL`, `settings.EMBEDDING_DIMENSIONS`
   - `httpx.AsyncClient` timeout: `10s`
   - `from_settings()` classmethod

   Important correction vs stale draft:
   - Compatible-mode docs explicitly show `encoding_format="float"`
   - Plan 07 does **not** send `output_type="dense"` on the compatible endpoint

2. `core/memory/memory_store.py`
   - Class: `MemoryStore`
   - DB path: `settings.MEMORY_DB_PATH`
   - async `initialize() -> None`
     - Creates table if not exists:
       `memories(`
         `id INTEGER PRIMARY KEY AUTOINCREMENT,`
         `user_id TEXT NOT NULL,`
         `fact TEXT NOT NULL,`
         `embedding_json TEXT NOT NULL,`
         `created_at TEXT NOT NULL`
       `)`
     - Index: `memories_user_id` on `(user_id)`
   - async `save_fact(user_id: str, fact: str, embedding: list[float]) -> int`
     - serialize embedding with `json.dumps(embedding)`
     - `INSERT` into `memories`
     - return `lastrowid`
   - async `recall_facts(user_id: str, query_embedding: list[float], top_k: int = 3) -> list[str]`
     - `SELECT fact, embedding_json FROM memories WHERE user_id = ?`
     - `json.loads()` each embedding
     - compute cosine similarity with NumPy
     - sort descending by similarity
     - return top_k facts
     - return `[]` if no facts stored
   - `from_settings()` classmethod

   Storage format decision:
   - Use `TEXT` column for serialized JSON, not raw `BLOB`
   - This is simpler, inspectable, and matches the “JSON blob / no raw binary” intent safely

3. `core/memory/memory_manager.py`
   - Class: `MemoryManager`
   - Composes `EmbeddingClient` + `MemoryStore`
   - Properties:
     - `embedder`
     - `store`
   - async `save(user_id: str, raw_utterance: str) -> str`
     - strip memory-save prefix using `prompt_builder.build_memory_fact(raw_utterance)`
     - call `EmbeddingClient.embed(cleaned_fact)`
     - call `MemoryStore.save_fact(user_id, cleaned_fact, embedding)`
     - return `cleaned_fact`
   - async `recall(user_id: str, query: str, top_k: int = 3) -> str | None`
     - call `EmbeddingClient.embed(query)`
     - call `MemoryStore.recall_facts(user_id, embedding, top_k)`
     - if results empty: return `None`
     - else return newline-joined facts string
   - `from_settings()` classmethod

4. `core/memory/__init__.py` (UPDATE — currently empty)
   - Export:
     - `MemoryManager`
     - `MemoryStore`
     - `EmbeddingClient`
     - `EmbeddingError`

5. `tests/unit/test_memory.py`
   - Unit tests — see section F below

### C) FILES TO EDIT

1. `requirements.txt`
   - ADD: `numpy`
   - Reason:
     - current venv has NumPy, but repo requirements do not declare it
     - Plan 07 uses NumPy for cosine similarity
     - this removes the hidden venv-only dependency

2. `shared/config/settings.py`
   - ADD:
     - `MEMORY_DB_PATH: str` — default `"data/sqlite/memory.db"`
   - Read from env var `MEMORY_DB_PATH`
   - Ensure parent directory is created on settings load:
     - `pathlib.Path(MEMORY_DB_PATH).parent.mkdir(parents=True, exist_ok=True)`

3. `core/orchestrator/policy_router.py`
   - REMOVE from `_UNIMPLEMENTED`:
     - `RouteTarget.MEMORY_WRITE`
     - `RouteTarget.MEMORY_READ`
   - After this change, `route(IntentCategory.MEMORY_SAVE)` returns `MEMORY_WRITE`
     and `route(IntentCategory.MEMORY_RECALL)` returns `MEMORY_READ` without fallback logging

4. `apps/backend/api/routes/realtime.py`
   - ADD at session init (same scope as classifier / mm_client):
     - `memory_manager = MemoryManager.from_settings()`
     - `await memory_manager.store.initialize()`

   - Preserve the existing previous-turn classifier architecture for other intents.

   - ADD **same-turn memory override** after the first upstream Omni turn returns,
     and before any audio/transcript is sent back to the browser:

     Exact pattern:
     1. Keep the current first call:
        - `result = await client.async_send_audio_turn(...)`
     2. Set:
        - `current_user_transcript = result.user_transcript or ""`
     3. Detect same-turn memory intent from `current_user_transcript`:
        - MEMORY_SAVE if `build_memory_fact(current_user_transcript)` removes a leading memory-save phrase
        - MEMORY_RECALL if transcript starts with recall phrases like:
          - `what did i tell you`
          - `do you remember`
          - `recall`
          - `what is my`
     4. If same-turn MEMORY_SAVE:
        - `confirmed_fact = await memory_manager.save(user_id="default", raw_utterance=current_user_transcript)`
        - `override_result = await client.async_send_audio_turn(`
             `audio_pcm=make_silent_pcm(0.5),`
             `instructions=f"Tell the user: I will remember that {confirmed_fact}."`
          `)`
        - Replace assistant-side outputs with `override_result`
        - Preserve `current_user_transcript` as the user transcript emitted back to browser
        - Do **not** queue a classifier task for this transcript afterward (avoid one-turn-late duplicate memory save)
     5. If same-turn MEMORY_RECALL:
        - `memory_context = await memory_manager.recall(user_id="default", query=current_user_transcript, top_k=3)`
        - If memory exists:
          - `recall_instructions = build_system_prompt(`
                `base_instructions=(`
                  `f"The user asked: {current_user_transcript}\n"`
                  `"Answer using only the relevant stored memory. Be brief."`
                `),`
                `memory_context=memory_context,`
            `)`
        - Else:
          - `recall_instructions = "Tell the user: I don't have anything stored about that yet."`
        - `override_result = await client.async_send_audio_turn(`
             `audio_pcm=make_silent_pcm(0.5),`
             `instructions=recall_instructions`
          `)`
        - Replace assistant-side outputs with `override_result`
        - Preserve `current_user_transcript` as the user transcript emitted back to browser
        - Do **not** queue a classifier task for this transcript afterward
     6. If not a same-turn memory intent:
        - keep current classifier-queue behavior exactly as it is

   - Important structural guardrail:
     - Do not rewrite the whole route.
     - Keep existing HEAVY_VISION / frame / error handling intact.
     - Add the memory manager at session scope and the same-turn memory override block after the first turn result and before websocket send-back.

   - Note: `user_id` remains hardcoded to `"default"` for Plan 07.

5. `core/orchestrator/prompt_builder.py`
   - **Expected outcome: no edit needed**
   - Reuse existing:
     - `build_system_prompt(...)`
     - `build_memory_fact(...)`
   - Edit only if the current helper signatures change unexpectedly during implementation

6. `tests/unit/test_policy_router.py`
   - ADD:
     - `test_memory_write_is_implemented()`
       - assert `route(IntentCategory.MEMORY_SAVE).target == RouteTarget.MEMORY_WRITE`
     - `test_memory_recall_is_implemented()`
       - assert `route(IntentCategory.MEMORY_RECALL).target == RouteTarget.MEMORY_READ`

7. `tests/unit/test_realtime_route.py`
   - ADD:
     - `test_memory_write_same_turn_confirmation()`
       - mock memory manager save
       - mock second silent override Omni turn
       - assert final assistant response says memory was saved
     - `test_memory_recall_same_turn_injects_memory_context()`
       - mock memory manager recall returning known facts
       - assert second override turn receives memory-aware instructions built from `build_system_prompt(...)`

### D) FILES TO DELETE
None

### E) SAFE DELETION RULES
N/A

### F) TESTS TO WRITE — `tests/unit/test_memory.py`

Use `unittest.mock` and `pytest-asyncio` throughout.
Mock `httpx.AsyncClient` for all DashScope calls.
Mock `aiosqlite.connect` for all DB calls.
Never hit real network or real filesystem in unit tests.

`test_embed_returns_list_of_floats()`
  - Mock HTTP response:
    - `{ "data": [{ "embedding": [0.1] * 1024 }] }`
  - Call `EmbeddingClient.embed("hello")`
  - Assert result is list of length 1024
  - Assert all elements are float

`test_embed_raises_on_error()`
  - Mock HTTP 400 / exception
  - Assert `EmbeddingError` is raised

`test_save_fact_calls_insert()`
  - Mock `aiosqlite.connect`
  - Call `MemoryStore.save_fact("u1", "my name is Om", [0.1] * 1024)`
  - Assert `execute()` called with INSERT
  - Assert `"my name is Om"` appears in args

`test_recall_facts_returns_top_k()`
  - Mock DB rows:
    - fact A with embedding aligned to query
    - fact B orthogonal
    - fact C intermediate
  - Query embedding aligned with fact A
  - Assert fact A is ranked first
  - Assert `top_k=2` returns 2 results

`test_recall_facts_returns_empty_when_no_facts()`
  - Mock DB returns 0 rows
  - Assert result is `[]`

`test_memory_manager_save_strips_prefix()`
  - Mock embedder and store
  - Call `MemoryManager.save("u1", "remember that my doctor is Dr. Sharma")`
  - Assert saved fact is `"my doctor is Dr. Sharma"`

`test_memory_manager_recall_returns_context()`
  - Mock embedder
  - Mock store recall result:
    - `["my doctor is Dr. Sharma", "my city is Bengaluru"]`
  - Call `MemoryManager.recall("u1", "who is my doctor")`
  - Assert returned string contains `Dr. Sharma`

`test_memory_manager_recall_returns_none_when_empty()`
  - Mock store recall result `[]`
  - Assert `MemoryManager.recall(...) is None`

### G) TESTS TO RUN (exact commands)
`C:/ally-vision-v2/.venv/Scripts/pytest.exe tests/unit/test_memory.py -v --timeout=30 -x`

`C:/ally-vision-v2/.venv/Scripts/pytest.exe tests/unit/test_realtime_route.py -v --timeout=30 -x`

`C:/ally-vision-v2/.venv/Scripts/pytest.exe tests/unit/test_policy_router.py -v --timeout=30 -x`

### H) GATE CHECKS

GATE 1 — Memory save live:
  Start backend.
  Open browser, speak: "Remember that my name is Om."
  Ally must respond: "I will remember that my name is Om."
  NOT a generic reply.
  PASS = confirmation spoken
  FAIL = generic response or error

GATE 2 — Memory recall live:
  In same session (or new session after db persists):
  Speak: "What is my name?"
  Ally must respond with "Om" using stored memory.
  PASS = correct name spoken
  FAIL = "I don't know" or no memory injected

GATE 3 — DB file created:
  After GATE 1:
  Check `C:/ally-vision-v2/data/sqlite/memory.db` exists
  Open with sqlite3 CLI:
    `sqlite3 data/sqlite/memory.db`
    `SELECT fact FROM memories;`
  Must show: `my name is Om`
  PASS = row visible in DB
  FAIL = file missing or table empty

## Section 5 — Quality Self-Check
Before committing the plan file, verify:
  □ EmbeddingClient never silently returns empty list
  □ MemoryStore uses `aiosqlite` (async) — never `sqlite3` (sync)
  □ Embedding serialized as JSON text — not raw binary
  □ Cosine similarity uses NumPy — and `numpy` is declared explicitly in `requirements.txt`
  □ `user_id` hardcoded `"default"` — noted, not a bug for Plan 07
  □ memory_manager initialized at session scope, not per-turn
  □ `MEMORY_WRITE` and `MEMORY_READ` removed from `_UNIMPLEMENTED`
  □ realtime.py preserves existing structure and adds only session init + same-turn memory override + targeted route tests
  □ `MEMORY_DB_PATH` parent directory created on settings load
  □ All 8 unit tests in `test_memory.py` use mocks — zero real network or disk I/O
  □ Gate checks are binary PASS/FAIL, runnable in < 5 minutes
  □ No always-on background processing introduced
  □ `aiosqlite` already in `requirements.txt` (confirmed in Step 1)
  □ No hidden venv-only dependency remains for NumPy

## Section 6 — Commit Rule
Commit ONLY the plan file:

```bash
git add .sisyphus/plans/07-memory-layer.md
git commit -m "plan: write plan 07 memory layer

EmbeddingClient: text-embedding-v3 1024-dim dense via DashScope
MemoryStore: aiosqlite facts table + cosine similarity recall
MemoryManager: save + recall with prefix stripping
realtime.py: MEMORY_WRITE and MEMORY_RECALL branches wired
policy_router.py: remove MEMORY_WRITE/READ from UNIMPLEMENTED
settings.py: MEMORY_DB_PATH added
8 unit tests in test_memory.py
3 physical gate checks"
```

## Section 7 — Stop Rule
STOP. Say `PLAN 07 PROMETHEUS COMPLETE`
Wait for instruction.
