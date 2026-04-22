# Plan 06 — Heavy Vision Alignment and Consolidation

## 1. Purpose

This is a **refine/alignment rewrite** of Plan 06, not a greenfield heavy-vision build plan. The backend already contains a live Heavy Vision path, including routing inside `apps/backend/api/routes/realtime.py`, a multimodal client, a pixel-based capture gate, high-level vision helpers, and unit tests. The purpose of this rewrite is to align stale planning language with current implementation truth, tighten the documented architecture, and define the remaining cleanup / verification work precisely.

The rewrite also locks the strongest repo-aligned technical baseline: **Heavy Vision should be documented around the native DashScope multimodal HTTP endpoint, with current repo model reality `qwen3.6-plus`**. Compatible-mode image input remains valid documentation context in general, but it is not the authoritative baseline assumption for the current repo’s heavy-vision model.

## 2. What is true now

- **CURRENT REPO REALITY** — Heavy Vision is already wired in `apps/backend/api/routes/realtime.py`.
  - `realtime.py:283-329` contains the live `RouteTarget.HEAVY_VISION` branch.
- **CURRENT REPO REALITY** — first-turn image fallback already exists.
  - `realtime.py:225-227` sets `predicted_intent = IntentCategory.SCENE_DESCRIBE` when no transcript exists and `pending_image_b64` is present.
- **CURRENT REPO REALITY** — `pending_image_b64` already has a complete lifecycle in the route.
  - declared at `realtime.py:160`
  - set from control message at `realtime.py:515-519`
  - consumed in route logic at `realtime.py:187`, `285`
  - reset at `realtime.py:458`
- **CURRENT REPO REALITY** — `last_user_transcript` is already stored and reused.
  - declared at `realtime.py:152`
  - assigned from current turn result at `realtime.py:439`
  - used for previous-turn memory logic at `realtime.py:241-243`, `259-267`, `440-449`
- **CURRENT REPO REALITY** — `_is_memory_query` already exists.
  - defined at `realtime.py:75-80`
  - used at `realtime.py:451-455`
- **CURRENT REPO REALITY** — `apps/backend/services/dashscope/multimodal_client.py` already exists.
- **CURRENT REPO REALITY** — `core/orchestrator/capture_coach.py` already exists and is wired before expensive vision use.
- **CURRENT REPO REALITY** — `core/vision/live_scene_reader.py` already exists.
- **CURRENT REPO REALITY** — `core/vision/page_reader.py` already exists.
- **CURRENT REPO REALITY** — `core/vision/framing_judge.py` already exists, but is not wired into the realtime route yet.
- **CURRENT REPO REALITY** — `tests/unit/test_heavy_vision.py` already exists and is part of the current validation surface.
- **CURRENT REPO REALITY** — the repo now has **9 intents**, not 8.
  - `intent_classifier.py:47-56` defines: `SCENE_DESCRIBE`, `READ_TEXT`, `SCAN_PAGE`, `WEB_SEARCH`, `MEMORY_SAVE`, `MEMORY_RECALL`, `DOCUMENT_QA`, `TRANSLATE`, `GENERAL_CHAT`
- **CURRENT REPO REALITY** — `TRANSLATE` exists in routing reality.
  - `policy_router.py:83-91` routes `TRANSLATE` to `REALTIME_CHAT`
- **CURRENT REPO REALITY** — `qwen3.6-plus` is the configured heavy-vision model for both dev and exam.
  - `settings.py:51-54`
- **CONFIRMED** — the strongest documented baseline for current repo reality is the **native DashScope multimodal endpoint**:
  - `POST {DASHSCOPE_HTTP_BASE}/services/aigc/multimodal-generation/generation`
- **WEAKER EVIDENCE** — compatible-mode image input is documented generally, but exact `qwen3.6-plus` image-input support on compatible mode is not strong enough to treat as the default implementation assumption.

## 3. Historical assumptions to remove or rewrite

- **HISTORICAL / SUPERSEDED** — “Heavy Vision is not implemented yet.”
  - This is false in current repo reality.
- **HISTORICAL / SUPERSEDED** — “Plan 06 builds Heavy Vision from scratch.”
  - Current repo already has the route, client, capture gate, helpers, and tests.
- **HISTORICAL / SUPERSEDED** — “There are 8 intents.”
  - Current repo has 9 intents, including `TRANSLATE`.
- **HISTORICAL / SUPERSEDED** — “Dev baseline is qwen3.5-flash while exam is qwen3.6-plus.”
  - Current repo reality uses `qwen3.6-plus` for both dev and exam in `settings.py`.
- **HISTORICAL / SUPERSEDED** — “Compatible-mode image input is the default heavy-vision assumption for qwen3.6-plus.”
  - This is weaker evidence and should not be the baseline assumption in the rewritten plan.
- **STALE CODE COMMENT** — `intent_classifier.py:4` still says “8 intent categories” even though the enum and label list now contain 9 values.

## 4. Current architecture

This is the actual heavy-vision flow in the repo today, in sequence:

1. **Frontend sends audio and optional image/frame**
   - The browser sends audio over `/ws/realtime` as a binary frame.
   - It can also send `{"type":"image","data":"<base64 jpeg>"}` before the turn.

2. **`realtime.py` receives WebSocket messages**
   - `apps/backend/api/routes/realtime.py` owns the main orchestration loop.
   - It stores `pending_image_b64` and `pending_instructions` as per-turn state.

3. **Intent classifier predicts route from transcript context**
   - Previous-turn classification happens through `IntentClassifier` task lookahead.
   - If there is no transcript yet but an image exists, the route falls back to `SCENE_DESCRIBE`.

4. **Policy router selects target**
   - `policy_router.route()` returns a `RoutingDecision` with `target`, `requires_frame`, and `system_instructions`.
   - `READ_TEXT` and `SCAN_PAGE` currently map to `HEAVY_VISION`.

5. **Capture coach validates frame quality before expensive vision use**
   - `capture_coach.assess_frame_quality()` blocks obviously bad frames using cheap pixel heuristics.
   - If the frame is bad, the route injects spoken guidance instead of calling the multimodal model.

6. **Multimodal client sends image + prompt to the heavy-vision model**
   - Current implementation detail: `multimodal_client.py` still uses compatible-mode request shape.
   - Baseline plan assumption after this rewrite: Heavy Vision should be documented around native DashScope multimodal HTTP for `qwen3.6-plus`.

7. **High-level helpers shape the prompts**
   - `live_scene_reader.py` provides scene description prompts.
   - `page_reader.py` provides OCR-style extraction and page-summary prompts.

8. **The result is returned through the existing orchestration path**
   - `realtime.py` turns successful heavy-vision text into `effective_instructions`.
   - The final spoken answer is still returned through the existing Omni audio response path.

## 5. Files and responsibilities

| File path | Current responsibility | Status |
|---|---|---|
| `apps/backend/api/routes/realtime.py` | Main `/ws/realtime` orchestration route; manages per-turn state, previous-turn classification, Heavy Vision branch, memory handling, interrupt control | **Implemented; reality source of truth** |
| `apps/backend/services/dashscope/multimodal_client.py` | HTTP heavy-vision client for image + prompt analysis | **Implemented; baseline transport assumption needs alignment** |
| `core/orchestrator/capture_coach.py` | Lightweight pixel-quality gate before expensive vision calls | **Implemented and wired** |
| `core/vision/live_scene_reader.py` | Builds scene-description prompts and delegates to multimodal client | **Implemented** |
| `core/vision/page_reader.py` | Builds OCR / page-summary prompts and delegates to multimodal client | **Implemented** |
| `core/vision/framing_judge.py` | Model-based framing check for future use after cheap gate | **Implemented; not wired** |
| `core/orchestrator/intent_classifier.py` | Classifies transcripts into current 9-intent set | **Implemented; docstring still stale** |
| `core/orchestrator/policy_router.py` | Maps intent to route target and instructions, including `HEAVY_VISION` and `TRANSLATE` reality | **Implemented** |
| `shared/config/settings.py` | Holds current `QWEN_VISION_MODEL`, `DASHSCOPE_COMPAT_BASE`, `DASHSCOPE_HTTP_BASE` values | **Implemented; current model reality is qwen3.6-plus for both profiles** |
| `tests/unit/test_heavy_vision.py` | Validates multimodal client + vision helper behavior | **Implemented; still pins compatible-mode request shape** |
| `tests/unit/test_realtime_route.py` | Validates route orchestration behavior around images, heavy vision, memory, interrupts | **Implemented** |

## 6. Baseline technical decisions

- **LOCKED BASELINE** — Native DashScope multimodal endpoint is the baseline Heavy Vision path.
  - `POST {DASHSCOPE_HTTP_BASE}/services/aigc/multimodal-generation/generation`
- **LOCKED BASELINE** — `qwen3.6-plus` is the current heavy-vision model in repo reality.
- **LOCKED BASELINE** — Compatible-mode image input remains documented only as secondary/general context.
- **LOCKED BASELINE** — The rewritten plan must not assume compatible-mode image support for `qwen3.6-plus` is the authoritative production path unless stronger repo-aligned evidence is gathered later.
- **CURRENT IMPLEMENTATION DETAIL** — `multimodal_client.py` is still written against compatible mode today; this is a current implementation fact, not the baseline architectural assumption the rewritten plan should preserve.

## 7. Remaining work

This section is intentionally narrow because Heavy Vision already exists.

- **Alignment cleanup**
  - Rewrite stale plan language so it matches implemented repo truth.
  - Clean up stale “8 intents” language in code comments/docstrings where needed.

- **Model / endpoint consistency verification**
  - Align `multimodal_client.py` to the native DashScope multimodal baseline.
  - Keep `qwen3.6-plus` as the current heavy-vision model unless a separate explicit config decision changes it.

- **Route verification**
  - Preserve `pending_image_b64`, first-turn fallback, `last_user_transcript`, and memory/interrupt behavior while tightening Heavy Vision transport assumptions.

- **Prompt / policy tightening**
  - Keep `READ_TEXT` / `SCAN_PAGE` mapped to `HEAVY_VISION`.
  - Preserve `TRANSLATE` as current routing reality, while being explicit that it is not itself the Heavy Vision target.

- **Test additions / updates**
  - Update Heavy Vision tests to match the locked baseline transport choice.
  - Add route-level regression checks to ensure Heavy Vision changes do not break memory or interrupt behavior.

- **Optional future path**
  - `framing_judge.py` remains a future enhancement path, not required core work for this rewrite.

## 8. Tests and validation

### Automated tests to run

Use exact current repo test paths:

```powershell
C:/ally-vision-v2/.venv/Scripts/pytest.exe tests/unit/test_heavy_vision.py -v --timeout=30 -x
C:/ally-vision-v2/.venv/Scripts/pytest.exe tests/unit/test_realtime_route.py -v --timeout=30 -x
C:/ally-vision-v2/.venv/Scripts/pytest.exe tests/unit/test_intent_classifier.py -v --timeout=30 -x
C:/ally-vision-v2/.venv/Scripts/pytest.exe tests/unit/test_policy_router.py -v --timeout=30 -x
```

If `apps/backend/services/dashscope/multimodal_client.py` changes:
- extend `tests/unit/test_heavy_vision.py` to pin the native DashScope request/response shape.

If `apps/backend/api/routes/realtime.py` changes:
- extend `tests/unit/test_realtime_route.py` to verify that Heavy Vision still preserves image state, first-turn visual fallback, memory behavior, and interrupt behavior.

### Manual gate checks

1. **First-turn visual behavior when image is present**
   - Capture an image before the first spoken turn.
   - Ask a visual question as the first turn.
   - PASS: app gives a visual answer, not a generic chat response.
   - NOTE: current repo reality uses first-turn `SCENE_DESCRIBE` fallback here, not direct `HEAVY_VISION`.

2. **OCR / read-text query**
   - Capture clear printed text.
   - Ask: `read this`.
   - PASS: text is read accurately and spoken back.

3. **Scene description query**
   - Capture a general scene.
   - Ask: `what is in front of me`.
   - PASS: scene is described in a grounded way.

4. **Translation-adjacent visual query (current routing reality)**
   - Capture visible non-English text.
   - Ask: `translate this`.
   - PASS: route behaves consistently with current `TRANSLATE → REALTIME_CHAT` reality and uses available image context if present.

## 9. Non-goals

- Do **not** pretend Heavy Vision is not already built.
- Do **not** reintroduce 8-intent language.
- Do **not** make compatible-mode image input the default `qwen3.6-plus` baseline.
- Do **not** invent unsupported new subsystems.
- Do **not** broaden scope into unrelated route/memory refactors.
- Do **not** wire `framing_judge.py` into the route as required work for this rewrite.
- Do **not** silently change the heavy-vision model away from current repo reality.

## 10. Commit rule

If this rewrite is committed, commit **only** the rewritten plan file.
No code changes.

## 11. Stop rule

STOP. Say PLAN 06 REWRITE COMPLETE. Wait for instruction.
