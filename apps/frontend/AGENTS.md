# Frontend Agent Notes

This file supplements `/AGENTS.md` for `apps/frontend/`.

## Overview
Next.js browser UI for camera capture, microphone capture, PCM playback, and realtime websocket turns.

## Structure
- `app/page.tsx` — main screen and layout composition
- `hooks/useRealtimeSession.ts` — session state, turn flushing, playback, barge-in
- `hooks/useMicStream.ts` — AudioWorklet microphone capture
- `hooks/useCameraCapture.ts` — camera enable/disable and frame capture
- `lib/ws-client.ts` — browser WebSocket transport
- `lib/audio-utils.ts` — PCM helpers
- `components/` — camera, status, controls, small UI pieces

## Where To Look
| Task | Location | Notes |
|------|----------|-------|
| Turn flushing / playback | `hooks/useRealtimeSession.ts` | Main browser-side session logic |
| Mic capture | `hooks/useMicStream.ts` | 16kHz AudioWorklet PCM source |
| Camera capture | `hooks/useCameraCapture.ts` | Video element and JPEG frame capture |
| WebSocket transport | `lib/ws-client.ts` | Binary audio + JSON control messages |
| UI composition | `app/page.tsx` | Mobile/desktop layout and transcript rendering |

## Conventions
- Run all npm commands from `apps/frontend`.
- Import internal modules with the `@/` alias from `tsconfig.json`.
- Component filenames are kebab-case; exported component names stay PascalCase; hooks use `use*.ts`.
- Tailwind/shadcn styling lives in `app/globals.css` and `components.json`; there is no checked-in `tailwind.config.*`.

## Anti-Patterns
- Do not send every worklet chunk as a full user turn; `useRealtimeSession.ts` accumulates and flushes complete turns.
- Do not use `decodeAudioData` for raw PCM fragments.
- Do not connect microphone processing nodes to the audio destination.
- Do not hardcode websocket endpoints when `NEXT_PUBLIC_WS_URL` or the built-in local fallback already covers dev mode.

## Commands
```bash
npm install
npm run dev
npm run build
npm run lint
```
