---

# Plan 02 — DashScope Realtime Client

## Goal
Create the Python WebSocket client that connects to
DashScope qwen3.5-omni-plus-realtime.
This is the single most important file in the project.
Everything else depends on it working correctly.

## Confirmed Protocol (from DashScope docs)
- WebSocket URL format is:
  - Beijing: `wss://dashscope.aliyuncs.com/api-ws/v1/realtime?model=<model-name>`
  - Singapore: `wss://dashscope-intl.aliyuncs.com/api-ws/v1/realtime?model=<model-name>`
- Authorization header format is:
  - `Authorization: Bearer DASHSCOPE_API_KEY`
- `session.update` is the documented client event used to configure the realtime session.
- Official `session.update` examples include these session fields:
  - `modalities: ["text", "audio"]`
  - `voice: "Cherry"` (example voice)
  - `instructions: <string>`
  - `input_audio_format: "pcm"`
  - `output_audio_format: "pcm"`
  - `turn_detection: {...}` for VAD mode
- Manual mode is explicitly documented by setting:
  - `session.turn_detection = null`
- Documented client-side input events for this flow:
  - `input_audio_buffer.append`
  - `input_image_buffer.append`
  - `input_audio_buffer.commit`
  - `response.create`
- Documented server-side events / lifecycle entries for this flow:
  - `session.created`
  - `session.updated`
  - `input_audio_buffer.committed`
  - `conversation.item.input_audio_transcription.completed`
  - `response.audio_transcript.delta`
  - `response.audio_transcript.done`
  - `response.audio.delta`
  - `response.audio.done`
  - `response.done`
- Official sample code also handles `error` events.
- Input audio is documented/sample-coded as PCM at 16kHz, 16-bit, mono.
- Official examples use `mic.read(3200, ...)`, and the docs/examples describe this as 3200 bytes = 100ms at 16kHz / 16-bit mono.
- Output playback in official examples is PCM at 24kHz, 16-bit, mono.
  - NOTE: CONFIRMED FROM OFFICIAL EXAMPLE CODE / SDK EXAMPLES.
  - NOTE: UNCONFIRMED AS A FORMAL PROTOCOL-INVARIANT FIELD SEPARATE FROM `output_audio_format: pcm`.
- Images are sent with event name:
  - `input_image_buffer.append`
- Image payload format in official examples is Base64 image data in the `image` field.
- Official image guidance says:
  - format must be JPG or JPEG
  - single image should be under 500KB
  - recommended resolution is 480p or 720p
  - maximum supported resolution is 1080p
  - send images at no more than about 1 frame per second
  - at least one `input_audio_buffer.append` must be sent before any `input_image_buffer.append`
- Input transcription is configured in official examples as:
  - `input_audio_transcription: { "model": "gummy-realtime-v1" }`
  - or SDK equivalent `input_audio_transcription_model='gummy-realtime-v1'`
- Session max lifetime is explicitly documented as:
  - **120 minutes**
- After 120 minutes, server closes the WebSocket automatically.
- NOTE: UNCONFIRMED — DashScope docs do not document a resume token or session-resume mechanism.
- NOTE: UNCONFIRMED — reconnect behavior is not formally specified as “full new session, no resume”, but that is the safe planning assumption because only fresh connection + fresh `session.created` / `session.update` flows are documented.

## Safe Deletions In This Plan
None. This plan only adds new files.

## Files To Create

### apps/backend/services/dashscope/realtime_client.py
This is the main deliverable.

Describe exactly what this file must contain:

CLASS: QwenRealtimeClient
  __init__(config: QwenRealtimeConfig)
  connect() -> None
    Opens WebSocket to DashScope
    Waits for session.created
    Sends session.update
    Waits for session.updated
    Sets self._connected = True
    Records self._session_start_time
  close() -> None
    Closes WebSocket gracefully
  needs_reconnect() -> bool
    Returns True if session age > 110 minutes
  reconnect() -> None
    Calls close() then connect()
    Note: new session, context NOT preserved
    NOTE: UNCONFIRMED whether server offers any resume semantics; this plan assumes none
  ensure_connected() -> None
    Calls connect() if not connected
    Calls reconnect() if needs_reconnect()
  send_audio_turn(
      audio_pcm: bytes,
      image_jpeg_b64: str | None = None,
      instructions: str | None = None,
  ) -> QwenRealtimeTurn
    SYNC method:
    1. ensure_connected()
    2. If instructions: send updated session.update, wait session.updated
    3. Stream audio in 3200-byte chunks via input_audio_buffer.append
    4. If image: send input_image_buffer.append AFTER first audio chunk
    5. Send input_audio_buffer.commit
    6. Wait for input_audio_buffer.committed
    7. Send response.create
    8. Collect events until response.done:
         - conversation.item.input_audio_transcription.completed
         - response.audio_transcript.delta / done
         - response.audio.delta / done
         - response.done
         - error
    9. Return QwenRealtimeTurn result
  async_send_audio_turn(
      audio_pcm: bytes,
      image_jpeg_b64: str | None = None,
      instructions: str | None = None,
  ) -> QwenRealtimeTurn
    Async wrapper using run_in_executor

CLASS: QwenRealtimeConfig
  api_key: str
  model: str (default from settings.QWEN_REALTIME_MODEL)
  endpoint: str (default from settings.DASHSCOPE_REALTIME_URL)
  voice: str (default "Cherry")
  audio_in_rate: int = 16000
  audio_out_rate: int = 24000
  chunk_bytes: int = 3200
  response_timeout_s: float = 60.0
  classmethod from_settings() -> QwenRealtimeConfig

DATACLASS: QwenRealtimeTurn
  user_transcript: str = ""
  assistant_transcript: str = ""
  assistant_audio_pcm: bytes = b""
  usage: dict = field(default_factory=dict)
  error: str | None = None
  property success: bool

FUNCTION: make_silent_pcm(duration_s: float = 0.5) -> bytes
  Returns silent PCM at 16kHz 16-bit mono
  For image-only turns (image requires audio first)
  = b"\x00\x00" * int(duration_s * 16000)

FUNCTION: compress_image_for_realtime(
    image_input,
    max_bytes: int = 500 * 1024,
) -> str | None
  Accepts numpy array, PIL Image, or file path
  Compresses to JPEG base64 < 500KB
  Tries qualities: 92, 88, 84, 80, 75, 70, 65, 60
  Returns None if compression fails

Additional implementation requirements for `realtime_client.py`:
- Use `import websocket` from the `websocket-client` package already present in `requirements.txt`
- Build the connection URL by appending `?model=<configured model>` to `settings.DASHSCOPE_REALTIME_URL`
- Do not require any new environment variables beyond those already used in `settings.py` and `tests/conftest.py`
- Support only the documented manual-turn flow in this plan; VAD mode is explicitly out of scope for this file’s first implementation
- Parse and preserve the latest `session_id` from `session.created`
- Parse `usage` from `response.done` when present
- Treat `error` event as terminal for the active turn and populate `QwenRealtimeTurn.error`
- Never perform a real network call in unit tests

### tests/unit/test_realtime_client.py
Describe exactly what tests must be written.
Tests use WebSocket mocks only — no real network.

Tests to include:
  test_config_defaults
    QwenRealtimeConfig defaults match settings
    model contains "realtime"
    endpoint starts with "wss://"
    audio_in_rate = 16000, audio_out_rate = 24000

  test_config_from_settings
    from_settings() reads DASHSCOPE_API_KEY
    raises ValueError when key missing

  test_turn_success_property
    error=None → success=True
    error="timeout" → success=False

  test_make_silent_pcm
    0.5s → 16000 bytes
    1.0s → 32000 bytes
    bytes are all zeros

  test_session_update_payload_structure
    mock ws.send captures JSON
    type == "session.update"
    session.voice == "Cherry"
    session.input_audio_format == "pcm"
    session.output_audio_format == "pcm"
    session.turn_detection is None

  test_audio_sent_before_image
    mock send captures event types in order
    input_audio_buffer.append appears before
    input_image_buffer.append

  test_commit_sent_after_audio
    input_audio_buffer.commit appears after
    all input_audio_buffer.append events

  test_response_create_sent_after_commit
    response.create appears after
    input_audio_buffer.commit

  test_needs_reconnect_fresh_session
    session_start_time = now → False

  test_needs_reconnect_old_session
    session_start_time = now - 111*60 → True

  test_compress_image_under_500kb
    numpy array → JPEG base64
    decoded bytes < 500 * 1024

  test_compress_image_returns_none_on_failure
    invalid input → None, no exception raised

## Verification Steps For Hephaestus

STEP A — Import test:
  python -c "
  from apps.backend.services.dashscope.realtime_client import (
      QwenRealtimeClient,
      QwenRealtimeConfig,
      QwenRealtimeTurn,
      make_silent_pcm,
      compress_image_for_realtime,
  )
  print('IMPORT OK')
  cfg = QwenRealtimeConfig.from_settings()
  print('Model:', cfg.model)
  print('Endpoint:', cfg.endpoint)
  silent = make_silent_pcm(0.5)
  print('Silent PCM bytes:', len(silent))
  assert len(silent) == 16000
  print('ALL CHECKS PASS')
  "

STEP B — Unit tests:
  pytest tests/unit/test_realtime_client.py -v --timeout=30 -x
  Expected: 12 passed 0 failed

STEP C — Regression:
  pytest tests/unit/test_settings.py -v --timeout=30 -x
  Expected: 7 passed 0 failed

## Gate Check (physical)
None for this plan.
The realtime client connects to DashScope WebSocket.
A full audio turn test will be verified in Plan 03
when the FastAPI route is wired.

## Implementation Notes For Hephaestus

1. websocket-client library is already installed
   Import: import websocket
   NOT: from websockets import ...
   These are different packages.

2. websocket.create_connection() is synchronous.
   Use asyncio.get_event_loop().run_in_executor()
   in async_send_audio_turn to avoid blocking.

3. The image must be sent AFTER the first audio chunk.
   DashScope docs/examples say at least one audio append
   must occur before any image append.

4. Empty recv() guard:
   raw = ws.recv()
   if not raw or not raw.strip():
       continue  # skip empty messages
   event = json.loads(raw)

5. Session.update must include turn_detection: null
   Not "none" string — actual JSON null.

6. make_silent_pcm is used for image-only turns.
   When user asks "read this" with no speech,
   send silent audio + image frame together.

7. Do not import PIL at module level.
   Import inside compress_image_for_realtime only.
   This prevents import errors when pillow not needed.

8. QwenRealtimeConfig.from_settings() should call
   get_api_key() which raises ValueError if not set.
   Tests mock this via conftest.py env var.

9. Use current repo defaults exactly unless explicitly overridden:
   - endpoint default from `settings.DASHSCOPE_REALTIME_URL`
   - model default from `settings.QWEN_REALTIME_MODEL`
   - transcription model default from `settings.QWEN_TRANSCRIPTION_MODEL`

10. Reconnect policy in this plan is freshness-first:
    on old session or closed socket, open a new WebSocket,
    wait for `session.created`, resend `session.update`,
    and proceed with a new turn.
    NOTE: UNCONFIRMED whether DashScope supports any session resume.

11. `audio_out_rate = 24000` and `chunk_bytes = 3200`
    match official examples and current intended client behavior.
    NOTE: UNCONFIRMED whether those are immutable server requirements
    versus documented example/default behavior.

---

## 4. Self-Check
  □ Protocol matches DashScope docs (or marked UNCONFIRMED)
  □ make_silent_pcm described correctly (16000 bytes for 0.5s)
  □ Image sent after audio (documented as required)
  □ Empty recv guard included in implementation notes
  □ websocket-client (not websockets) noted
  □ 12 unit tests listed
  □ No network calls in unit tests
  □ Gate check honest (none for this plan)
  □ Regression test included
