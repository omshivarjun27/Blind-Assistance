# Plan 08 — Web Search via DashScope-Compatible Chat Completions

## 0. Repo audit findings before planning (source of truth)

This section records the required file reads and exact line-number findings before any plan content.

### 0.1 Current project state

- Plans complete: `00–07b`
- Last code commit at planning time: `e7e3108` — Plan 07b auto-memory
- Current passing test state from latest execution:
  - `tests/unit/test_memory.py` → 20 passed
  - `tests/unit/test_realtime_route.py` → 30 passed
  - `tests/unit/test_policy_router.py` → 9 passed
  - `tests/unit/test_intent_classifier.py` → 8 passed
  - `tests/unit/test_heavy_vision.py` → 9 passed
  - `tests/unit/test_prompt_builder.py` → 10 passed

### 0.2 Locked environment config confirmed in repo

From `shared/config/settings.py`:

- `DASHSCOPE_HTTP_BASE` → lines `33-36`
- `DASHSCOPE_COMPAT_BASE` → lines `41-44`
- `QWEN_REALTIME_MODEL` → lines `47-50`
- `QWEN_VISION_MODEL` → lines `51-54`
- `QWEN_TRANSCRIPTION_MODEL` → line `55`
- `QWEN_TURBO_MODEL` → line `56`
- `EMBEDDING_MODEL` → line `59`
- `EMBEDDING_DIMENSIONS` → line `60`
- `APP_HOST` / `APP_PORT` / `DEBUG` → lines `67-70`

Repo-truth summary:

- realtime model = `qwen3-omni-flash-realtime`
- heavy vision model = `qwen3.6-plus`
- extraction/search model = `qwen-turbo`
- embeddings = `text-embedding-v4`, `1024`

### 0.3 Exact line-number findings for current WEB_SEARCH wiring

#### `core/orchestrator/policy_router.py`

- `RouteTarget.WEB_SEARCH` is defined at line `27`
- `_UNIMPLEMENTED` includes `RouteTarget.WEB_SEARCH` at lines `41-44`
- `IntentCategory.WEB_SEARCH` routes to `RouteTarget.WEB_SEARCH` at lines `63-67`
- `route()` falls unimplemented targets back to `REALTIME_CHAT` at lines `100-125`, specifically `107-118`
- module docstring is stale at lines `7-9`: it still says `MEMORY_WRITE` and `MEMORY_READ` are unimplemented, but `_UNIMPLEMENTED` now only contains `WEB_SEARCH` and `DOCUMENT_QA`

#### `core/orchestrator/intent_classifier.py`

- `WEB_SEARCH` is in `_LABELS` at line `27`
- classifier prompt includes `WEB_SEARCH` at lines `35-44`, specifically `37`
- `IntentCategory.WEB_SEARCH` is defined at line `51`

#### `apps/backend/api/routes/realtime.py`

- `_is_memory_query()` exists at lines `93-98`
- `_is_search_query()` is **absent** in current codebase
- route-local `make_silent_pcm()` exists at lines `171-174`
- current `_skip_classifier` guard points are at lines:
  - `476`
  - `486`
  - `489`
  - `535`
  - `538`
  - `541`
  - enqueue guard at `568`
- there is **no explicit WEB_SEARCH branch** in `realtime.py`
- current imports contain no search manager or search helper import; the route only imports `build_memory_fact` and `build_system_prompt` from prompt builder at lines `39-42`

#### Existing search-related stub/helper

- `core/orchestrator/prompt_builder.py` already contains `_SEARCH_PREFIXES` at lines `12-15`
- `build_search_query()` already exists at lines `40-46`
- this helper is currently unused by runtime wiring

#### Existing tests that lock current search behavior

- `tests/unit/test_policy_router.py:45-53`
  - currently asserts `WEB_SEARCH` falls back to `REALTIME_CHAT`
- `tests/unit/test_realtime_route.py`
  - does **not** contain any live WEB_SEARCH branch tests yet
  - already protects async classifier queueing, image lifecycle, and `_skip_classifier` behavior, so search wiring must preserve those contracts

#### Dependency / config findings

- `requirements.txt:1-13` has no dedicated search package; `httpx` is already present at line `4`
- `shared/config/settings.py:56` confirms `QWEN_TURBO_MODEL` is already present from Plan 07b

## 1. External doc verification (CONFIRMED vs UNCONFIRMED)

### 1.1 DashScope web search on compatible APIs

1. **Compatible Chat Completions endpoint**
   - **CONFIRMED**
   - Endpoint:
     - `POST https://dashscope-intl.aliyuncs.com/compatible-mode/v1/chat/completions`
   - Evidence:
     - Alibaba Cloud OpenAI-compatible chat docs
     - Alibaba Cloud web-search docs reference the same chat completions surface

2. **How to enable web search on Chat Completions**
   - **CONFIRMED**
   - Correct contract:
     - `enable_search: true`
   - Evidence:
     - Alibaba Cloud web-search docs explicitly show Chat Completions using `enable_search` (for SDKs this appears as `extra_body={"enable_search": True}`)

3. **`tools: [{"type": "web_search"}]` on Chat Completions**
   - **UNCONFIRMED / CONTRADICTED**
   - Evidence:
     - Alibaba docs place `tools: [{"type": "web_search"}]` on the **Responses API**, not on compatible Chat Completions
   - Planning consequence:
     - Do **not** write Plan 08 against a chat-completions `tools` contract
     - Use `enable_search: true` for the SearchManager request body

4. **Responses API supports `tools: [{"type": "web_search"}]`**
   - **CONFIRMED**
   - But out of scope for this plan because the project is locked to compatible chat completions for this feature

### 1.2 Response shape and citations

1. **Final answer text for Chat Completions**
   - **CONFIRMED**
   - Path:
     - `choices[0].message.content`

2. **Separate citations/sources in Chat Completions**
   - **UNCONFIRMED / NOT SUPPORTED ON COMPAT CHAT**
   - Evidence:
     - Alibaba web-search docs explicitly say the OpenAI-compatible protocol does **not** support returning search sources separately
   - Planning consequence:
     - Plan 08 should treat the final `message.content` as the spoken answer source
     - no source/citation parsing should be planned for compatible chat mode

3. **`tool_calls` block for built-in web search on Chat Completions**
   - **UNCONFIRMED / NOT DOCUMENTED**
   - Evidence:
     - Alibaba compatibility docs say `tools` on chat currently refer to function tools; built-in `web_search` is documented under Responses instead
   - Planning consequence:
     - do not design SearchManager around `tool_calls`

### 1.3 Model support risk

1. **`qwen-turbo` as a general compatible chat model**
   - **CONFIRMED**

2. **`qwen-turbo` specifically documented as web-search-enabled**
   - **UNCONFIRMED**
   - Evidence:
     - Alibaba web-search docs list search-enabled models such as `qwen3.5-plus`, `qwen3.5-flash`, and `qwen3-max`, but did not explicitly list `qwen-turbo`
   - Planning consequence:
     - keep `qwen-turbo` as the locked project model ID
     - add a mandatory preflight live smoke before route wiring
     - if provider rejects `qwen-turbo` + `enable_search`, stop and report exact error rather than silently switching models

### 1.4 Latency / resilience notes

- Search-enabled calls are slower than classification/embedding calls
- This supports using a longer timeout (`15s`) for SearchManager
- SearchManager must never raise; it should return a fallback string on timeout or provider failure

## 2. Goal

Add a live web-search capability so Ally can answer questions that require current real-world information — scores, prices, weather, news, opening hours, trending events — using the existing `WEB_SEARCH` intent and a dedicated `SearchManager` execution path.

This plan wires the feature end-to-end while preserving:

- the current realtime route structure
- current memory and heavy-vision behavior
- classifier lookahead behavior
- `pending_image_b64` lifecycle
- current websocket message shapes

## 3. High-level design

### 3.1 Search execution model

Use a **same-turn override** after the user transcript is known, following the same pattern already used for memory save/recall:

1. browser sends audio turn
2. realtime client returns assistant audio + `result.user_transcript`
3. route detects current-turn search intent via `_is_search_query(current_user_transcript)`
4. route calls `search_manager.search(current_user_transcript)`
5. route injects the grounded search answer into a second silent Omni turn using `make_silent_pcm(0.5)`
6. route sets `skip_classifier = True`

This avoids fighting the current previous-turn classifier design and keeps Plan 08 consistent with the repo’s established override pattern.

### 3.2 Preflight risk gate

Because `qwen-turbo` search support is not externally re-proven, Plan 08 must start with a runtime smoke test **before** wiring the route:

- call compatible `/chat/completions`
- set `enable_search: true`
- use model `qwen-turbo`
- ask a clearly current question such as latest cricket score or today’s weather

If the provider rejects `enable_search` or rejects `qwen-turbo` for search, stop and report the exact provider error. Do **not** silently swap models.

## 4. Files to create

### 4.1 `core/search/__init__.py` (update if present, create if missing)

Export:

- `SearchManager`
- `SearchError`

### 4.2 `core/search/search_manager.py`

Create a small, isolated search wrapper.

Classes:

- `SearchError(Exception)` for internal signalling if desired
- `SearchManager`

Contract:

- `__init__(self, api_key: str, base_url: str, model: str)`
- `@classmethod from_settings(cls) -> "SearchManager"`
  - reads:
    - `settings.get_api_key()`
    - `settings.DASHSCOPE_COMPAT_BASE`
    - `settings.QWEN_TURBO_MODEL`
- `async search(self, query: str) -> str`

HTTP contract:

- method: `POST`
- URL: `{base_url}/chat/completions`
- headers:
  - `Authorization: Bearer {api_key}`
  - `Content-Type: application/json`
- JSON body:
  - `model: self.model`
  - `messages: [{"role": "user", "content": query}]`
  - `enable_search: true`
- timeout: `httpx.AsyncClient(timeout=15.0)`

Response parsing:

- happy path: `response["choices"][0]["message"]["content"]`
- on any HTTP/timeout/JSON failure:
  - return exactly:
    - `I was unable to search for that right now.`
- never raise externally

### 4.3 `tests/unit/test_search.py`

All tests mock `httpx.AsyncClient`; zero real network calls.

Tests to add:

1. `test_search_returns_answer`
2. `test_search_returns_fallback_on_http_error`
3. `test_search_returns_fallback_on_timeout`
4. `test_search_sends_enable_search_flag`
5. `test_search_from_settings_uses_correct_model`

Note: this is a small correction from the prompt — since docs prove chat-completions search uses `enable_search`, the body assertion must verify `enable_search: true`, not `tools: [{"type": "web_search"}]`.

## 5. Files to edit

### 5.1 `core/orchestrator/policy_router.py`

Required changes:

1. Remove `RouteTarget.WEB_SEARCH` from `_UNIMPLEMENTED`
2. Leave `RouteTarget.DOCUMENT_QA` in `_UNIMPLEMENTED`
3. Update the stale module docstring so it no longer claims `MEMORY_WRITE` / `MEMORY_READ` are unimplemented

Expected result:

- `IntentCategory.WEB_SEARCH` routes cleanly to `RouteTarget.WEB_SEARCH`
- no fallback logging for search

### 5.2 `apps/backend/api/routes/realtime.py`

Targeted additions only.

Add imports:

- `from core.search import SearchManager`

Session init:

- create `search_manager = SearchManager.from_settings()` alongside the existing `memory_manager`

Add helper near `_is_memory_query()`:

- `_SEARCH_TRIGGERS = (...)`
- `_is_search_query(transcript: str) -> bool`

Suggested trigger coverage:

- `search for`
- `look up`
- `find out`
- `what is the latest`
- `latest news`
- `current price`
- `today's`
- `news about`
- `who won`
- `what happened`
- `how much does`
- `is it open`
- `weather`
- `score`
- `trending`
- `right now`
- `currently`
- `live score`

Same-turn search override block:

- place **after** the same-turn memory recall override block
- place **before** the default fallthrough that leaves `result` unchanged
- shape:

```python
elif _is_search_query(current_user_transcript):
    search_answer = await search_manager.search(current_user_transcript)
    override_result = await client.async_send_audio_turn(
        audio_pcm=make_silent_pcm(0.5),
        instructions=(
            "Tell the user this search result naturally and conversationally, "
            f"without adding facts that are not present: {search_answer}"
        ),
    )
    override_result.user_transcript = current_user_transcript
    result = override_result
    _skip_classifier = True
```

Guardrails:

- do not modify `_is_memory_query`
- do not restructure heavy-vision or memory blocks
- do not change `pending_image_b64` lifecycle
- do not change websocket transcript/audio shapes
- do not change previous-turn classifier queueing

### 5.3 `shared/config/settings.py`

Verify only.

- `QWEN_TURBO_MODEL` is already present at line `56`
- no edit required unless missing during implementation

### 5.4 `tests/unit/test_policy_router.py`

Update the current fallback assertion:

- replace `test_web_search_falls_back_to_realtime_in_plan05`
- with a search-implemented assertion such as:
  - `decision.target == RouteTarget.WEB_SEARCH`

Keep all other existing router tests intact.

### 5.5 `tests/unit/test_realtime_route.py`

Add route-level search regressions with full mocks.

Minimum new tests:

1. `test_web_search_same_turn_calls_search_manager`
   - patch `SearchManager.from_settings()`
   - simulate current-turn transcript recognized as search query
   - assert `search_manager.search(current_user_transcript)` is awaited

2. `test_web_search_override_uses_silent_turn`
   - assert override sends `make_silent_pcm(0.5)` to `client.async_send_audio_turn`

3. `test_web_search_sets_skip_classifier`
   - ensure search override does not enqueue the same utterance again for next-turn classification

4. `test_web_search_fallback_message_spoken_on_search_failure`
   - mock `search_manager.search` to return fallback string
   - assert assistant is instructed to speak that fallback instead of crashing

These tests must preserve all existing route tests unchanged.

## 6. Preflight implementation step (must happen before route wiring)

Before editing `policy_router.py` or `realtime.py`, implementation must run a direct DashScope-compatible smoke for search:

```powershell
C:/ally-vision-v2/.venv/Scripts/python.exe -c "... qwen-turbo + enable_search ..."
```

Success criteria:

- HTTP 200
- no provider error on `enable_search`
- non-empty `choices[0].message.content`

Failure rule:

- stop immediately
- report exact provider error
- do not silently replace `qwen-turbo`

## 7. Exact automated test commands

Run exactly:

```powershell
C:/ally-vision-v2/.venv/Scripts/pytest.exe tests/unit/test_search.py -v --timeout=30 -x
C:/ally-vision-v2/.venv/Scripts/pytest.exe tests/unit/test_realtime_route.py -v --timeout=30 -x
C:/ally-vision-v2/.venv/Scripts/pytest.exe tests/unit/test_policy_router.py -v --timeout=30 -x
C:/ally-vision-v2/.venv/Scripts/pytest.exe tests/unit/test_intent_classifier.py -v --timeout=30 -x
```

## 8. Manual gate checks

### Gate 1 — Live search spoken answer

Ask:

- `Search for the latest cricket score`

PASS:

- Ally speaks a grounded result rather than generic fallback

### Gate 2 — Current-information query

Ask:

- `What is the weather like in Bengaluru today?`

PASS:

- Ally speaks a search-grounded current answer

### Gate 3 — Graceful fallback

Temporarily block outbound HTTP, then ask a search query.

PASS:

- Ally says exactly:
  - `I was unable to search for that right now.`
- no backend crash or hang

## 9. Quality self-check

Before implementation is claimed complete, verify:

- SearchManager never raises; always returns `str`
- search model remains `qwen-turbo`
- compatible chat-completions uses `enable_search: true`
- do **not** use `tools: [{"type": "web_search"}]` on chat completions
- timeout is `15s`
- `WEB_SEARCH` removed from `_UNIMPLEMENTED`
- `DOCUMENT_QA` remains in `_UNIMPLEMENTED`
- `realtime.py` changes are targeted only
- new route block sets `_skip_classifier = True`
- `_is_search_query` does not interfere with `_is_memory_query`
- no new dependency beyond existing `httpx`
- `core/search/__init__.py` exports `SearchManager`
- all search tests are mocked

## 10. Commit rule

Commit only the plan file:

```powershell
git add .sisyphus/plans/08-web-search.md
git commit -m "plan: write plan 08 web search — SearchManager qwen-turbo, compat chat enable_search, WEB_SEARCH route wiring, mocked tests, physical gates"
```

## 11. Stop rule

STOP. Say PLAN 08 PROMETHEUS COMPLETE. Wait for instruction.
