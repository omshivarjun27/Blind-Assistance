# Plan 08 — Barge-In and True Interruption Support

## Section 1 — Identity / Role

You are Prometheus. Write plan only.
No code. No edits to `.py` or `.js/.ts/.tsx` files.
One output: `.sisyphus/plans/08-barge-in-interruption.md`
One commit: the plan file only.

## Section 2 — Context (what is true right now)

Plans completed:
  00 master plan
  01 scaffold
  02 realtime client
  03 websocket route
  04 frontend capture
  05 orchestrator + intent router
  06 heavy vision
  06b heavy vision fixes
  07 memory layer

Current barge-in state (confirmed from repo + docs pass):
  DONE — protocol level:
    - `session.update` already sends `server_vad` with
      `threshold=0.5`, `silence_duration_ms=500`,
      `prefix_padding_ms=300`, `interrupt_response=True`
    - `turn_detection: None` is already gone in current config

  BROKEN — architectural level:
    - Frontend `AudioWorklet` capture is live, but `useRealtimeSession.ts`
      buffers a full turn before sending anything to backend
    - Frontend explicitly ignores mic chunks while assistant audio is playing
    - Frontend sends one complete binary blob per turn, not a live chunk stream
    - Backend `/ws/realtime` still treats one binary websocket frame as one full turn
    - Backend forwards that full turn to `async_send_audio_turn(...)`, not chunk-by-chunk
    - Frontend does not play `response.audio.delta` progressively; it plays one full blob after completion
    - No explicit interrupt / cancel control path exists between frontend and backend today

## Section 3 — Codebase Read Step

### Step 1: Read before planning — findings

Files read completely:
- `C:/ally-vision-v2/apps/frontend/app/page.tsx`
- `C:/ally-vision-v2/apps/frontend/hooks/useMicStream.ts`
- `C:/ally-vision-v2/apps/frontend/hooks/useRealtimeSession.ts`
- `C:/ally-vision-v2/apps/frontend/lib/ws-client.ts`
- `C:/ally-vision-v2/apps/frontend/lib/audio-utils.ts`
- `C:/ally-vision-v2/apps/frontend/public/worklets/mic-processor.js`
- `C:/ally-vision-v2/apps/backend/api/routes/realtime.py`
- `C:/ally-vision-v2/apps/backend/services/dashscope/realtime_client.py`

Directory listing summary for `apps/frontend/`:
- Source files present:
  - `app/page.tsx`
  - `app/layout.tsx`
  - `app/globals.css`
  - `components/camera-view.tsx`
  - `components/control-bar.tsx`
  - `components/status-pill.tsx`
  - `components/ui/button.tsx`
  - `hooks/useCameraCapture.ts`
  - `hooks/useMicStream.ts`
  - `hooks/useRealtimeSession.ts`
  - `lib/audio-utils.ts`
  - `lib/ws-client.ts`
  - `lib/utils.ts`
  - `public/worklets/mic-processor.js`
- Project files present:
  - `package.json`
  - `package-lock.json`
  - `tsconfig.json`
  - `components.json`
  - `eslint.config.mjs`
  - `postcss.config.mjs`
  - `.env.local`
  - `.gitignore`
- Non-source/build/vendor dirs present:
  - `.next/`
  - `node_modules/`

### 1) `apps/frontend/app/page.tsx`

How mic audio is captured:
- `page.tsx` does not capture mic directly.
- It delegates to `useRealtimeSession(camera.captureFrame)` at line `13`.
- Actual mic capture is in `hooks/useMicStream.ts`.

Where audio is sent to backend:
- Not in `page.tsx` directly.
- `page.tsx` wires `useRealtimeSession`, which sends audio via the websocket client.

Is mic muted/stopped while assistant audio plays?
- In `page.tsx`: not directly.
- Actual suppression is in `useRealtimeSession.ts:74`
  - `if (isSpeakingRef.current) return; // don't capture while assistant speaks`

How assistant audio is received and played:
- Not in `page.tsx` directly.
- `useRealtimeSession.ts:115-129` receives assistant audio callback and calls `playPcmAudio(pcm)`.

### 2) Frontend hooks / websocket path

Hooks present:
- `apps/frontend/hooks/useCameraCapture.ts`
- `apps/frontend/hooks/useMicStream.ts`
- `apps/frontend/hooks/useRealtimeSession.ts`

Relevant lib files:
- `apps/frontend/lib/ws-client.ts`
- `apps/frontend/lib/audio-utils.ts`

How WebSocket messages are sent and received:
- `ws-client.ts:21-64`
  - opens `new WebSocket(url)`
  - `binaryType = 'arraybuffer'`
  - onmessage routes binary vs text
- Binary receive path:
  - `ws-client.ts:40-49`
  - Blob/ArrayBuffer from backend → `onAudio(buffer)`
- Text receive path:
  - `ws-client.ts:52-60`
  - parses JSON `transcript` / `error`
- Audio send path:
  - `ws-client.ts:67-70` → `ws.send(pcm)`
- Image send path:
  - `ws-client.ts:73-76` → `{"type":"image","data":...}`
- No interrupt send path exists yet.

Is there a flag that suppresses mic during playback?
- Yes.
- `useRealtimeSession.ts:45` declares `isSpeakingRef`
- `useRealtimeSession.ts:74` drops incoming mic chunks while speaking
- `useRealtimeSession.ts:115-118` sets `isSpeakingRef.current = true` before playback
- `useRealtimeSession.ts:126` clears it after playback finishes

### 3) `apps/frontend/public/worklets/mic-processor.js`

What the AudioWorklet processor does:
- `mic-processor.js:13-35` reads mic samples from `inputs[0][0]`
- It accumulates samples into an internal Float32 buffer
- It converts Float32 → Int16 PCM
- It posts Int16 PCM back to the main thread via `this.port.postMessage(...)`

Does it buffer a full turn before posting, or stream chunks?
- It does **not** buffer a full conversational turn.
- It emits fixed-size chunks every time it accumulates `1600` samples.
- That is effectively chunk streaming from the worklet to the JS main thread.

What is the chunk size?
- `mic-processor.js:3-5` and `22-31`
- `1600` Int16 mono samples
- `3200` bytes
- `100ms` at `16kHz` mono

Important architectural finding:
- The worklet is already chunk-oriented.
- The batching happens later in `useRealtimeSession.ts`, not in the worklet.

### 4) `apps/backend/api/routes/realtime.py`

How binary frames are received:
- `realtime.py:133-139`
  - one `ws.receive()`
  - one `data.get("bytes")`
  - one `audio_pcm = data["bytes"]`
- Current contract is still documented as full-turn input:
  - `realtime.py:9-13`
  - `Binary frame = one complete PCM audio turn`

Does the route loop stream audio chunks to DashScope or batch them?
- It batches at the browser/backend boundary.
- Backend receives one complete turn blob, then calls:
  - `realtime.py:310-315` → `client.async_send_audio_turn(audio_pcm=route_audio_pcm, ...)`
- So backend route is **not** a pass-through streaming relay today.

Is there any cancel/interrupt path?
- No explicit interrupt path exists.
- Current text control messages handled are only:
  - `image` at `472-477`
  - `instructions` at `479-484`
  - `ping` at `486-487`
- No `{"type":"interrupt"}` branch exists.

### 5) `apps/backend/services/dashscope/realtime_client.py`

Does `_stream_audio()` send chunks as they arrive or all at once?
- `_stream_audio()` sends 3200-byte chunks progressively **from a preassembled `pcm_bytes` blob**.
- Evidence:
  - `341-367`
  - loops through `for i in range(0, len(pcm_bytes), chunk)`
  - sends repeated `input_audio_buffer.append`
- So it is chunked-on-wire upstream, but only after the backend already has the whole turn.

Does `_collect_response()` have any cancellation path?
- No.
- `_collect_response()` only handles:
  - `conversation.item.input_audio_transcription.completed` (`396-398`)
  - `response.audio_transcript.delta` (`399-401`)
  - `response.audio_transcript.done` (`402-405`)
  - `response.audio.delta` (`407-410`)
  - `response.audio.done` (`412-413`)
  - `response.done` (`415-427`)
  - `error` (`429-432`)
- No `response.cancelled`
- No `input_audio_buffer.speech_started`
- No `response.cancel` helper method

What interruption events does it currently listen for?
- None.
- Search results found no `speech_started`, `speech_stopped`, `response.cancel`, or `response.cancelled` handling in the current file.

## Section 4 — Docs Research Step

### Step 2: Verify DashScope barge-in protocol

#### Search 1 — server VAD / interruption events

Confirmed:
- `input_audio_buffer.speech_started` is a documented / example-used server event when speech begins.
- DashScope sample clients use `input_audio_buffer.speech_started` to detect interruption and then cancel the current response.
- DashScope docs confirm that when `turn_detection` is enabled, the service can interrupt the current response when the user speaks during model output.
- `response.cancel` is a documented client-side cancel action / SDK method.

Unconfirmed:
- A distinct server event named `response.cancelled` was **not** clearly confirmed from the gathered docs.
- Therefore Plan 08 must not depend on `response.cancelled` existing.

What the client should do on `speech_started` mid-response:
- Confirmed from docs/examples:
  - stop local playback immediately
  - treat current response as interrupted
  - send / invoke response cancel upstream if a response is active

#### Search 2 — streaming audio chunks vs one large blob

Confirmed:
- DashScope realtime expects streaming PCM chunks via repeated `input_audio_buffer.append` events.
- Docs recommend sending audio in `100ms` packets.
- Real-time interaction docs and examples continuously send audio chunks while the session is active.
- With server VAD enabled, the service automatically decides turn boundaries.

Unconfirmed:
- A single large binary blob per turn was **not** documented as the intended client pattern for realtime omni + barge-in.
- A maximum inter-chunk interval that causes premature commit was **not** clearly documented in the gathered material.

Plan implication:
- Treat continuous chunk streaming as the required architecture for real barge-in.
- Treat one-blob-per-turn as the current architectural bug.

#### Search 3 — browser mic capture during playback / AEC

Confirmed:
- `AudioWorklet` is the modern low-latency off-main-thread browser audio processing path.
- `AudioWorklet`/`audioWorklet` are secure-context-only.
- `getUserMedia()` supports `echoCancellation` constraints.
- MDN documents that echo cancellation attempts to reduce/remove crosstalk from system output into microphone capture.

Unconfirmed:
- That `echoCancellation: true` guarantees zero feedback in this app.
- That browser AEC alone guarantees perfect barge-in under laptop-speaker conditions.

Plan implication:
- Keep mic open during playback.
- Request AEC / noise suppression.
- Treat AEC as best-effort mitigation, not a proof of no feedback.

SharedArrayBuffer needed?
- **UNCONFIRMED as required**
- MDN confirms AudioWorklet message passing via `MessagePort`; no evidence gathered that `SharedArrayBuffer` is required for this MVP.
- Plan should avoid requiring SharedArrayBuffer.

Chunk size for 100ms at 16kHz mono Int16:
- **CONFIRMED**
- `1600` Int16 samples = `3200` bytes = `100ms`

#### Search 4 — streaming PCM playback in browser

Confirmed:
- `decodeAudioData()` works only on complete audio file data, not fragments.
- Therefore `decodeAudioData()` is not suitable for live `response.audio.delta` PCM chunks.
- `AudioScheduledSourceNode.stop()` can stop playback immediately when called without a future time.

Supported approach from docs + current architecture:
- create / queue small PCM playback buffers as chunks arrive
- play via `AudioBuffer` + `AudioBufferSourceNode`
- stop current source and clear queued buffers on interruption

Unconfirmed:
- The single best browser implementation for seamless gapless chunk playback is not specified by the docs.
- Therefore Plan 08 should specify an interruptible queue based on `AudioBufferSourceNode` / `AudioBuffer` and leave exact queue tuning to implementation.

## Section 5 — Plan Requirements

The plan must achieve:
  True end-to-end barge-in:
  - User can speak at any time, including while assistant is talking
  - Assistant audio stops immediately when user starts speaking
  - Backend forwards the interrupt to DashScope and starts a new turn
  - No audio feedback (mic captures speaker output) — use AEC

This is a cross-cutting change across frontend + backend.
Split into logical layers. Do NOT try to do all in one file.

### A. Backend — `apps/backend/services/dashscope/realtime_client.py`

- Current `_stream_audio()` only chunks a preassembled turn blob; it does not accept live chunk ingress.
- Replace the single-turn abstraction as the primary realtime path.
- Add a session-streaming API surface alongside the existing turn API:
  - `append_audio_chunk(pcm_chunk: bytes) -> None`
  - `append_image_chunk(image_b64: str) -> None` or reuse existing image append helper
  - `cancel_response() -> None`
  - event/callback hook or queue surfacing for provider events

- `cancel_response()` method requirements:
  - Sends client event `{ "type": "response.cancel" }`
  - Guard so it only sends once when a response is actually active
  - Must not raise if no active response exists; log and no-op safely

- `_collect_response()` requirements:
  - Handle streamed `response.audio.delta` as progressive output events, not just an accumulated final blob
  - Handle interruption-sensitive provider events if they appear:
    - `input_audio_buffer.speech_started` → confirmed
    - `input_audio_buffer.speech_stopped` → optional informational
    - `response.done` → confirmed terminal event
    - `response.cancelled` → **UNCONFIRMED**, treat as optional if observed
  - When `input_audio_buffer.speech_started` arrives during active response:
    - mark response interrupted
    - call `cancel_response()` once
    - stop accumulating stale output

- Architectural rule:
  - Keep current `send_audio_turn()` for compatibility tests or non-streaming flows if needed,
    but Plan 08 must define the new streaming path as the primary path for `/ws/realtime`.

### B. Backend — `apps/backend/api/routes/realtime.py`

- Current contract:
  - one binary WebSocket frame = one full turn
- New contract:
  - binary WebSocket frame = one live PCM chunk (100ms / ~3200 bytes)
  - text WebSocket control messages include:
    - `{ "type": "image", "data": "<base64 jpeg>" }`
    - `{ "type": "instructions", "text": "..." }`
    - `{ "type": "ping" }`
    - `{ "type": "interrupt" }`  ← new frontend manual interrupt signal

- Route loop change:
  - Do not wait for a full turn blob before forwarding upstream
  - On each binary chunk:
    - immediately forward to realtime client append path
  - With server VAD enabled:
    - do not own turn-boundary silence logic in backend
    - let provider VAD determine response boundary

- Interrupt path:
  - If frontend sends `{ "type": "interrupt" }`:
    - backend calls realtime client `cancel_response()`
    - backend discards queued downstream output for the cancelled response
    - backend may emit `{ "type": "interrupt" }` back to browser for local playback stop if needed

- Streaming downstream path:
  - As provider `response.audio.delta` events arrive, backend forwards them immediately to frontend as binary audio frames
  - As transcript deltas or done events arrive, backend forwards transcript JSON as it already does or in streaming form if desired
  - Do not wait for a final full assistant blob before sending playback data to browser

- Structural guardrail:
  - Existing vision/memory/orchestrator logic currently depends on turn-scoped transcripts.
  - Plan 08 must preserve current behavior by scoping barge-in MVP to the **realtime conversation path first**, unless Hephaestus explicitly adapts the routing logic for streamed turns in the same change.
  - Do not let Plan 08 silently depend on Plan 09 or later.

### C. Frontend — AudioWorklet / mic path

Files to edit:
- `apps/frontend/hooks/useMicStream.ts`
- `apps/frontend/public/worklets/mic-processor.js`
- `apps/frontend/hooks/useRealtimeSession.ts`

- Required behavior:
  - Must NOT stop capturing mic while assistant audio is playing
  - Remove / replace the guard at `useRealtimeSession.ts:74`
    - `if (isSpeakingRef.current) return`
  - Remove full-turn silence batching as the main send model
  - Keep AudioWorklet posting chunk-sized PCM continuously

- getUserMedia constraints must include:
  - `echoCancellation: true`
  - `noiseSuppression: true`
  - keep `channelCount: 1`

- SharedArrayBuffer:
  - not required for Plan 08
  - use AudioWorklet `MessagePort` chunk delivery

### D. Frontend — WebSocket send loop

Files to edit:
- `apps/frontend/hooks/useRealtimeSession.ts`
- `apps/frontend/lib/ws-client.ts`

- Change from:
  - record full turn → concatenate → send one blob
- Change to:
  - each AudioWorklet chunk → send immediately to backend as binary frame

- Interrupt detection path:
  - local speech energy detection may still be used as a browser-side early signal
  - if assistant audio is currently playing and new speech energy is detected:
    - send `{ "type": "interrupt" }` immediately
    - continue streaming new mic chunks

- Important guardrail:
  - local interrupt detection is a UX improvement, not the only source of truth
  - provider-side `input_audio_buffer.speech_started` remains the confirmed interruption signal

### E. Frontend — Audio playback

Files to edit:
- `apps/frontend/lib/audio-utils.ts`
- `apps/frontend/hooks/useRealtimeSession.ts`
- possibly `apps/frontend/lib/ws-client.ts` if message typing changes

- Change from:
  - receive full assistant blob → `playPcmAudio(fullBlob)`
- Change to:
  - receive audio delta chunks continuously
  - queue / schedule small `AudioBuffer` playback units as they arrive
  - maintain explicit playback queue state

- On interrupt:
  - stop currently playing `AudioBufferSourceNode` immediately via `.stop()`
  - clear any queued unplayed chunks
  - return to capture-ready state without muting mic

- Explicit prohibition:
  - do not use `decodeAudioData()` for `response.audio.delta` PCM chunks

## Files To Create
None new — all changes are to existing files.

## Files To Edit

Backend:
- `apps/backend/services/dashscope/realtime_client.py`
  - add streaming append path
  - add `cancel_response()`
  - surface interruption-sensitive provider events
  - make response collection interruption-aware
- `apps/backend/api/routes/realtime.py`
  - replace full-turn binary contract with progressive chunk forwarding
  - add interrupt control message handler
  - forward streamed audio deltas back to browser immediately

Frontend:
- `apps/frontend/hooks/useMicStream.ts`
  - preserve continuous mic capture during assistant playback
  - keep AEC / noise suppression constraints
- `apps/frontend/hooks/useRealtimeSession.ts`
  - remove mic mute / turn-batching logic
  - send chunks continuously
  - send interrupt control message on local speech-over-playback
  - stop playback immediately on interrupt
- `apps/frontend/lib/ws-client.ts`
  - support interrupt control send path
  - support streamed binary audio receive path without assuming one blob = one response
- `apps/frontend/lib/audio-utils.ts`
  - replace full-blob playback helper with interruptible chunk playback queue
- `apps/frontend/public/worklets/mic-processor.js`
  - keep streaming chunk behavior
  - remove any future temptation to buffer whole turns here

## Files To Delete
None.

## Safe Deletion Rules
N/A.

## Tests To Write

### `tests/unit/test_realtime_client.py`
- `test_cancel_response_sends_response_cancel_event()`
- `test_collect_response_handles_interruption_signal()`
  - use confirmed `input_audio_buffer.speech_started`
- `test_collect_response_treats_response_done_as_terminal_after_cancel()`
  - do not require `response.cancelled`
- `test_stream_audio_sends_chunks_progressively()`

### `tests/unit/test_realtime_route.py`
- `test_interrupt_control_message_cancels_turn()`
- `test_streaming_audio_frames_forwarded_progressively()`
- `test_binary_frames_are_treated_as_live_chunks_not_full_turn_blobs()`

## Tests To Run
`C:/ally-vision-v2/.venv/Scripts/pytest.exe tests/unit/test_realtime_client.py -v --timeout=30 -x`

`C:/ally-vision-v2/.venv/Scripts/pytest.exe tests/unit/test_realtime_route.py -v --timeout=30 -x`

## Gate Checks (physical, binary PASS/FAIL, runnable in 5 min)

Gate A — Backend starts clean:
  `curl http://127.0.0.1:8000/health` → `{"status": "ok"}`

Gate B — Barge-in live:
  Speak → hear assistant start talking → speak again mid-response
  Assistant stops immediately
  Assistant answers the new input
  Report: `BARGE-IN PASS` or `BARGE-IN FAIL` + what happened

Gate C — No audio feedback:
  Speak with speakers on (not headphones)
  Assistant must not echo your voice back
  Report: `AEC PASS` or `AEC FAIL`

## Section 6 — Quality Self-Check

- [ ] Every file listed has a disposition (edit / create / delete)
- [ ] No file deleted before callers updated
- [ ] Tests listed are runnable with exact pytest commands
- [ ] Gate checks are binary PASS/FAIL and runnable in 5 minutes
- [ ] DashScope barge-in event names confirmed from docs (not assumed)
- [ ] `interrupt_response` client-side semantics flagged if still unconfirmed
- [ ] AEC approach confirmed as best-effort (`getUserMedia` constraints), not overclaimed as guaranteed
- [ ] No always-on processing introduced (mic stays open, but chunk emission is worklet-driven — no polling / setInterval loop for capture)
- [ ] Plan does not depend on any code from Plan 09 or later

## Section 7 — Commit Rule

Commit ONLY the plan file:

`git add .sisyphus\plans\08-barge-in-interruption.md`

`git commit -m "plan: write Plan 08 barge-in and true interruption support"`

Do NOT commit any `.py`, `.ts`, `.tsx`, or `.js` files.
Do NOT commit `.env`.

## Section 8 — Stop Rule

STOP. Say:

`PLAN 08 PROMETHEUS COMPLETE.`
`Summary: This plan converts Ally from full-turn request/response audio into a true streaming realtime pipeline so user speech can interrupt assistant playback end-to-end.`
`Key confirmed facts from docs:`
- `input_audio_buffer.speech_started` is the confirmed interruption signal
- with server VAD enabled, audio/video input continues during model response
- realtime audio input is documented as continuous chunk streaming, with 100ms packets recommended
- `response.cancel` exists as the client-side cancel action / SDK method
- `decodeAudioData()` only works on complete audio file data, not live PCM fragments
`Key unconfirmed items flagged:`
- a distinct server event named `response.cancelled`
- exact maximum inter-chunk gap that may cause premature provider behavior
- perfect AEC / zero-feedback guarantee under laptop-speaker playback
`Ready for Hephaestus.`

Wait for instruction.
