---

# Plan 03 — FastAPI WebSocket Route

## Goal
Create the /ws/realtime WebSocket endpoint that:
1. Accepts browser audio (and optional camera frames)
2. Routes audio to QwenRealtimeClient
3. Returns Qwen's spoken audio response to browser
4. Handles session lifecycle and disconnects

This is the first plan with a physical gate check:
user opens browser, speaks, hears the model-appropriate default voice.

## Audio Format Note
- `getUserMedia()` gives the browser a `MediaStream`, not raw bytes by itself.
- If the frontend uses `MediaRecorder(stream)`, browser output is recorded as encoded `Blob` chunks in the browser's default container/codec format rather than raw PCM.
- MDN's recording example finalizes recorded audio as `audio/ogg; codecs=opus`.
- Therefore, if the frontend uses MediaRecorder-style chunks, the backend must transcode encoded browser audio before sending it to DashScope.
- `decodeAudioData()` is not a valid streaming primitive for arbitrary PCM fragments because it operates on complete audio file data, not fragments.
- For this plan, the backend contract is intentionally narrowed to **binary WebSocket frames containing one complete turn of raw PCM audio**.
- That means **no backend transcoding is in scope for Plan 03**.
- Plan 04 frontend must intentionally capture and send PCM (for example via Web Audio / AudioWorklet / equivalent browser-side PCM extraction path) if it wants to use this route contract directly.
- If the frontend later chooses MediaRecorder default chunks instead, a separate backend transcoder will be required before DashScope.
- UNCONFIRMED: exact default browser MediaRecorder MIME/container is not guaranteed to be identical across browsers.
- UNCONFIRMED: exact PCM extraction implementation choice on the frontend is deferred to Plan 04.

## Safe Deletions In This Plan
None. This plan only adds new files.

## Files To Create

### apps/backend/api/routes/realtime.py

Describe what this file must contain:

WebSocket route: GET /ws/realtime
  - Accepts WebSocket connection
  - Creates QwenRealtimeClient per session
  - Receives messages from browser:
      binary frames = one complete audio turn of raw PCM bytes
      text frames = JSON control messages
        {"type": "image", "data": "<base64 jpeg>"}
        {"type": "instructions", "text": "..."}
        {"type": "ping"}
  - On audio received:
      Call client.async_send_audio_turn(
          audio_pcm,
          pending_image_b64,
          pending_instructions,
      )
      Send result.assistant_audio_pcm back as binary frame
      Send result.assistant_transcript as text JSON:
        {"type": "transcript", "text": "...", "role": "assistant"}
      Send user transcript as text JSON:
        {"type": "transcript", "text": "...", "role": "user"}
      After dispatch, reset:
        pending_image_b64 = None
        pending_instructions = None
  - On ping control message:
      Send text JSON:
        {"type": "pong"}
  - On disconnect: close QwenRealtimeClient
  - On error: log, close gracefully

Session state per connection:
  pending_image_b64: str | None
  pending_instructions: str | None

Route behavior details that must be specified in the implementation:
  - The route is request/response over WebSocket, not full-duplex live upstream streaming.
  - Each binary frame is treated as one full user audio turn.
  - `pending_image_b64` applies to the next audio turn only.
  - `pending_instructions` applies to the next audio turn only.
  - If the browser disconnects before a turn completes, close the DashScope client and end the session cleanly.
  - Use FastAPI `WebSocketDisconnect` handling for normal disconnect path.
  - If invalid JSON is received in a text frame, log it and close gracefully.
  - If an unknown control message type is received, log it and close gracefully.
  - Use one lazy-created QwenRealtimeClient per WebSocket session; do not create any shared module-level client.

### apps/backend/main.py (UPDATE — not replace)
Add router import and include:
  from apps.backend.api.routes import realtime as realtime_route
  app.include_router(realtime_route.router)

Describe exactly where to add these lines.
Do not replace existing content.

Exact placement:
  - Add the router import immediately after the existing line:
      `from shared.config.settings import get_config, APP_HOST, APP_PORT, DEBUG`
  - Add `app.include_router(realtime_route.router)` immediately after the existing `app.add_middleware(...)` block
  - Place the include_router line before the first existing route decorator `@app.get("/health")`
  - Preserve all existing logging, FastAPI app construction, middleware, `/health`, `/config`, and `uvicorn.run(...)` code unchanged

### tests/unit/test_realtime_route.py

Tests to include (all mocked — no real network):

  test_health_endpoint_still_works
    GET /health returns 200 and status ok
    Regression check after router added

  test_websocket_route_exists
    WebSocket /ws/realtime route is registered
    Check app.routes for websocket path

  test_websocket_audio_calls_qwen_client
    Mock QwenRealtimeClient.async_send_audio_turn
    Send binary frame to /ws/realtime
    Assert async_send_audio_turn was called
    Assert binary audio response returned

  test_websocket_returns_transcript_json
    Mock turn with assistant_transcript="hello"
    Send binary frame
    Assert text frame received with
    {"type": "transcript", "role": "assistant", "text": "hello"}

  test_websocket_handles_image_control_message
    Send text JSON {"type": "image", "data": "abc123"}
    Assert pending_image_b64 is set to "abc123"
    Next audio turn should use this image

  test_websocket_handles_disconnect_gracefully
    Connect then disconnect immediately
    Assert no exception raised
    Assert client.close() was called

Testing approach requirements:
  - Use FastAPI/Starlette test client WebSocket support only
  - Mock QwenRealtimeClient construction and async_send_audio_turn results
  - Do not perform any real DashScope network calls in unit tests
  - Do not require browser microphone access in unit tests

## Physical Gate Check (human verified)
This plan's gate requires Om to physically verify.

GATE A — Backend WebSocket starts:
  Start: uvicorn apps.backend.main:app --host 127.0.0.1 --port 8000
  Check: no startup errors
  Check: /health returns 200

GATE B — Simple WebSocket smoke test:
  python -c "
  import asyncio, websockets, json

  async def test():
      uri = 'ws://127.0.0.1:8000/ws/realtime'
      async with websockets.connect(uri) as ws:
          from apps.backend.services.dashscope.realtime_client import make_silent_pcm
          silent = make_silent_pcm(0.5)
          await ws.send(silent)
          response = await asyncio.wait_for(ws.recv(), timeout=30)
          if isinstance(response, bytes):
              print('Audio response received:', len(response), 'bytes')
              print('GATE B PASS')
          else:
              data = json.loads(response)
              print('JSON response:', data)
              print('GATE B PASS if no error')

  asyncio.run(test())
  "
  Expected: audio bytes received from Qwen
  This is the first real DashScope turn in the project.

GATE C — Log cleanliness:
  Startup logs must show a successful realtime session log for the active model voice.
  For the current `qwen3.5-omni-plus-realtime` setup, expect:
    "Realtime session ready: voice=Tina"
  Must NOT show:
    Any localhost:11434 reference
    Any Deepgram/ElevenLabs reference

## Implementation Notes For Hephaestus

1. FastAPI WebSocket route:
   from fastapi import WebSocket, WebSocketDisconnect
   @router.websocket("/ws/realtime")
   async def realtime_endpoint(ws: WebSocket):
       await ws.accept()
       ...

2. Receiving from browser:
   data = await ws.receive()
   if data["type"] == "websocket.receive":
       if "bytes" in data and data["bytes"]:
           # binary = one complete PCM audio turn
       elif "text" in data and data["text"]:
           # text = JSON control message

3. Browser audio format:
   - Browser microphone capture does not arrive as raw PCM automatically.
   - `getUserMedia()` gives a MediaStream.
   - `MediaRecorder(stream)` yields encoded Blob chunks in the browser's default format, not raw PCM.
   - Therefore this route contract assumes the frontend does NOT use MediaRecorder for `/ws/realtime`.
   - Frontend must send raw PCM frames extracted with Web Audio / AudioWorklet / equivalent.
   - If MediaRecorder is used instead, backend transcoding is needed before DashScope.
   - That transcoding path is out of scope for Plan 03.
   - UNCONFIRMED: exact browser default container/codec across all supported browsers.

4. Sending binary audio back:
   await ws.send_bytes(result.assistant_audio_pcm)

5. Sending JSON transcript:
   await ws.send_text(json.dumps({
       "type": "transcript",
       "role": "assistant",
       "text": result.assistant_transcript,
   }))

6. Session cleanup on disconnect:
   try:
       ... main loop ...
   except WebSocketDisconnect:
       client.close()
   except Exception as exc:
       logger.error("WebSocket error: %s", exc)
       client.close()

7. QwenRealtimeClient is synchronous.
   Call async_send_audio_turn which uses run_in_executor.
   Do NOT call send_audio_turn directly in async context.

8. Image accumulation:
   Store pending_image_b64 = None at session start.
   When {"type":"image","data":"..."} received:
       pending_image_b64 = data["data"]
   On next audio turn:
       pass pending_image_b64 to async_send_audio_turn
       then reset: pending_image_b64 = None

9. Instructions accumulation:
   Store pending_instructions = None at session start.
   When {"type":"instructions","text":"..."} received:
       pending_instructions = data["text"]
   On next audio turn:
       pass pending_instructions to async_send_audio_turn
       then reset: pending_instructions = None

10. WebSocket state handling:
    FastAPI exposes `client_state` and `application_state`.
    Use normal exception handling for disconnects and avoid sending after close.

---

## Self-Check
  □ Router describes /ws/realtime WebSocket route
  □ Binary frames = audio, text frames = JSON control
  □ Image accumulation before audio turn described
  □ QwenRealtimeClient lifecycle: one per session
  □ Disconnect handled gracefully
  □ main.py update described (not replace)
  □ 6 unit tests listed
  □ Physical gate check B requires real DashScope call
  □ Audio format note from docs research included
