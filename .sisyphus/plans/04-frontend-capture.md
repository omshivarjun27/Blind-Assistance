---

# Plan 04 — Browser Camera and Mic Capture

## Goal
Build the Next.js frontend that:
1. Captures microphone audio as raw PCM
2. Sends it to /ws/realtime as binary frames
3. Plays back received PCM audio (Cherry voice)
4. Captures camera frames on demand
5. Shows camera feed and status messages

This plan's gate: user opens browser,
speaks, hears Cherry voice respond.

## Audio Implementation Decision
RECOMMENDED: AudioWorklet approach
  - AudioWorkletProcessor runs in audio thread
  - Outputs raw Float32 or Int16 PCM chunks
  - No deprecated APIs
  - Works in all modern browsers

Chosen approach: **AudioWorklet**.

Why this approach is chosen:
- MDN confirms `ScriptProcessorNode` is deprecated and replaced by AudioWorklets / `AudioWorkletNode`.
- MDN confirms `AudioWorkletProcessor.process()` runs off the main thread and is called for each block of **128 sample-frames**.
- SharedArrayBuffer is **not required** for this MVP; using it would force cross-origin isolation requirements that this project does not currently have.
- The current backend `/ws/realtime` contract already expects raw PCM binary audio, so the frontend should intentionally produce PCM rather than emit encoded MediaRecorder blobs.

Exact chunk size:
  3200 bytes = 1600 Int16 samples = 100ms at 16kHz mono

Implementation decision for chunking:
- The worklet should accumulate incoming 128-frame quanta until it has exactly **1600 mono samples**.
- At that point it should convert to Int16 PCM and post a **3200-byte** chunk to the main thread.
- The frontend session layer should then accumulate multiple 3200-byte chunks into **one completed audio turn buffer** before sending a single final binary frame to `/ws/realtime`.
- This matches the actual backend route contract, which treats **one binary WebSocket frame as one full user turn**, not as incremental live streaming.

UNCONFIRMED:
- Whether every browser will honor `new AudioContext({ sampleRate: 16000 })` exactly without internal resampling.
- If a browser does not honor 16kHz exactly, Hephaestus must verify actual `audioContext.sampleRate` and fail fast with a clear UI error rather than silently sending the wrong PCM rate.

## Audio Playback Decision
- Backend `/ws/realtime` returns assistant speech as raw PCM bytes in a binary WebSocket message.
- Browser playback should use **manual `AudioBuffer` creation**, not `decodeAudioData()`.
- MDN confirms `decodeAudioData()` is for complete encoded audio file data, not arbitrary live PCM fragments.
- Playback approach:
  - Convert the received binary message to `ArrayBuffer`
  - Interpret it as mono Int16 PCM
  - Convert Int16 samples to Float32 by dividing by `32768`
  - Create `AudioContext({ sampleRate: 24000 })`
  - Create mono `AudioBuffer`
  - Copy Float32 samples into channel 0
  - Create `AudioBufferSourceNode`, connect to destination, and start playback
- This is the safest browser-native path for raw PCM 24kHz playback in this project.

UNCONFIRMED:
- Whether every browser will honor a requested 24kHz playback context exactly instead of resampling internally.
- For this MVP, that is acceptable because browser-side resampling during playback is less risky than using the wrong API (`decodeAudioData()`) on raw PCM.

## Safe Deletions In This Plan
None. This plan only adds new files.

## Prerequisites Before Hephaestus Runs
Hephaestus must do these FIRST before any code:

1. Initialize Next.js app:
   cd C:/ally-vision-v2/apps/frontend
   npx create-next-app@latest . --typescript --tailwind
     --eslint --app --no-src-dir --import-alias "@/*"

2. Install shadcn/ui:
   cd C:/ally-vision-v2/apps/frontend
   npx shadcn@latest init

3. Install lucide-react:
   cd C:/ally-vision-v2/apps/frontend
   npm install lucide-react

4. Verify dev server starts:
   cd C:/ally-vision-v2/apps/frontend
   npm run dev
   Open http://localhost:3000 — must show Next.js page

## Files To Create

### apps/frontend/public/worklets/mic-processor.js
AudioWorklet processor for raw PCM capture.

Describe exactly what this file must contain:

class MicProcessor extends AudioWorkletProcessor {
  process(inputs, outputs, parameters):
    Get input[0][0] (Float32 mono channel)
    Accumulate samples until 1600 mono samples collected
    Convert to Int16 PCM: sample * 32767
    Post message with Int16Array buffer
    Return true (keep processor alive)

registerProcessor('mic-processor', MicProcessor)

The chunk size naturally follows AudioWorklet quantum:
  128 samples per quantum at 16kHz
  To collect 3200 bytes = 1600 Int16 samples:
    Accumulate exactly 1600 samples in the processor
    Then post one chunk to JS

### apps/frontend/hooks/useMicStream.ts
React hook for microphone capture.

Describe what this hook must contain:

State:
  isListening: boolean
  error: string | null

Methods:
  startListening(onChunk: (pcm: ArrayBuffer) => void) -> Promise<void>
    Request getUserMedia({audio: true})
    Create AudioContext at 16000Hz
    Load AudioWorklet from /worklets/mic-processor.js
    Create MediaStreamSource from microphone stream
    Create AudioWorkletNode('mic-processor')
    Connect: source → workletNode
    Do NOT connect to destination
    workletNode.port.onmessage = (e) => onChunk(e.data)
  stopListening() -> void
    Disconnect node graph
    Stop microphone tracks
    Close AudioContext

Additional requirements:
- This hook must be client-only.
- AudioContext must be created lazily inside `startListening()`, never at module import time.
- If microphone permission is denied, set `error` and keep `isListening = false`.

### apps/frontend/hooks/useCameraCapture.ts
React hook for camera frame capture.

Describe what this hook must contain:

State:
  isEnabled: boolean
  error: string | null

Ref: videoRef: RefObject<HTMLVideoElement>

Methods:
  enableCamera() -> Promise<void>
    getUserMedia({video: {width: 640, height: 480}})
    Attach stream to videoRef.current.srcObject
  captureFrame() -> string | null
    Draw videoRef.current to offscreen canvas
    Return canvas.toDataURL('image/jpeg', 0.8)
    Strip 'data:image/jpeg;base64,' prefix
    Return base64 string only
    Return null if camera not enabled
  disableCamera() -> void
    Stop all tracks

Additional requirements:
- This hook must be client-only.
- `requestVideoFrameCallback()` may be used as an optional enhancement when available, but frame capture must still work without it.
- If `requestVideoFrameCallback` exists, Hephaestus may feature-detect it to grab a fresh frame before capture; otherwise use direct canvas draw from the current `<video>` frame.

### apps/frontend/lib/audio-utils.ts
PCM audio utilities.

Describe what this file must contain:

FUNCTION: playPcmAudio(pcmBytes: ArrayBuffer, sampleRate: number = 24000)
  Create AudioContext
  Convert Int16 PCM to Float32:
    const int16 = new Int16Array(pcmBytes)
    const float32 = Float32Array.from(int16, s => s / 32768)
  Create AudioBuffer: sampleRate, 1 channel, float32.length samples
  Copy float32 into channel 0
  Create BufferSource, connect to destination, start()

FUNCTION: concatArrayBuffers(buffers: ArrayBuffer[]) -> ArrayBuffer
  Concatenate multiple ArrayBuffer chunks into one

Additional requirements:
- Do not use `decodeAudioData()` for assistant PCM playback.
- Create playback context lazily, not at import time.

### apps/frontend/lib/ws-client.ts
WebSocket client for /ws/realtime.

Describe what this file must contain:

CLASS: RealtimeWSClient
  constructor(url: string)
  connect() -> Promise<void>
    new WebSocket(url)
    onopen, onclose, onerror handlers
    onmessage: route binary vs text
  sendAudio(pcm: ArrayBuffer) -> void
    ws.send(pcm)
  sendImage(base64Jpeg: string) -> void
    ws.send(JSON.stringify({type:"image", data: base64Jpeg}))
  sendInstructions(text: string) -> void
    ws.send(JSON.stringify({type:"instructions", text}))
  sendPing() -> void
    ws.send(JSON.stringify({type:"ping"}))
  disconnect() -> void
  onAudio: (pcm: ArrayBuffer) => void   (callback to set)
  onTranscript: (role: string, text: string) => void
  onError: (msg: string) => void

Additional requirements:
- Binary backend messages must be treated as assistant PCM audio.
- Text backend messages must parse:
  - `{type:"transcript", role:"assistant"|"user", text:"..."}`
  - `{type:"error", ...}`
  - `{type:"pong"}`
- If `event.data` is `Blob`, convert it with `await event.data.arrayBuffer()`.

### apps/frontend/hooks/useRealtimeSession.ts
Main session hook combining ws + mic + camera.

Describe what this hook must contain:

State:
  status: "idle" | "connecting" | "listening"
          | "thinking" | "speaking" | "error"
  transcript: {role: "user"|"assistant", text: string}[]
  error: string | null

Methods:
  startSession() -> Promise<void>
    Create RealtimeWSClient(ws://127.0.0.1:8000/ws/realtime)
    Connect WebSocket
    Start mic listening
    On PCM chunk: append chunk to current turn buffer
    On local turn end (explicit stop or client-side silence timeout):
      concat current turn buffers
      sendAudio(one complete ArrayBuffer turn)
      status → thinking
    On audio response: playPcmAudio, status→speaking
    On transcript: append to transcript array
    After playback completes: status → listening

  captureAndSend() -> void
    captureFrame() from useCameraCapture
    If frame: sendImage(base64)

  stopSession() -> void
    stopListening, disconnect
    status → idle

Additional requirements:
- This hook must be client-only.
- It must respect the actual backend route contract: **one binary WebSocket frame per completed user turn**.
- It must not send every 3200-byte mic chunk directly to `/ws/realtime`.
- It may use a simple client-side silence timeout to end a turn automatically after the user stops speaking.

### apps/frontend/components/status-pill.tsx
Tiny status indicator component.

Describe:
  Props: status string
  Shows colored pill with text:
    idle    → gray   "Ready"
    connecting → yellow "Connecting"
    listening  → green  "Listening"
    thinking   → blue   "Thinking"
    speaking   → purple "Speaking"
    error      → red    "Error"

### apps/frontend/components/control-bar.tsx
Mic and camera control buttons.

Describe:
  Props: onStart, onStop, onCapture, status, isCapturing
  Shows:
    Start button (microphone icon, green) when idle
    Stop button (stop icon, red) when active
    Camera capture button (camera icon) always visible
    Disabled state when connecting or thinking

### apps/frontend/components/camera-view.tsx
Camera feed display.

Describe:
  Props: videoRef, isEnabled
  Shows:
    <video> element with videoRef attached
    autoPlay muted playsInline
    Placeholder text when camera not enabled
    640x480 fixed size

### apps/frontend/app/page.tsx
Main page combining all components.

Describe:
  'use client' directive at top
  Uses: useRealtimeSession, useCameraCapture
  Layout:
    Title: "Ally Vision"
    StatusPill showing current status
    CameraView with videoRef from useCameraCapture
    ControlBar wired to session methods
    Transcript list showing last 10 messages
    Each message: role label + text

Additional wiring requirement:
- The page is the client boundary and owns browser-only hooks.
- `useCameraCapture` provides `videoRef`, camera state, and `captureFrame()`.
- `useRealtimeSession` consumes the capture callback so `captureAndSend()` can send the current JPEG frame to the backend before the next spoken turn.

### apps/frontend/app/layout.tsx
Root layout.

Describe:
  Standard Next.js app router layout
  Inter font
  Dark background (#0a0a0a)
  Min height screen

## TypeScript Strict Rules For Hephaestus
  - All components must have 'use client' if they use
    browser APIs (getUserMedia, AudioContext, WebSocket)
  - videoRef must be RefObject<HTMLVideoElement | null>
  - No any types unless absolutely unavoidable
  - AudioContext must be created lazily (not at import time)
    to avoid SSR errors in Next.js app router

## Physical Gate Check
GATE A — Dev server starts:
  cd C:/ally-vision-v2/apps/frontend && npm run dev
  http://localhost:3000 must load without errors

GATE B — Camera visible:
  Allow camera permission
  Camera feed must appear in the video element

GATE C — Voice to Cherry voice:
  Start backend: uvicorn apps.backend.main:app --host 127.0.0.1 --port 8000
  Open http://localhost:3000
  Click Start
  Speak: "Hello"
  Must hear Cherry voice respond
  Status must change: idle → connecting → listening → thinking → speaking → listening

GATE D — Transcript visible:
  After speaking, transcript must show
  user and assistant messages in the list

## Implementation Notes For Hephaestus

1. CORS: backend allows localhost:3000 already.
   No changes needed to backend.

2. AudioContext sampleRate:
   Input:  16000 Hz (what DashScope expects)
   Output: 24000 Hz (what DashScope sends back)
   These are DIFFERENT — use separate contexts
   or create new context per playback.

3. AudioWorklet secure context:
   AudioWorklet requires HTTPS or localhost.
   localhost:3000 works fine during development.

4. PCM chunk accumulation:
   AudioWorkletProcessor runs at 128 sample quanta.
   At 16kHz: 128 samples = 8ms.
   Accumulate exactly 1600 mono samples in the processor
   to emit 3200-byte chunks.
   Then accumulate those chunks in JS until the browser
   decides the user turn is complete.

5. WebSocket URL:
   Use: ws://127.0.0.1:8000/ws/realtime
   Do NOT hardcode — use env variable:
   NEXT_PUBLIC_WS_URL=ws://127.0.0.1:8000/ws/realtime
   Add to apps/frontend/.env.local

6. Binary WebSocket message in browser:
   ws.send(arrayBuffer) sends binary frame.
   onmessage event.data is Blob for binary.
   Convert Blob to ArrayBuffer:
   const buffer = await event.data.arrayBuffer()

7. Playing 24kHz PCM:
   const ctx = new AudioContext({sampleRate: 24000})
   This requests correct sample rate for playback.
   Do not use decodeAudioData on raw PCM.

8. Next.js App Router:
   All hooks and browser API code needs 'use client'
   Page component must be client component.

9. create-next-app choices for Hephaestus:
   --typescript --tailwind --eslint --app
   --no-src-dir --import-alias "@/*"
   Answer "Yes" to all prompts.

10. SharedArrayBuffer:
    Do NOT use SharedArrayBuffer for this MVP.
    AudioWorklet MessagePort + typed arrays are enough,
    and SharedArrayBuffer would require cross-origin isolation.

11. Route contract reminder:
    `/ws/realtime` currently treats one binary frame as one
    complete raw PCM audio turn.
    Frontend must NOT send every worklet chunk directly.
    It must concatenate chunks and flush a final turn buffer.

---

## Self-Check
  □ AudioWorklet approach specified
  □ PCM chunk size 3200 bytes explained
  □ 24kHz playback approach described
  □ WebSocket binary send/receive described
  □ All 9 frontend files listed
  □ 'use client' directive noted for browser components
  □ AudioContext sampleRate difference noted (16k vs 24k)
  □ NEXT_PUBLIC_WS_URL env var mentioned
  □ create-next-app prerequisites listed
  □ 3 physical gate checks (A/B/C/D)
