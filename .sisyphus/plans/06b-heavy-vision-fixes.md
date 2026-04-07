# Plan 06b — Heavy Vision Fixes

## Section 1 — Context (what is true now)

Plans complete:
  00 — master plan
  01 — scaffold + settings
  02 — DashScope realtime client
  03 — FastAPI WebSocket route
  04 — browser camera + frame capture
  05 — orchestrator + intent classifier + policy router
  06 — heavy vision path (Hephaestus executed)

Last commit: `d2fd94a2d5ded01e702af61bc386df9f5ccb8451`
Plan 06 Prometheus commit: `d2fd94a`

What is working after Plan 06 Hephaestus execution:
  - `multimodal_client.py` exists and implements `VisionRequest`, `VisionResponse`, and `MultimodalClient.analyze()`
  - `capture_coach.py` exists and provides pixel-based frame quality gating
  - `live_scene_reader.py` exists
  - `page_reader.py` exists
  - `realtime.py` contains a HEAVY_VISION branch
  - `framing_judge.py` exists and is intentionally not wired yet
  - `tests/unit/test_heavy_vision.py` passes

Critical stale-brief reconciliation:
The user-provided 06b post-mortem is **partially stale** relative to the actual repo.

Already landed in code now:
  - `TRANSLATE` intent already exists in `intent_classifier.py`
  - `TRANSLATE` routing already exists in `policy_router.py`
  - first-turn image fallback to `SCENE_DESCRIBE` already exists in `realtime.py`
  - async non-blocking classification via `_asyncio.create_task(...)` already exists in `realtime.py`
  - `mm_client` is already instantiated once per WebSocket session in `realtime.py`
  - frontend already sends an image before audio in `useRealtimeSession.ts`

Therefore Plan 06b is **not** a fresh implementation plan for those five items.
It is a **reconciliation + regression-hardening plan** that:
  1. preserves the already-landed behavior
  2. closes the remaining explicit regression gap
  3. cleans up duplicated test coverage
  4. proves the runtime behavior with fast binary gate checks

Remaining real gaps for Plan 06b:
  - GAP A — No explicit regression test yet proves `MultimodalClient.from_settings()` is created exactly once per WebSocket session.
  - GAP B — `tests/unit/test_intent_classifier.py` contains duplicated `TRANSLATE` tests.
  - GAP C — `tests/unit/test_policy_router.py` contains duplicated `TRANSLATE` tests and lacks the granular assertions requested in the post-mortem.

Non-goals for Plan 06b:
  - Do not re-add `TRANSLATE` to classifier or router.
  - Do not re-implement first-turn image fallback.
  - Do not re-implement async lookahead classification.
  - Do not re-implement frontend frame-before-audio sending.
  - Do not add new runtime files.

## Section 2 — Step 1: Read Before Planning (actual findings)

Files read completely:
  - `C:/ally-vision-v2/apps/backend/api/routes/realtime.py`
  - `C:/ally-vision-v2/core/orchestrator/intent_classifier.py`
  - `C:/ally-vision-v2/core/orchestrator/policy_router.py`
  - `C:/ally-vision-v2/apps/backend/services/dashscope/multimodal_client.py`
  - `C:/ally-vision-v2/shared/config/settings.py`
  - `C:/ally-vision-v2/tests/unit/test_intent_classifier.py`
  - `C:/ally-vision-v2/tests/unit/test_policy_router.py`
  - `C:/ally-vision-v2/tests/unit/test_realtime_route.py`
  - `C:/ally-vision-v2/tests/unit/test_heavy_vision.py`
  - `C:/ally-vision-v2/apps/frontend/hooks/useRealtimeSession.ts`
  - `C:/ally-vision-v2/apps/frontend/hooks/useCameraCapture.ts`
  - `C:/ally-vision-v2/apps/frontend/app/page.tsx`

Repo findings:

### `apps/backend/api/routes/realtime.py`
- Current routing decision is used in the audio-turn path before the upstream realtime call.
- `HEAVY_VISION` is detected at:
  - `174-175`: `if decision.target == RouteTarget.HEAVY_VISION:` then `applied_target = RouteTarget.HEAVY_VISION`
- When `HEAVY_VISION` is routed:
  - `176-177`: it selects `vision_image_b64 = classified_image_b64 or pending_image_b64`
  - `177`: it runs `assess_frame_quality(vision_image_b64)`
  - `178-185`: if unusable, it sets spoken guidance instructions and skips heavy vision HTTP
  - `186-215`: if usable, it calls `mm_client.analyze(VisionRequest(...))`
  - `198-206`: on success, it turns returned text into spoken instructions
  - `207-215`: on failure, it falls back to retry guidance
  - `239-244`: it still sends the final user turn through `client.async_send_audio_turn(...)`

### `core/orchestrator/policy_router.py`
- `RouteTarget.HEAVY_VISION` definition:
  - `25`: `HEAVY_VISION = "HEAVY_VISION"`
- `requires_frame` in context means the intent needs a current camera frame before it can be served safely.
- Evidence:
  - `55-63`: `READ_TEXT` and `SCAN_PAGE` both route to `HEAVY_VISION` with `requires_frame=True`
  - `115-116`: returned `RoutingDecision` includes the route target and `requires_frame` flag

### `shared/config/settings.py`
- `QWEN_VISION_MODEL`
  - `50-53`
  - dev default: `qwen3.5-flash`
  - exam default: `qwen3.6-plus`
- `DASHSCOPE_COMPAT_BASE`
  - `40-43`: `https://dashscope-intl.aliyuncs.com/compatible-mode/v1`
- `DASHSCOPE_HTTP_BASE`
  - `32-35`: `https://dashscope-intl.aliyuncs.com/api/v1`

### Symbol search findings with exact line numbers

`last_user_transcript` in `realtime.py`
  - `93`: declaration
  - `252`: assignment from `result.user_transcript`
  - `253`: truthiness check
  - `256`: classification task creation uses it
  - `261`: queued lookahead stores it

`pending_classification_task` in `realtime.py`
  - `96`: declaration
  - `127-132`: done-task check and result retrieval
  - `141`: reset to `None`
  - `147-149`: `_asyncio.create_task(classifier.classify(queued_transcript))`
  - `153-154`: not-done branch
  - `254-257`: `_asyncio.create_task(classifier.classify(last_user_transcript))`

`pending_image_b64` in `realtime.py`
  - `99`: declaration
  - `161-163`: first-turn image fallback to `SCENE_DESCRIBE`
  - `176`: consumed into `vision_image_b64`
  - `221`: frame-required fallback branch
  - `242`: passed to `client.async_send_audio_turn(...)`
  - `249`: copied to `turn_image_b64`
  - `266`: reset to `None`
  - `325-327`: assigned from control message `{"type":"image"}`

`mm_client` in `realtime.py`
  - `95`: `mm_client = MultimodalClient.from_settings()`
  - `189`: logging `mm_client._model`
  - `191`: `vision_result = await mm_client.analyze(...)`

`captureFrame` in `apps/frontend/`
  - `apps/frontend/app/page.tsx:13`: `useRealtimeSession(camera.captureFrame)`
  - `apps/frontend/hooks/useCameraCapture.ts:33-50`: function implementation
  - `apps/frontend/hooks/useRealtimeSession.ts:36`: hook accepts `captureFrame`
  - `apps/frontend/hooks/useRealtimeSession.ts:42`: `captureFrameRef` declaration
  - `apps/frontend/hooks/useRealtimeSession.ts:60-64`: frame captured and sent before audio in `flushTurn()`
  - `apps/frontend/hooks/useRealtimeSession.ts:110`: `captureFrameRef.current = captureFrame`
  - `apps/frontend/hooks/useRealtimeSession.ts:121-124`: capture after playback
  - `apps/frontend/hooks/useRealtimeSession.ts:158-160`: manual capture button path
  - `apps/frontend/hooks/useRealtimeSession.ts:172`: reset on stop

`useRealtimeSession` in `apps/frontend/`
  - `apps/frontend/hooks/useRealtimeSession.ts:36`: hook export
  - `apps/frontend/app/page.tsx:9`: import
  - `apps/frontend/app/page.tsx:13`: usage

`TRANSLATE` in `core/orchestrator/`
  - `core/orchestrator/intent_classifier.py:31`: `_LABELS`
  - `core/orchestrator/intent_classifier.py:39-41`: prompt includes TRANSLATE instructions
  - `core/orchestrator/intent_classifier.py:55`: enum member
  - `core/orchestrator/policy_router.py:26`: `RouteTarget.TRANSLATE`
  - `core/orchestrator/policy_router.py:85-93`: routing table entry

Test-file findings:
- `tests/unit/test_intent_classifier.py`
  - `56-70`: first `test_classify_returns_translate`
  - `74-88`: duplicate `test_classify_returns_translate`
- `tests/unit/test_policy_router.py`
  - `35-42`: first translate routing test
  - `45-52`: duplicate translate routing test
- `tests/unit/test_realtime_route.py`
  - `190-225`: first-turn image fallback already covered
  - `328-369`: non-blocking classifier behavior already covered
  - No explicit `mm_client created once per session` test yet

## Section 3 — Step 2: Verify Docs

1. DashScope compatible-mode: does qwen-turbo support classification prompts returning a single label word?
   - **CONFIRMED (partial)**: `qwen-turbo` is a supported model on the compatible-mode chat-completions endpoint.
   - **UNCONFIRMED (specific behavior)**: Alibaba docs do not explicitly document “single-label classification prompt” as a named supported pattern. That behavior is a prompt-design choice, not a documented product guarantee.

2. Qwen Omni realtime multilingual support for TRANSLATE intent
   - **CONFIRMED**: Qwen3.5-Omni documentation explicitly lists support for **113 input languages/dialects**.

3. `asyncio.create_task()` safety inside FastAPI WebSocket handler
   - **CONFIRMED**: Python docs identify `asyncio.create_task()` as the standard API for scheduling a coroutine as a task in the running event loop.
   - **CONFIRMED**: FastAPI/Starlette WebSocket handlers are async coroutines running on the active event loop, so using `create_task()` from inside the handler is valid.
   - **Guardrail**: create tasks only from within the handler coroutine and keep loop-bound objects session-local to avoid cross-loop test/runtime issues.

## Section 4 — Plan Requirements

### A) Goal
Reconcile the stale 06b post-mortem against the actual repo, preserve the already-landed runtime fixes, close the one remaining regression gap (`mm_client` once-per-session coverage), and clean up duplicated TRANSLATE test coverage.

### B) Files To Edit (actual reconciled scope)

Expected code edits for 06b are **test-focused**. Runtime files should remain unchanged unless a newly added regression test proves a real defect.

1. `tests/unit/test_realtime_route.py`
   - ADD:
     - `test_websocket_creates_multimodal_client_once_per_session()`
       - patch `MultimodalClient.from_settings`
       - open one websocket session
       - send multiple audio turns
       - assert constructor/factory called exactly once for the session
       - assert existing behavior still works across multiple turns

2. `tests/unit/test_intent_classifier.py`
   - CLEAN UP duplicate translate coverage
   - KEEP one translate-intent test
   - ADD:
     - `test_translate_in_labels()`
       - assert `"TRANSLATE" in _LABELS`
   - REMOVE or merge the duplicate `test_classify_returns_translate()` so coverage is not duplicated

3. `tests/unit/test_policy_router.py`
   - CLEAN UP duplicate translate routing test
   - REPLACE the duplicate pair with these explicit tests:
     - `test_translate_routes_to_realtime_chat()`
     - `test_translate_not_requires_frame()`
     - `test_translate_has_system_instructions()`

4. `apps/backend/api/routes/realtime.py`
   - **Expected outcome: no code change** because the requested fixes are already present.
   - Edit only if the new `mm_client once per session` regression test fails.
   - If that happens, enforce this exact invariant:
     - `MultimodalClient.from_settings()` stays above the websocket `while True` loop
     - no per-turn `MultimodalClient()` or `.from_settings()` call exists below line `102`

5. `apps/frontend/hooks/useRealtimeSession.ts`
   - **Expected outcome: no code change** because frame-before-audio sending is already present in `flushTurn()`.
   - Do not edit unless Gate 2 proves a real mismatch between browser runtime behavior and current code.

### C) Files To Create
None.

### D) Files To Delete
None.

### E) Tests To Update

1. `tests/unit/test_intent_classifier.py`
   ADD / NORMALIZE:
     - `test_translate_in_labels()`
       - verify `"TRANSLATE" in _LABELS`
     - `test_classify_translate_intent()`
       - mock httpx to return `"TRANSLATE"`
       - assert `result.intent == IntentCategory.TRANSLATE`
   CLEANUP:
     - remove duplicate translate test definition so only one translate-classification test remains

2. `tests/unit/test_policy_router.py`
   ADD / NORMALIZE:
     - `test_translate_routes_to_realtime_chat()`
       - assert `route(IntentCategory.TRANSLATE).target == RouteTarget.REALTIME_CHAT`
     - `test_translate_not_requires_frame()`
       - assert `route(IntentCategory.TRANSLATE).requires_frame is False`
     - `test_translate_has_system_instructions()`
       - assert `"translate" in route(IntentCategory.TRANSLATE).system_instructions.lower()`
   CLEANUP:
     - remove duplicate translate routing test definition

3. `tests/unit/test_realtime_route.py`
   ADD:
     - `test_mm_client_created_once_per_session()`
       - verify `MultimodalClient.from_settings()` is not re-instantiated on every audio turn
   KEEP existing tests untouched because they already cover:
     - first-turn image fallback to `SCENE_DESCRIBE`
     - non-blocking classifier behavior via lookahead task

### F) Tests To Run (exact commands)
`C:/ally-vision-v2/.venv/Scripts/pytest.exe tests/unit/test_intent_classifier.py -v --timeout=30 -x`

`C:/ally-vision-v2/.venv/Scripts/pytest.exe tests/unit/test_policy_router.py -v --timeout=30 -x`

`C:/ally-vision-v2/.venv/Scripts/pytest.exe tests/unit/test_realtime_route.py -v --timeout=30 -x`

`C:/ally-vision-v2/.venv/Scripts/pytest.exe tests/unit/test_heavy_vision.py -v --timeout=30 -x`

### G) Gate Checks

GATE 1 — Translation intent live:
  Start backend.
  Open browser, speak: "translate hello to Hindi"
  Ally must respond in Hindi. Not a generic reply.
  PASS = Hindi response heard
  FAIL = generic response or error

GATE 2 — Frame auto-sent with audio turn:
  Open browser DevTools → Network → WS.
  Speak anything while camera is on.
  WS frames must show: image JSON message sent
  BEFORE audio binary frame.
  PASS = image frame visible in DevTools before audio frame
  FAIL = no image frame in WS messages

GATE 3 — First-turn vision works:
  Open browser, point camera at object.
  Speak "what is this" as first ever message.
  (No prior turn, no transcript history)
  Ally must describe the object, not give generic response.
  PASS = object described correctly
  FAIL = generic "how can I help" response

## Section 5 — Quality Self-Check
Before committing the plan file, verify:
  □ TRANSLATE already exists in both `intent_classifier.py` and `policy_router.py`
  □ TRANSLATE is already mapped to `REALTIME_CHAT` (Qwen native, no new service)
  □ first-turn fallback already uses `SCENE_DESCRIBE` when image present
  □ async classification already uses `create_task()` — current turn is not blocked
  □ `mm_client` is already session-scoped, not per-turn
  □ Frontend already sends image BEFORE audio binary in same turn
  □ All 5 stale-gap claims are reconciled against actual repo state
  □ No existing passing tests are broken
  □ Gate checks are binary PASS/FAIL and runnable in < 5 minutes
  □ No always-on background processing introduced
  □ No new runtime files created — only test cleanup/hardening expected

## Section 6 — Commit Rule
Commit ONLY the plan file:

  git add .sisyphus/plans/06b-heavy-vision-fixes.md
  git commit -m "plan: write plan 06b heavy vision fixes

  Fix 5 gaps from Plan 06:
  - TRANSLATE intent added to classifier + router
  - First-turn vision fallback (SCENE_DESCRIBE when image present)
  - Async non-blocking classification via create_task()
  - mm_client moved to session scope (not per-turn)
  - Frontend auto-sends frame before every audio turn"

Commit-message note:
  The message is preserved exactly as requested for continuity,
  even though the repo read shows those fixes are already landed and
  06b is now a regression-hardening / reconciliation plan.

## Section 7 — Stop Rule
STOP. Say "PLAN 06b PROMETHEUS COMPLETE"
Wait for instruction.
