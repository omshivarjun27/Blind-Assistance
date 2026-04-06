---

# Plan 06 — Heavy Vision Path

## Goal
Implement the heavy vision path that sends camera frames
to qwen3.5-flash (dev) or qwen3.6-plus (exam) for:
- OCR / text reading ("read this")
- Scene analysis with more detail than realtime path
- Page capture for document sessions

This is wired into the existing routing system from Plan 05.
When PolicyRouter returns HEAVY_VISION, the route handler
calls MultimodalClient instead of Qwen Omni Realtime.

## Confirmed API Format
- Compatible-mode vision endpoint is:
  - `POST https://dashscope-intl.aliyuncs.com/compatible-mode/v1/chat/completions`
- Compatible-mode base URL is:
  - `https://dashscope-intl.aliyuncs.com/compatible-mode/v1`
- Compatible-mode vision uses OpenAI-style `messages` with a `content` array.
- Image input in compatible mode is passed with:
  - `{ "type": "image_url", "image_url": { "url": "..." } }`
- Text input in compatible mode is passed with:
  - `{ "type": "text", "text": "..." }`
- Base64 image format is supported as a Data URL:
  - `data:image/jpeg;base64,...`
- Broader DashScope vision docs confirm Base64 image input can be passed in this format and that the MIME type in the Data URL must match the actual image type.
- Base64 input image strings are documented at **<= 10MB**.
- Broader DashScope vision docs confirm the dev-profile visual-understanding model name:
  - `qwen3.5-flash`
- Current repo settings use:
  - dev vision model: `qwen3.5-flash`
  - exam vision model: `qwen3.6-plus`

UNCONFIRMED:
- The dedicated compatible-mode vision page explicitly lists Qwen-VL family models, not `qwen3.5-flash` / `qwen3.6-plus` by name.
- Broader vision docs show OpenAI-compatible image input examples with `qwen3.5-plus`, and native DashScope examples with `qwen3.5-plus` / `qwen3.5-flash`.
- Therefore the exact pairing of `qwen3.5-flash` or `qwen3.6-plus` with the compatible-mode chat-completions endpoint should be treated as a runtime-verified assumption.
- If the configured model rejects compatible-mode image input, Hephaestus must fail fast with a clear error and document the required override rather than silently falling back to another endpoint.

## Safe Deletions In This Plan
None. This plan only adds new files.

## Files To Create

### apps/backend/services/dashscope/multimodal_client.py
Describe exactly what this file must contain:

DATACLASS: VisionRequest
  image_jpeg_b64: str
  prompt: str
  model: str (from settings.QWEN_VISION_MODEL)
  max_tokens: int = 1024

DATACLASS: VisionResponse
  text: str
  error: str | None = None
  property success: bool

CLASS: MultimodalClient
  __init__(api_key: str, model: str, base_url: str)
  async analyze(request: VisionRequest) -> VisionResponse
    POST to DashScope compatible chat completions
    Message format:
      role: user
      content: array with:
        {type: "image_url", image_url: {url: "data:image/jpeg;base64,{b64}"}}
        {type: "text", text: prompt}
    Parse response["choices"][0]["message"]["content"]
    Timeout: 30 seconds
    On error: return VisionResponse(text="", error=str(exc))

  classmethod from_settings() -> MultimodalClient

Additional implementation requirements:
- Use `httpx.AsyncClient`.
- POST target must be `{base_url}/chat/completions`.
- Use `Authorization: Bearer {api_key}` and `Content-Type: application/json`.
- Use `settings.QWEN_VISION_MODEL` and `settings.DASHSCOPE_COMPAT_BASE`.
- Do not silently fall back to `DASHSCOPE_HTTP_BASE` or the native DashScope endpoint.
- Reject or fail clearly if `image_jpeg_b64` is empty.
- Reject or fail clearly if the constructed Data URL exceeds the documented 10MB Base64 limit.

### core/vision/live_scene_reader.py
Describe what this file must contain:

FUNCTION: read_scene(
    image_jpeg_b64: str,
    client: MultimodalClient,
    detail_level: str = "standard",
) -> str
  Builds prompt based on detail_level:
    "standard": "Describe what you see. Be specific about
                  objects, their positions, and distances.
                  Keep it brief for a blind user."
    "detailed": "Describe everything visible in detail."
  Calls client.analyze(VisionRequest(image_b64, prompt))
  Returns text or error fallback string

### core/vision/page_reader.py
Describe what this file must contain:

FUNCTION: read_text_from_image(
    image_jpeg_b64: str,
    client: MultimodalClient,
) -> str
  Prompt: "Read all text visible in this image.
           Return the exact text, nothing else.
           If no text is visible, say 'No text found'."
  Calls client.analyze(VisionRequest(image_b64, prompt))
  Returns text content

FUNCTION: summarize_page(
    image_jpeg_b64: str,
    client: MultimodalClient,
    page_number: int = 1,
) -> str
  Prompt: "This is page {page_number} of a document.
           Describe its content: main topic, key points,
           any important numbers, dates, or names."
  Returns page summary string

### core/vision/framing_judge.py
Describe what this file must contain:

FUNCTION: get_framing_guidance(
    image_jpeg_b64: str,
    client: MultimodalClient,
) -> tuple[bool, str]
  Sends image to multimodal model with prompt:
    "Is this image clear and readable?
     Reply with YES or NO followed by one sentence
     of guidance if NO.
     Example: NO - The image is too blurry."
  Parse response:
    Starts with YES → return (True, "")
    Starts with NO → return (False, guidance_text)
    Unexpected → return (True, "")

Note: This is model-based framing check.
capture_coach.py does pixel-based pre-check.
framing_judge.py does model-based post-check.
Use capture_coach first (cheap), framing_judge
only if capture_coach passes but quality uncertain.

### apps/backend/api/routes/realtime.py (UPDATE)
DO NOT replace the file.
ADD heavy vision handling.

When routing decision is HEAVY_VISION:
  Check capture_coach.assess_frame_quality(pending_image_b64)
  If not usable: send guidance as Qwen spoken response
  If usable:
    Call multimodal_client.analyze(VisionRequest(...))
    Convert text response to speech via Qwen Omni
    (send text as instructions with short silent PCM)
    Return audio to browser as normal

Exact pattern:
  if decision.target == RouteTarget.HEAVY_VISION:
      from core.orchestrator.capture_coach import assess_frame_quality
      is_usable, guidance = assess_frame_quality(pending_image_b64)
      if not is_usable:
          effective_instructions = (
              f"Tell the user: {guidance}"
          )
          # Fall through to normal Qwen turn with guidance
      else:
          vision_result = await mm_client.analyze(
              VisionRequest(
                  image_jpeg_b64=pending_image_b64,
                  prompt=decision.system_instructions,
              )
          )
          if vision_result.success:
              effective_instructions = (
                  f"Say exactly this to the user: "
                  f"{vision_result.text}"
              )
          else:
              effective_instructions = (
                  "Tell the user the image could not "
                  "be analyzed. Ask them to try again."
              )

Add multimodal_client creation per session
alongside the existing classifier creation.

Critical routing details for this update:
- `capture_coach.assess_frame_quality()` must gate the heavy-vision HTTP call; if it fails, `MultimodalClient.analyze()` must not run.
- Spoken output still uses the existing Omni audio path.
- Heavy vision does not itself produce speech; it returns text that is handed off to the existing Omni response path.
- Do not analyze the same image twice in the core Plan 06 path.
- `framing_judge.py` is not wired into `realtime.py` in Plan 06.

### tests/unit/test_heavy_vision.py
Tests to include (all mocked — no real API calls):

  test_multimodal_client_analyze_success
    Mock httpx POST returns text response
    VisionResponse.text == expected text
    VisionResponse.success == True

  test_multimodal_client_analyze_on_error
    Mock httpx raises exception
    VisionResponse.error is not None
    VisionResponse.success == False

  test_multimodal_client_image_in_request
    Mock captures request body
    Assert "image_url" in content array
    Assert "data:image/jpeg;base64," prefix in url

  test_read_scene_returns_description
    Mock client.analyze returns "A table with a laptop"
    read_scene() returns that string

  test_read_text_from_image_returns_text
    Mock client.analyze returns "STOP"
    read_text_from_image() returns "STOP"

  test_summarize_page_includes_page_number
    Mock captures prompt sent to client
    Assert "page 2" in prompt when page_number=2

  test_framing_judge_yes_response
    Mock returns "YES the image is clear"
    get_framing_guidance() returns (True, "")

  test_framing_judge_no_response
    Mock returns "NO - Image is too blurry"
    get_framing_guidance() returns (False, guidance)

## Physical Gate Check
GATE A — "Read this" with camera:
  Start backend + frontend
  Point camera at printed text (phone/paper/screen)
  Press Capture button → then say "read this"
  Must hear: the text read aloud by Cherry voice
  Logs must show: HEAVY_VISION route taken

GATE B — Blurry frame guidance:
  Cover lens partially → press Capture → say "read this"
  Must hear capture coach guidance
  ("Move closer" or "Hold still" etc.)
  Must NOT attempt to read unreadable frame

## Implementation Notes For Hephaestus

1. Image format in DashScope compatible mode:
   content: [
     {
       "type": "image_url",
       "image_url": {
         "url": f"data:image/jpeg;base64,{image_jpeg_b64}"
       }
     },
     {
       "type": "text",
       "text": prompt
     }
   ]

2. MultimodalClient uses DASHSCOPE_COMPAT_BASE
   (not DASHSCOPE_HTTP_BASE).
   Compatible mode supports vision in this format.

3. Heavy vision converts text → speech via existing
   Qwen Omni turn with effective_instructions.
   This reuses the existing audio pipeline.
   No new TTS service needed.

4. multimodal_client instance per WebSocket session
   in realtime.py — same pattern as classifier.
   Do not create module-level shared clients.

5. capture_coach.assess_frame_quality runs BEFORE
   calling multimodal_client.
   It is cheap (pixel check).
   Do not call multimodal for clearly bad frames.

6. framing_judge is optional enhancement.
   Not required in Plan 06 core path.
   Include the file but do not wire into realtime.py yet.

---

## Self-Check
  □ MultimodalClient uses compatible mode base URL
  □ Image format: data:image/jpeg;base64,... in content array
  □ Heavy vision text → speech via Qwen instructions
  □ capture_coach runs before multimodal call
  □ realtime.py update described (not replace)
  □ 8 unit tests listed
  □ 2 physical gate checks require real camera
  □ framing_judge described but not required in core path
