# Frontend Hooks Agent Notes

This file supplements `/apps/frontend/AGENTS.md` for `apps/frontend/hooks/`.

## Overview
Browser audio/video capture and realtime session state machine.

## Where To Look
| Task | Location | Notes |
|------|----------|-------|
| Turn flush + playback + barge-in | `useRealtimeSession.ts` | Hot-path refs, silence detection, interruption timing |
| Microphone PCM capture | `useMicStream.ts` | 16kHz AudioWorklet capture contract |
| Camera frame capture | `useCameraCapture.ts` | JPEG compression/quality ladder |

## Conventions
- Keep hot-path mutable session state in refs when timing matters; this subtree is intentionally state-machine-heavy.
- Mic capture is built around 16kHz mono PCM and fails fast when the browser sample rate drifts too far.
- Playback logic assumes 24kHz PCM chunks and scheduled source cleanup, not one-shot browser decoding helpers.
- Camera capture trades quality for safe frame size; preserve the compression ladder behavior when adjusting capture settings.

## Anti-Patterns
- Do not replace the accumulated-turn model with chunk-per-message sending.
- Do not move timer/ref-driven playback and barge-in logic into generic UI state without proving the timing still works.
- Do not connect mic processing to speaker output.
- Do not change sample-rate assumptions or frame-size tuning casually; these hooks are coupled to backend transport expectations.
