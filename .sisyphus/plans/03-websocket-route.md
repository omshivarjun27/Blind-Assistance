---

# Plan 03 — FastAPI WebSocket Route

## Goal
Create the /ws/realtime WebSocket endpoint that:
1. Accepts browser audio (and optional camera frames)
2. Routes audio to QwenRealtimeClient
3. Returns Qwen's spoken audio response to browser
4. Handles session lifecycle and disconnects

This is the first plan with a physical gate check:
user opens browser, speaks, hears Cherry voice.

## Audio Format Note
- `getUserMedia()` gives the browser a `MediaStream`, not bytes on the wire.
- If the frontend uses `MediaRecorder`, the browser emits encoded `Blob` chunks in a browser-selected container/codec, not raw PCM. Common outcomes are Opus in WebM/Ogg, but the exact default is browser-dependent and therefore UNCONFIRMED unless the frontend forces `mimeType`.
- DashScope realtime expects PCM input, so backend transcoding is required if the frontend sends MediaRecorder chunks.
- For this plan, the safer approach is: browser mic → Web Audio / AudioWorklet → Float32 samples → convert/resample in the browser to 16kHz 16-bit mono PCM → send binary PCM bytes over WebSocket.
- In that browser-side PCM path, the backend does not transcode; it forwards PCM bytes to QwenRealtimeClient.
- `decodeAudioData()` is for complete encoded audio file data, not arbitrary live fragments, so it is not a good primary backend strategy for realtime MediaRecorder chunk handling.
- UNCONFIRMED:
  - exact default browser codec/container when `MediaRecorder` is created without explicit `mimeType`
  - exact browser audio callback chunk size when using AudioWorklet/Web Audio

## Safe Deletions In This Plan
None. This plan only adds new files.

## Files To Create

### apps/backend/api/routes/realtime.py

Describe what this file must contain:

WebSocket route: GET /ws/realtime
  - Accepts WebSocket connection
  - Creates QwenRealtimeClient per session
  - Receives messages from browser:
      binary frames = audio PCM bytes
      text frames = JSON control messages
        {"type": "image", "data": "<base64 jpeg>"}
        {"type": "instructions", "text": "..."}
        {"type": "ping"}
  - On audio received:
      Call client.async_send_audio_turn(audio_pcm, image_b64)
      Send result.assistant_audio_pcm back as binary frame
      Send result.assistant_transcript as text JSON:
        {"type": "transcript", "text": "...", "role": "assistant"}
      Send user transcript as text JSON:
        {"type": "transcript", "text": "...", "role": "user"}
  - On disconnect: close QwenRealtimeClient
  - On error: log, close gracefully

Session state per connection:
  pending_image_b64: str | None
  pending_instructions: str | None

Additional planning notes for this file:
  - Use `APIRouter()` even though the repo does not yet use routers; this becomes the first route module under `apps/backend/api/routes/`.
  - Use `await ws.accept()` before entering the loop.
  - Prefer `await ws.receive()` so the handler can distinguish binary frames (`bytes`) from text JSON frames (`text`) in one loop.
  - On binary audio frames, treat payload as already-normalized PCM16 mono bytes for DashScope.
  - On `{"type": "image", ...}` store image only for the next audio turn, then clear it after the turn finishes.
  - On `{"type": "instructions", ...}` store instruction override only for the next audio turn, then clear it after the turn finishes.
  - On `{"type": "ping"}` respond with text JSON such as `{"type": "pong"}` so browser keepalive is explicit.
  - If `result.error` is set, send text JSON `{"type": "error", "message": ...}` and keep shutdown graceful.
  - Import path should reuse the existing service client directly from `apps.backend.services.dashscope.realtime_client`.

### apps/backend/main.py (UPDATE — not replace)
Add router import and include:
  from apps.backend.api.routes import realtime as realtime_route
  app.include_router(realtime_route.router)

Describe exactly where to add these lines.
Do not replace existing content.

Placement notes:
  - Add the import in the existing import block after FastAPI/CORS imports and before or alongside the `shared.config.settings` import so imports stay grouped at top-of-file.
  - Add `app.include_router(realtime_route.router)` after the existing `app.add_middleware(...)` block and before the `/health` route so router wiring happens once during startup.
  - Keep `/health` and `/config` unchanged.

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

Additional testing notes:
  - This becomes the repo’s first FastAPI route-level websocket test file.
  - Use FastAPI/Starlette `TestClient` websocket support for route tests; that is a new pattern in this repo and should be called out in implementation.
  - Keep all QwenRealtimeClient behavior mocked; tests should verify route wiring, message handling, and cleanup only.
  - Continue to rely on `tests/conftest.py` for env defaults instead of introducing new fixtures unless strictly necessary.

## Physical Gate Check (human verified)
This plan's gate requires Om to physically verify.

GATE A — Backend WebSocket starts:
  Start: uvicorn apps.backend.main:app --host 127.0.0.1 --port 8000
  Check: no startup errors
  Check: /health returns 200

GATE B — Simple WebSocket smoke test:
  python -c "
  import json, websocket
  from apps.backend.services.dashscope.realtime_client import make_silent_pcm

  ws = websocket.create_connection('ws://127.0.0.1:8000/ws/realtime', timeout=30)
  try:
      silent = make_silent_pcm(0.5)
      ws.send_binary(silent)
      response = ws.recv()
      if isinstance(response, bytes):
          print('Audio response received:', len(response), 'bytes')
          print('GATE B PASS')
      else:
          data = json.loads(response)
          print('JSON response:', data)
          print('GATE B PASS if no error')
  finally:
      ws.close()
  "
  Expected: audio bytes received from Qwen
  This is the first real DashScope turn in the project.

GATE C — Log cleanliness:
  After Gate B, logs must show:
    "Realtime session ready: voice=Cherry"
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
           # binary = audio PCM
       elif "text" in data and data["text"]:
           # text = JSON control message

3. Browser audio format:
   Browser mic capture does not produce raw bytes on its own.
   If frontend uses MediaRecorder, the backend will receive encoded/containerized chunks and must transcode to PCM before DashScope.
   For this plan, the route should assume the frontend sends PCM bytes directly over WebSocket binary frames.
   That implies browser-side conversion/resampling (for example via AudioWorklet/Web Audio) to 16kHz 16-bit mono PCM before `ws.send(...)`.
   Exact browser default MediaRecorder codec/container is UNCONFIRMED and should not be assumed.

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
