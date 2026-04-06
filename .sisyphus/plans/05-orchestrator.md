---

# Plan 05 — Orchestrator and Intent Router

## Goal
Add intent classification and routing so the system
knows what the user wants before deciding how to respond.

Currently: every audio turn goes directly to Qwen Omni.
After this plan: the orchestrator classifies intent
first, then routes to the correct handler.

## Intent Categories
Define exactly these 8 intents:

  SCENE_DESCRIBE   → "what is in front of me",
                     "what do you see", "describe surroundings"
  READ_TEXT        → "read this", "what does this say",
                     "read the label", "read the sign"
  SCAN_PAGE        → "scan this page", "capture this"
  WEB_SEARCH       → "search for", "look up", "find online"
  MEMORY_SAVE      → "remember", "save this", "note that"
  MEMORY_RECALL    → "what did I tell you", "do you remember",
                     "recall", "what is my"
  DOCUMENT_QA      → "summarize this document",
                     "what does the document say",
                     "find in document"
  GENERAL_CHAT     → everything else (default)

## Architecture Decision
Intent classification approach:
  Use qwen-turbo via DashScope compatible mode
  Send the user transcript as input
  Ask for one-word intent label
  Parse response → map to IntentCategory enum
  Fallback to GENERAL_CHAT on any error

Why qwen-turbo not Qwen Omni for classification:
  - Classification is text-only, fast, cheap
  - Qwen Omni is reserved for audio+vision turns
  - qwen-turbo via compatible mode = simple HTTP POST

What is confirmed from research:
- Zero-shot / few-shot LLM classification with a fixed label set and constrained output format is a standard prompt pattern.
- Best parseability is a single label only or tightly constrained JSON.
- DashScope compatible chat-completions base is `https://dashscope-intl.aliyuncs.com/compatible-mode/v1/chat/completions`.
- `qwen-turbo` is a documented compatible-mode model name.

Important routing realism for Plan 05:
- Current `/ws/realtime` has **no pre-send transcript** for the current audio turn.
- `result.user_transcript` arrives **with** the response from the completed turn.
- Therefore Plan 05 can only classify using the **previous turn’s transcript** when the input is voice-only.
- This plan still adds the classifier, router, and instruction-injection machinery now, but same-turn audio intent routing remains limited by transcript timing.

## Safe Deletions In This Plan
None. This plan only adds new files.

## Files To Create

### core/orchestrator/intent_classifier.py
Describe exactly what this file must contain:

ENUM: IntentCategory
  SCENE_DESCRIBE
  READ_TEXT
  SCAN_PAGE
  WEB_SEARCH
  MEMORY_SAVE
  MEMORY_RECALL
  DOCUMENT_QA
  GENERAL_CHAT

DATACLASS: ClassificationResult
  intent: IntentCategory
  confidence: str  ("high" | "low")
  raw_label: str
  error: str | None = None

CLASS: IntentClassifier
  __init__(api_key: str, model: str = "qwen-turbo",
           base_url: str = DASHSCOPE_COMPAT_BASE)
  async classify(transcript: str) -> ClassificationResult
    If transcript empty → return GENERAL_CHAT high
    Call qwen-turbo with prompt:
      "Classify this user request into exactly one of:
       SCENE_DESCRIBE, READ_TEXT, SCAN_PAGE, WEB_SEARCH,
       MEMORY_SAVE, MEMORY_RECALL, DOCUMENT_QA, GENERAL_CHAT.
       Reply with ONLY the category name, nothing else.
       Request: {transcript}"
    Parse response → match to IntentCategory
    If no match → GENERAL_CHAT low
    On any exception → GENERAL_CHAT low, set error

  classmethod from_settings() -> IntentClassifier
    Uses get_api_key(), DASHSCOPE_COMPAT_BASE

Implementation details that must be explicit:
- Use `httpx.AsyncClient`.
- POST to `{base_url}/chat/completions`.
- Use `Authorization: Bearer {api_key}` header.
- Use a short timeout: **3 seconds**.
- Response parsing target:
  `response["choices"][0]["message"]["content"].strip()`
- Normalize case and whitespace before matching labels.
- If the model returns extra prose, punctuation, multiple labels, or blank output, fall back to `GENERAL_CHAT` low.
- Classifier failure must never block or duplicate a user turn.

### core/orchestrator/policy_router.py
Describe exactly what this file must contain:

ENUM: RouteTarget
  REALTIME_CHAT    ← default, Qwen Omni handles it
  HEAVY_VISION     ← needs camera frame + multimodal
  WEB_SEARCH       ← needs search service
  MEMORY_WRITE     ← needs memory store
  MEMORY_READ      ← needs memory retrieval
  DOCUMENT_QA      ← needs document session

DATACLASS: RoutingDecision
  target: RouteTarget
  intent: IntentCategory
  requires_frame: bool
  system_instructions: str  (injected into Qwen turn)

FUNCTION: route(intent: IntentCategory) -> RoutingDecision
  Maps each intent to RouteTarget:
    SCENE_DESCRIBE → REALTIME_CHAT, requires_frame=True
      instructions: "Describe what you see in the camera
                     image. Be specific about objects,
                     positions, and distances."
    READ_TEXT      → HEAVY_VISION, requires_frame=True
      instructions: "Read all visible text in the image.
                     Be precise and complete."
    SCAN_PAGE      → HEAVY_VISION, requires_frame=True
      instructions: "Capture and describe this document page
                     for later reference."
    WEB_SEARCH     → WEB_SEARCH, requires_frame=False
      instructions: "Search the web for this information."
    MEMORY_SAVE    → MEMORY_WRITE, requires_frame=False
      instructions: "Save this information to memory."
    MEMORY_RECALL  → MEMORY_READ, requires_frame=False
      instructions: "Recall relevant stored information."
    DOCUMENT_QA    → DOCUMENT_QA, requires_frame=False
      instructions: "Answer from the scanned document."
    GENERAL_CHAT   → REALTIME_CHAT, requires_frame=False
      instructions: ""  (no override, use default)

Guardrails for this router in Plan 05:
- This is route-selection metadata inside the existing realtime path, not a full multi-service rollout yet.
- Unimplemented targets (`WEB_SEARCH`, `MEMORY_WRITE`, `MEMORY_READ`, `DOCUMENT_QA`) may be predicted by the classifier, but the applied route in Plan 05 still falls back to current realtime chat behavior until later plans exist.
- Log both predicted route and applied route when they differ.

### core/orchestrator/prompt_builder.py
Describe what this file must contain:

FUNCTION: build_system_prompt(
    base_instructions: str,
    memory_context: str = "",
    document_context: str = "",
) -> str
  Combines base instructions with optional
  memory and document context into one
  system instruction string for Qwen turns.
  Returns combined prompt.

FUNCTION: build_search_query(transcript: str) -> str
  Extracts the search query from user speech.
  Strips phrases like "search for", "look up",
  "find online" from the beginning.
  Returns clean query string.

FUNCTION: build_memory_fact(transcript: str) -> str
  Extracts the fact to save from user speech.
  Strips phrases like "remember that",
  "save this", "note that".
  Returns clean fact string.

Implementation detail:
- `build_system_prompt()` must preserve empty-context cases cleanly and avoid leading/trailing blank sections.

### core/orchestrator/capture_coach.py
Describe what this file must contain:

FUNCTION: assess_frame_quality(
    image_jpeg_b64: str | None,
) -> tuple[bool, str]
  Returns (is_usable, guidance_message)
  If image_jpeg_b64 is None:
    return (False, "Please point the camera at something.")
  Decode base64 → check image:
    If image is too dark (mean pixel < 30):
      return (False, "Move to better lighting.")
    If image dimensions < 100x100:
      return (False, "Move closer.")
    If image is mostly uniform (std dev < 5):
      return (False, "Hold the camera still.")
  If all checks pass:
    return (True, "")

Implementation detail:
- Import PIL inside the function.
- This is only a lightweight pixel-quality gate for current-image presence/quality, not true scene understanding.

### apps/backend/api/routes/realtime.py (UPDATE)
Describe the UPDATE to existing file:

DO NOT replace the file.
ADD orchestrator integration.

Current flow:
  audio received → send to Qwen → return audio

New flow:
  audio received
  → get transcript from previous turn OR
    use current turn's gummy transcript
  → classify intent
  → get routing decision
  → if requires_frame: get pending_image_b64
  → if frame needed but none: send spoken guidance
  → build system instructions
  → send to correct handler

For Plan 05 implement only:
  Classification + routing decision logged
  system_instructions injected into Qwen turn
  REALTIME_CHAT and HEAVY_VISION routes only
  (WEB_SEARCH, MEMORY_WRITE, MEMORY_READ,
   DOCUMENT_QA left as GENERAL_CHAT fallback
   until Plans 07-09 implement those services)

Exact change:
  After receiving audio_pcm binary frame,
  BEFORE calling async_send_audio_turn:
    1. Use last_user_transcript (store it per session)
    2. If transcript available: classify intent
    3. Get routing decision
    4. If requires_frame and no pending_image_b64:
         send spoken guidance text via Qwen with
         instructions="Tell the user to point the
         camera and press the capture button."
    5. Build instructions from routing decision
    6. Pass instructions to async_send_audio_turn

Store last_user_transcript per session:
  After each turn: store result.user_transcript
  Use it on next turn for classification
  (classification runs on previous turn's transcript
   because current turn's transcript comes with
   the response, not before)

Critical realism for this update:
- Do not claim same-turn voice intent routing when there is no pre-send transcript.
- Preserve the existing websocket contract and transcript JSON schema exactly.
- If classifier fails, times out, or produces no usable label, continue with default realtime behavior silently.
- If a predicted route target is not implemented yet, log the predicted route and apply `GENERAL_CHAT` instructions instead.
- Keep existing error handling intact.

### tests/unit/test_intent_classifier.py
Tests to include (all mocked — no real API calls):

  test_classify_returns_scene_describe
    mock qwen response "SCENE_DESCRIBE"
    assert result.intent == IntentCategory.SCENE_DESCRIBE

  test_classify_returns_read_text
    mock "READ_TEXT" → IntentCategory.READ_TEXT

  test_classify_returns_general_chat_on_empty
    empty transcript → GENERAL_CHAT high, no API call

  test_classify_returns_general_chat_on_unknown
    mock "UNKNOWN_LABEL" → GENERAL_CHAT low

  test_classify_returns_general_chat_on_error
    mock API raises exception → GENERAL_CHAT low, error set

  test_from_settings_reads_api_key
    from_settings() uses DASHSCOPE_API_KEY from env

### tests/unit/test_policy_router.py
Tests to include:

  test_scene_describe_routes_to_realtime_with_frame
    route(SCENE_DESCRIBE) → REALTIME_CHAT, requires_frame=True

  test_read_text_routes_to_heavy_vision
    route(READ_TEXT) → HEAVY_VISION, requires_frame=True

  test_general_chat_no_frame_needed
    route(GENERAL_CHAT) → REALTIME_CHAT, requires_frame=False

  test_web_search_routes_correctly
    route(WEB_SEARCH) → WEB_SEARCH, requires_frame=False

  test_all_intents_have_routing
    for each IntentCategory: route() must not raise

### tests/unit/test_prompt_builder.py
Tests to include:

  test_build_system_prompt_combines_context
    base + memory_context → combined string contains both

  test_build_search_query_strips_prefix
    "search for the weather" → "the weather"
    "look up pizza recipes" → "pizza recipes"

  test_build_memory_fact_strips_prefix
    "remember my doctor is Dr Sharma" → "my doctor is Dr Sharma"

## Physical Gate Check
None for Plan 05.
Orchestrator is backend-only.
Verify with unit tests only.
No physical browser check needed until Plan 06
when heavy vision is wired.

## Implementation Notes For Hephaestus

1. qwen-turbo via DashScope compatible mode:
   import httpx
   POST https://dashscope-intl.aliyuncs.com/compatible-mode/v1/chat/completions
   headers: Authorization: Bearer {api_key}
   body: {model: "qwen-turbo", messages: [...], max_tokens: 20}
   Parse: response["choices"][0]["message"]["content"].strip()

2. IntentClassifier.classify() must be async.
   Use httpx.AsyncClient for the API call.

3. In realtime.py the classification uses
   LAST turn's transcript not current turn.
   Current turn's transcript arrives WITH the response.
   So the pattern is:
     Turn N:   receive audio → classify using turn N-1 transcript
               → send to Qwen → get transcript N
     Turn N+1: classify using transcript N

4. Capture coach is simple pixel checks.
   Import PIL inside the function.
   No heavy CV dependencies needed.

5. Do NOT refactor existing realtime.py structure.
   Only add classification before async_send_audio_turn.
   Keep existing error handling intact.

6. If classification API call fails or times out
   (set 3s timeout): fall through to GENERAL_CHAT
   silently. Never block a user turn on classification.

7. Because `QwenRealtimeClient` temporarily overrides
   instructions per turn, tests must verify instructions
   do not leak into later turns after success or failure.

---

## Self-Check
  □ 8 intent categories defined
  □ IntentClassifier uses qwen-turbo via compat mode
  □ Classification falls back gracefully on any error
  □ PolicyRouter maps all 8 intents
  □ capture_coach does pixel-based quality check
  □ realtime.py update described (not replace)
  □ last_user_transcript pattern described
  □ 14 unit tests listed across 3 test files
  □ No physical gate check (backend only)
