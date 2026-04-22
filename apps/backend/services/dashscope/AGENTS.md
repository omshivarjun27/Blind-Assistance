# DashScope Transport Agent Notes

This file supplements `/apps/backend/AGENTS.md` for `apps/backend/services/dashscope/`.

## Overview
Realtime WebSocket transport + heavy-vision HTTP transport for DashScope.

## Where To Look
| Task | Location | Notes |
|------|----------|-------|
| Realtime protocol/session lifecycle | `realtime_client.py` | `session.updated`, reconnect, cancel, buffering, transcript/audio flow |
| Vision HTTP contract | `multimodal_client.py` | Payload shape, image size limit, never-raise fallback |

## Conventions
- Treat the docstring protocol notes in `realtime_client.py` as local transport invariants, especially audio rate/chunk assumptions and image ordering.
- `QwenRealtimeConfig.from_settings()` is the normal config entrypoint; keep wire-model adjustments localized in this subtree.
- `session.updated` confirmation gates turn readiness; do not start treating the session as usable before that handshake completes.
- Realtime and multimodal are separate transports with different payload rules and failure modes.

## Anti-Patterns
- Do not send realtime images before the audio turn has started; this subtree assumes image-after-audio ordering.
- Do not collapse HTTP multimodal behavior into the realtime transport or vice versa.
- Do not remove `never raises` / structured-error behavior from `VisionResponse`-style APIs.
- Do not change reconnect semantics to imply session resume; reconnect here means a fresh session.
- Do not casually remove wire-model remapping like `gummy-realtime-v1` -> `qwen3-asr-flash-realtime` without checking the session.update contract.
