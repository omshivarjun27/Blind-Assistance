# Plan 06b — Heavy Vision Fixes

## Context

Historical reference point:
- Plan 06 Prometheus commit: `d2fd94a`
- Post-06 gap list originally identified:
  1. TRANSLATE intent missing
  2. First-turn vision fallback missing
  3. Frontend not sending a frame with each audio turn
  4. Classification blocking turns
  5. `mm_client` instantiated per turn

Current repo truth after audit (HEAD is beyond Plan 06):
- Those five gaps are already implemented in code.
- Therefore, Plan 06b is now a **verification/supersession plan**, not a new feature implementation plan.
- The purpose of this file is to document the exact code locations, doc confirmations, and the remaining manual gate checks that still need a human to verify in the browser.

Current relevant commits after Plan 06:
- `ee79273` — heavy vision path
- `24c3a8e` — camera vision pipeline + translation intent

## Step 1 — Repo audit before planning

### Backend and orchestrator findings (exact symbol locations)

#### `apps/backend/api/routes/realtime.py`
- `last_user_transcript`: line **93**
- `mm_client = MultimodalClient.from_settings()`: line **95**
- `pending_classification_task`: line **96**
- `pending_image_b64`: line **99**
- previous-turn classification block starts: line **118**
- first-turn image fallback:
  - `if predicted_intent is None and pending_image_b64:` line **161**
  - `predicted_intent = IntentCategory.SCENE_DESCRIBE` line **162**
- heavy vision branch begins: line **174**
- heavy vision uses current/preserved image:
  - `vision_image_b64 = classified_image_b64 or pending_image_b64` line **176**
- multimodal call:
  - `mm_client.analyze(...)` lines **191-197**
- previous-turn classification task creation:
  - `_asyncio.create_task(classifier.classify(last_user_transcript))` lines **254-257**
- current turn still sends image/audio to realtime client:
  - `image_jpeg_b64=pending_image_b64` line **242**

Current behavioral summary:
- Classification is non-blocking and previous-turn based.
- If no transcript exists yet but an image is present, the route assumes `SCENE_DESCRIBE`.
- `mm_client` is already session-scoped.
- Heavy vision uses preserved image state from the classified turn.

#### `core/orchestrator/intent_classifier.py`
- `_LABELS` includes `TRANSLATE`: line **31**
- classifier prompt includes translation wording: lines **35-43**
- `IntentCategory.TRANSLATE`: line **55**

#### `core/orchestrator/policy_router.py`
- `RouteTarget.TRANSLATE`: line **26**
- `IntentCategory.TRANSLATE` mapping: lines **85-93**
- Current target for translate is `RouteTarget.REALTIME_CHAT`, not a separate translation backend.

#### `apps/backend/services/dashscope/multimodal_client.py`
- `VisionRequest`: lines **28-33**
- `VisionResponse`: lines **36-43**
- `MultimodalClient.from_settings()`: lines **63-75**
- `analyze()` method: lines **77-157**

#### Frontend: `apps/frontend/hooks/useRealtimeSession.ts`
- `captureFrameRef`: line **42**
- auto-capture before audio send:
  - `const frame = captureFrameRef.current?.();` line **60**
  - console log `[Session] Frame captured:` line **61**
  - send image before audio: lines **62-65**
- `captureFrameRef.current = captureFrame`: line **110**
- auto-preload next frame after playback: lines **121-124**
- manual capture path still exists: lines **157-160**

#### Frontend: `apps/frontend/lib/ws-client.ts`
- `sendImage()` logs and sends image JSON: lines **73-76**

### Existing tests that now enforce the once-missing behavior

#### `tests/unit/test_intent_classifier.py`
- translate classification test: lines **55-88**

#### `tests/unit/test_policy_router.py`
- translate routing test: lines **35-52**

#### `tests/unit/test_realtime_route.py`
- image queued for next turn: lines **152-188**
- first-turn no-transcript image fallback to scene describe: lines **190-225**
- non-blocking pending classifier: lines **328-369**
- empty transcript clears stale classification state: lines **372-423**
- first heavy-vision request preserved while later transcript arrives: lines **425-510**

### Audit conclusion

The five original 06b gaps are already fixed in the current codebase. There is no honest implementation work left that matches the original 06b scope.

## Step 2 — Docs verification

### Point 1 — qwen-turbo for short single-label classification prompts
**UNCONFIRMED**

Confirmed:
- official Alibaba docs list `qwen-turbo` as a supported compatible-mode chat model.

Not confirmed:
- I did not find an official Alibaba doc explicitly recommending `qwen-turbo` for short single-label classification prompts.

Interpretation:
- The current classifier path is plausible and already passing tests, but not directly doc-proven as a classification best practice.

### Point 2 — Qwen Omni realtime multilingual support for translation-style prompts
**UNCONFIRMED**

Confirmed:
- official docs confirm multilingual recognition/synthesis support and configurable instructions/system goals.

Not confirmed:
- I did not find a direct official doc statement that Omni-Realtime itself should be used for prompt-driven translation, because Alibaba also documents a dedicated realtime translation model separately.

Interpretation:
- The current `TRANSLATE -> REALTIME_CHAT` design is plausible and already implemented, but not first-party doc-proven as the canonical translation path.

### Point 3 — `asyncio.create_task()` safety inside FastAPI WebSocket handler
**CONFIRMED**

Confirmed from docs:
- `asyncio.create_task()` schedules work on the running event loop.
- FastAPI WebSocket handlers are async handlers and run on the event loop.
- Important caveat: keep a strong reference to created tasks so they are not garbage collected.

Interpretation:
- The current route’s retained task references are consistent with safe usage.

## Plan requirements (supersession status)

### Goal
No new code changes are required for the original 06b scope because all five historical gaps are already implemented.

### Files to edit
None for the original 06b gap list.

### Files to create
None.

### Files to delete
None.

### Tests to update
None required for the original 06b scope, because the relevant tests already exist and currently pass:
- `tests/unit/test_intent_classifier.py`
- `tests/unit/test_policy_router.py`
- `tests/unit/test_realtime_route.py`

### Tests to run to confirm the 06b state remains healthy
```bash
C:/ally-vision-v2/.venv/Scripts/pytest.exe tests/unit/test_intent_classifier.py -v --timeout=30 -x
C:/ally-vision-v2/.venv/Scripts/pytest.exe tests/unit/test_policy_router.py -v --timeout=30 -x
C:/ally-vision-v2/.venv/Scripts/pytest.exe tests/unit/test_realtime_route.py -v --timeout=30 -x
C:/ally-vision-v2/.venv/Scripts/pytest.exe tests/unit/test_heavy_vision.py -v --timeout=30 -x
```

### Remaining gate checks (manual only)

#### Gate 1 — Translation intent live
- Start backend + frontend.
- Speak: `translate hello to Hindi`
- Pass: Hindi response is heard.

#### Gate 2 — Frame auto-sent with audio turn
- Open browser DevTools → Network → WS.
- Speak any utterance while camera is on.
- Pass: image JSON frame is visible before the binary audio frame.

#### Gate 3 — First-turn vision works
- Open browser, point camera at object.
- First utterance only: `what is this`
- Pass: object is described rather than a generic chat response.

## Quality self-check

- [x] `TRANSLATE` exists in both `intent_classifier.py` and `policy_router.py`
- [x] `TRANSLATE` maps to `REALTIME_CHAT`
- [x] first-turn fallback uses `SCENE_DESCRIBE` when image is present
- [x] async classification uses `create_task()` and does not block the turn
- [x] `mm_client` is session-scoped
- [x] frontend sends image before audio in the auto-capture path
- [x] all five original 06b gaps are already addressed
- [x] no new files are needed for the original gap list

## Commit rule

Commit ONLY this plan file:

```bash
git add .sisyphus/plans/06b-heavy-vision-fixes.md
git commit -m "plan: write plan 06b heavy vision fixes

Fix 5 gaps from Plan 06:
- TRANSLATE intent added to classifier + router
- First-turn vision fallback (SCENE_DESCRIBE when image present)
- Async non-blocking classification via create_task()
- mm_client moved to session scope (not per-turn)
- Frontend auto-sends frame before every audio turn"
```

## Stop rule

This plan records that the intended 06b code fixes are already present in the current repo. No further implementation should be performed under Plan 06b unless a new gap is discovered during the manual browser gates.
