# Plan 00 — Master Plan

## Project Goal
Blind-first voice+vision web assistant.
User opens browser, speaks, hears Cherry voice.
Camera captures scene and documents on demand.
DashScope only. SQLite only. No local models.

## Core User Flows
1. "What is in front of me?" → scene description
2. "Read this" → OCR via Qwen heavy vision
3. "Scan this page" → camera capture, stored internally
4. "Next page / finish document" → multi-page session
5. "Summarize this document" → document QA
6. "Search [topic]" → DashScope web search
7. "Remember [fact]" → SQLite memory store
8. "Recall [fact]" → SQLite memory retrieval

## Architecture
Browser → FastAPI WebSocket → DashScope Realtime
                           → DashScope Heavy Vision
                           → DashScope Web Search
                           → SQLite Memory + Sessions

## Model Profiles
PROFILE=dev:  qwen3.5-omni-flash-realtime + qwen3.5-flash
PROFILE=exam: qwen3.5-omni-plus-realtime  + qwen3.6-plus
Embedding:    text-embedding-v3 (1024 dims, dense)
Transcription: gummy-realtime-v1 (fixed by DashScope)

## Plans Sequence
01: Scaffold + config + settings + DashScope smoke test
02: DashScope realtime WebSocket client
03: FastAPI WebSocket endpoint + browser audio
04: Browser camera + frame capture pipeline
05: Orchestrator + intent classifier + policy router
06: Heavy vision path (scene + OCR + document QA)
07: Memory (SQLite + text-embedding-v3)
08: Web search path
09: Document session (scan + multi-page + QA)
10: Self-improvement (corrections + online reflection)
11: Frontend polish (Next.js + status messages)
12: End-to-end gate checks

## Not In This Project
No LiveKit, Deepgram, ElevenLabs, Ollama
No YOLO, MiDaS, FAISS, Docker, pgvector
No local models of any kind
No file upload UI (camera-first only)
