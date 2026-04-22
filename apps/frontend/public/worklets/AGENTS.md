# Worklet Agent Notes

This file supplements `/apps/frontend/AGENTS.md` for `apps/frontend/public/worklets/`.

## Overview
AudioWorklet-side PCM chunking contract for microphone capture.

## Where To Look
| Task | Location | Notes |
|------|----------|-------|
| PCM chunk contract | `mic-processor.js` | 1600 Float32 samples -> transferable 3200-byte Int16 PCM buffer |

## Conventions
- The processor accumulates exactly 1600 mono samples before posting a chunk.
- Output is transferred as a raw `ArrayBuffer` from an `Int16Array`, not JSON or copied structured data.
- `process()` must keep returning `true` so the worklet stays alive.

## Anti-Patterns
- Do not change chunk size without updating the matching hooks/backend transport expectations.
- Do not switch away from Int16 PCM output here.
- Do not add extra buffering or message wrapping that changes the main-thread contract.
