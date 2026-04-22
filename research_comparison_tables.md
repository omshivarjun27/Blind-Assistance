# Ally Vision v2 — Research Comparison Tables
# Generated: 2026-04-10
# Purpose: Supporting evidence for research paper submission
# Total tables: 9

## Section 1 — Repo Audit and Grounded Extraction

### Audit notes on requested paths

The requested read list included several stale or moved paths. I read the requested files where they exist, then followed the repo’s current structure for moved equivalents:

- `apps/backend/services/dashscope/embedding_client.py` → actual implementation is `core/memory/embedding_client.py`
- `apps/backend/services/capture/capture_coach.py` → actual implementation is `core/orchestrator/capture_coach.py`
- `apps/backend/services/capture/frame_buffer.py` → no matching file exists in the current repo
- `core/memory/embedding_store.py` → no matching file exists in the current repo
- `apps/frontend/src/app/page.tsx` → actual implementation is `apps/frontend/app/page.tsx`
- `apps/frontend/src/hooks/useRealtimeSession.ts` → actual implementation is `apps/frontend/hooks/useRealtimeSession.ts`
- `apps/frontend/src/hooks/useCameraCapture.ts` → actual implementation is `apps/frontend/hooks/useCameraCapture.ts`

I also read adjacent current files when they are part of the active runtime path, especially `apps/frontend/hooks/useMicStream.ts`, `apps/frontend/lib/ws-client.ts`, `apps/frontend/lib/audio-utils.ts`, `core/memory/memory_manager.py`, `core/learning/correction_store.py`, and `core/search/search_manager.py`.

### Model and voice IDs explicitly present in repo files

Only strings actually present in code, config, tests, or the requested plans are listed below.

| Identifier | Type | Where Found | Notes |
|---|---|---|---|
| `qwen3-omni-flash-realtime` | Realtime model | `.env`, `.env.example`, `shared/config/settings.py`, `AGENTS.md`, tests, `realtime_client.py` | Current realtime model in code/config |
| `qwen3.6-plus` | Heavy vision model | `.env`, `.env.example`, `shared/config/settings.py`, `AGENTS.md`, tests, `multimodal_client.py` | Current heavy-vision model in code/config |
| `gummy-realtime-v1` | Input transcription model | `.env`, `.env.example`, `shared/config/settings.py`, tests, `realtime_client.py` | Used in `session.update.input_audio_transcription.model` |
| `qwen-turbo` | Text model | `shared/config/settings.py`, `intent_classifier.py`, `mem0_extractor.py`, `search_manager.py`, `offline_replay.py`, tests | Used for intent classification, extraction, replay, search wrapper |
| `text-embedding-v4` | Embedding model | `.env`, `.env.example`, `shared/config/settings.py`, `embedding_client.py`, tests | Current embedding model |
| `text-embedding-v3` | Stale plan-only embedding model | `.sisyphus/plans/00-master-plan.md`, `.sisyphus/plans/07-memory-layer.md` | Historical plan value; not current runtime |
| `Cherry` | Voice ID | `.env`, tests, `realtime_client.py` | Current realtime voice |

### Python dependencies declared by the repo

`pyproject.toml` contains build metadata only. Runtime/test dependencies are currently declared in `requirements.txt`, and all entries are unpinned.

| Library | Declared Version in Repo | Evidence |
|---|---|---|
| `fastapi` | not pinned | `requirements.txt` |
| `uvicorn` | not pinned | `requirements.txt` |
| `pydantic` | not pinned | `requirements.txt` |
| `httpx` | not pinned | `requirements.txt` |
| `dashscope` | not pinned | `requirements.txt` |
| `python-dotenv` | not pinned | `requirements.txt` |
| `aiosqlite` | not pinned | `requirements.txt` |
| `pillow` | not pinned | `requirements.txt` |
| `orjson` | not pinned | `requirements.txt` |
| `websocket-client` | not pinned | `requirements.txt` |
| `websockets` | not pinned | `requirements.txt` |
| `numpy` | not pinned | `requirements.txt` |
| `mem0ai` | not pinned | `requirements.txt` |

Test tooling is present in the repo and project rules, but `pytest`, `pytest-asyncio`, and `pytest-timeout` are **not** pinned in the checked-in dependency files.

### Named algorithms, patterns, and techniques explicitly present in code or requested plans

This list includes only named techniques actually present in the repo or the requested plan files.

- Multi-tier cosine recall
- Long-term memory / short-term memory / session memory composition
- Automatic fact extraction (`Mem0Extractor`)
- Embedding-based similarity recall
- Priority-memory promotion / startup priority memory preload
- Ebbinghaus forgetting curve
- THEANINE timeline memory
- Field-Theoretic Memory
- Meta-Adaptive Context Engineering
- MemInsight autonomous augmentation
- Causal replay packet
- 3-turn-before / 3-turn-after replay window
- Prompt verbosity adaptation (`COMPACT`, `NORMAL`, `VERBOSE`)
- Intent penalty injection
- Pixel-quality capture gate (`capture_coach`)
- Model-based framing judge
- OCR-style text extraction
- Page summarization
- LLM-based 9-class intent classification
- Deterministic policy routing
- Search query prefix stripping
- Memory-save prefix stripping
- Manual turn batching (`turn_detection: None`)
- Interrupt / barge-in control via `response.cancel`
- Acoustic echo cancellation (`echoCancellation: true`)
- Noise suppression (`noiseSuppression: true`)
- AudioWorklet chunked PCM capture
- Gap-managed `AudioBufferSourceNode` scheduling

### Browser Web APIs used in the frontend

Only APIs actually referenced in the current frontend are listed. `requestVideoFrameCallback` is mentioned in a comment but is not called.

- `navigator.mediaDevices.getUserMedia`
- `HTMLVideoElement`
- `HTMLVideoElement.srcObject`
- `WebSocket`
- `AudioContext`
- `audioWorklet.addModule`
- `AudioWorkletNode`
- `AudioWorkletProcessor`
- `AudioBuffer`
- `AudioBufferSourceNode`
- `Blob.arrayBuffer()`
- `ArrayBuffer`
- `CanvasRenderingContext2D.drawImage`
- `HTMLCanvasElement.toDataURL`
- `performance.now()`
- `Element.scrollIntoView()`

---

## Section 2 — Table 1: Realtime Audio-Vision Models

| Model | Provider | Release | Context | Languages | Input Modalities | Output Modalities | Latency Class | Access | Our Project Uses |
|---|---|---|---|---|---|---|---|---|---|
| qwen3-omni-flash-realtime | Alibaba DashScope | Current reviewed runtime ID `2025-12-01` (older `2025-09-15`) | 65,536 ctx / 49,152 input / 16,384 output | Multilingual; reviewed public source lists major language families and dialect voices, but exact count for this specific SKU was not found | Streaming audio, image, text | Text, speech | Low-latency realtime | DashScope WebSocket / SDK | ✅ YES |
| qwen3.5-omni-plus-realtime | Alibaba DashScope | Reviewed public runtime ID `2026-03-15` | Publicly unspecified for exact realtime context window | 113 ASR languages/dialects; 36 TTS languages/dialects; 55 voices | Streaming audio, image, text | Text, speech | Low-latency realtime | DashScope WebSocket / SDK | ❌ NO |
| qwen2.5-omni-7b-realtime | Alibaba DashScope | Exact realtime SKU not found in reviewed public source; nearest public family reference is Mar 2025 Qwen2.5-Omni | Publicly unspecified for exact realtime SKU; nearest non-realtime Qwen2.5-Omni-7B entry lists 32,768 ctx | Publicly unspecified | Nearest public family description: text, image, audio, video | Nearest public family description: text, speech | Publicly unspecified for exact realtime SKU | Publicly unspecified | ❌ NO |
| qwen-omni-turbo-realtime | Alibaba DashScope | Current reviewed runtime ID `2025-05-08` | 32,768 ctx / 30,720 input / 2,048 output | Chinese, English | Streaming audio, image, text | Text, speech | Low-latency realtime | DashScope WebSocket / SDK | ❌ NO |
| gpt-4o-realtime-preview | OpenAI | Public beta announced Oct 1, 2024 | Publicly unspecified in reviewed announcement | Multilingual / improved non-English handling; exact count not given | Audio and text over persistent WebSocket | Audio and text | Low-latency realtime | Realtime API for paid developers | ❌ NO |
| gpt-4o-mini-realtime-preview | OpenAI | Upcoming Realtime API support was announced; exact preview release not found in reviewed source | 128K on base GPT-4o mini release page; exact realtime-preview limit not found | Same language range as GPT-4o family was implied; exact realtime-preview count not found | Exact realtime-preview modalities not found; base GPT-4o mini launched with text+vision and future audio/video plans | Exact realtime-preview outputs not found in reviewed source | Expected low-latency small-model tier, but exact preview spec not found | Publicly unspecified in reviewed source | ❌ NO |
| gpt-4-turbo (with audio) | OpenAI | GPT-4 Turbo announced Nov 6, 2023; reviewed sources describe separate TTS / later audio APIs rather than a native GPT-4 Turbo audio model | 128K | Publicly unspecified | Text and image (vision preview) | Text; speech available through separate TTS pipeline rather than native end-to-end audio in reviewed source | Not native realtime speech-to-speech in reviewed source | Chat Completions API + separate TTS tooling | ❌ NO |
| gemini-2.0-flash-live | Google | Exact `gemini-2.0-flash-live` entries were found in reviewed provider materials; released Apr 9, 2025 | Reviewed source did not expose a single context-window number; current Live API docs instead expose streaming token rates | Multilingual; current Live API docs list 70 supported languages | Audio (16 kHz PCM), image (JPEG ≤1 FPS), text | Audio (24 kHz PCM) | Low-latency live | Gemini Live API via WebSocket; client-to-server or server-to-server | ❌ NO |
| gemini-1.5-pro-live | Google | Exact public SKU not found in reviewed source | Publicly unspecified | Publicly unspecified | Publicly unspecified | Publicly unspecified | Publicly unspecified | Exact public access details not found in reviewed source | ❌ NO |
| claude-3-5-sonnet (voice mode) | Anthropic | Closest reviewed public material covered Claude 3 family and current Claude API model overview; exact “Claude 3.5 Sonnet voice mode” SKU was not verified | Claude 3 family announcement listed 200K context | Multilingual; exact count not given | Reviewed public API docs show text+image input; exact voice-mode input spec not verified | Reviewed public API docs show text output; exact voice-mode output spec not verified | Fast / near-instant family positioning, but exact voice-mode latency not verified | Closest verified access is Claude API / claude.ai; exact voice-mode SKU not verified | ❌ NO |
| ElevenLabs Conversational AI | ElevenLabs | Publicly unspecified on reviewed product page | Publicly unspecified | 70+ languages | Voice, chat | Voice, chat | Sub-second responsiveness | Web platform, APIs, SDKs | ❌ NO |
| Hume EVI 2 | Hume AI | Exact `EVI 2` label was not separately documented in current reviewed public docs; closest reviewed product is Hume EVI | Publicly unspecified as token context; session limit 30 minutes documented | Closest reviewed current public doc for EVI 4-mini lists 11 languages | Audio | Audio, transcripts, structured chat-history events | ~300 ms time-to-first-byte on product page | WebSocket API, SDKs, playground | ❌ NO |
| Deepgram Voice Agent | Deepgram | Publicly unspecified on reviewed docs | Publicly unspecified as token context; conversation context/history features are documented | Publicly unspecified in reviewed fetched pages | Audio plus configurable prompt/settings | Audio plus conversation-text / server events | Low-latency streaming | WebSocket API / SDK | ❌ NO |

### Why qwen3-omni-flash-realtime

- DashScope ecosystem integration — the repo already standardizes on DashScope for realtime, heavy vision, and embeddings, so one provider covers voice, vision, and memory retrieval without adding a second cloud stack.
- Cost — Alibaba’s reviewed public positioning for the Flash / cost-sensitive Omni tier emphasizes short-video and lower-cost realtime use cases relative to larger Omni models.
- Multilingual rationale — the reviewed public DashScope Omni family materials are strongly multilingual, but the exact language count for `qwen3-omni-flash-realtime` itself was not found; the 113-language figure belongs to the newer `qwen3.5-omni-plus-realtime` public docs, not a verified flash-tier spec.

---

## Section 3 — Table 2: Vision / Heavy Multimodal Models

| Model | Provider | Release | Vision Tasks | OCR Quality | Languages | Context Window | API Type | Our Project Uses |
|---|---|---|---|---|---|---|---|---|
| qwen3.6-plus (repo runtime; closest reviewed public source: qwen3.5-plus) | Alibaba DashScope | Closest reviewed public source `qwen3.5-plus-2026-02-15`; exact public `qwen3.6-plus` SKU not found | OCR, scene reading, translation, long-video analysis, captioning, moderation | Strong multimodal/OCR positioning; exact OCR benchmark for `qwen3.6-plus` not found | Publicly unspecified | 1,000,000 | DashScope / Model Studio multimodal API | ✅ YES |
| qwen3.5-flash | Alibaba DashScope | `2026-02-23` | Exact vision-task list not stated in reviewed public source | Publicly unspecified | Publicly unspecified | 1,000,000 | DashScope / Model Studio API | ❌ NO |
| qwen2.5-vl-72b | Alibaba | Publicly unspecified in reviewed source | Image understanding, OCR-style document reading, summarization/inference | Strong family-level OCR/document-reading positioning; model-specific OCR number not found | Publicly unspecified | 131,072 | Open-weight / Model Studio Qwen-VL edition | ❌ NO |
| qwen2-vl-7b | Alibaba | Qwen2-VL public README (2024 generation) | Image understanding, video understanding, multilingual in-image text, agent-style device operation | OCRBench 845 in reviewed README | Multilingual in-image text support across English, Chinese, major European languages, Japanese, Korean, Arabic, Vietnamese, and more | Publicly unspecified as one text-context number; visual token range per image documented | Open-weight Hugging Face / Transformers | ❌ NO |
| gpt-4o (vision) | OpenAI | May 13, 2024 | Joint text-image-audio-video model family with strong image understanding and multilingual reasoning | Strong vision positioning; exact OCR-only benchmark not isolated in reviewed source | Multilingual / improved non-English handling; exact count not given | Publicly unspecified in reviewed source | OpenAI API and ChatGPT | ❌ NO |
| gpt-4-turbo (vision) | OpenAI | Nov 6, 2023 | Captioning, real-world image analysis, document reading with figures | Good document-reading support; exact OCR benchmark not found | Publicly unspecified | 128K | Chat Completions API (`gpt-4-vision-preview` at launch) | ❌ NO |
| gemini-2.0-flash | Google | Dec 11, 2024 in reviewed provider materials; current model page marks it deprecated | Multimodal family supporting text, image, video, and audio workflows | Publicly unspecified | Publicly unspecified | 1M token context on reviewed model page | Gemini API / Vertex family | ❌ NO |
| gemini-1.5-pro | Google | Reviewed provider materials show 2024 launch progression and later aliases | Multimodal text, image, video, and audio family model | Publicly unspecified | Publicly unspecified | Publicly unspecified in reviewed source | Gemini API / Vertex family | ❌ NO |
| claude-3-5-sonnet (vision) | Anthropic | Exact 3.5 Sonnet vision row not separately verified in current reviewed docs | Closest verified Anthropic family docs: text+image input with strong image processing | Strong vision capability stated at family level; exact OCR score not found | Multilingual | Publicly unspecified for exact 3.5 Sonnet row in reviewed current docs | Claude API / Bedrock / Vertex | ❌ NO |
| llava-1.6 (open source) | LLaVA Team | Jan 30, 2024 generation (`LLaVA-NeXT`) | Image captioning, visual question answering, multimodal chat | Improved OCR over LLaVA 1.5 is claimed; exact OCRBench score not given in reviewed model card | English with bilingual-support note in reviewed card | Publicly unspecified in reviewed model card | Open-weight Hugging Face / Transformers | ❌ NO |
| InternVL2-26B | Shanghai AI Lab | Jul 2024 generation (`InternVL 2.0`) | Document/chart comprehension, infographics QA, scene text understanding, OCR, math/science reasoning | OCRBench 825 in reviewed model card | Multilingual | 8K | Open-weight Hugging Face / ModelScope | ❌ NO |
| Phi-4-multimodal | Microsoft | Reviewed model card / technical report generation from early 2025 | OCR, chart/table understanding, multiple-image comparison, video summarization, speech tasks | Strong OCR support is explicit; exact OCRBench score not given in reviewed card | Text: 24 listed languages; vision: English; audio: 8 listed languages | 128K | Open-weight Hugging Face / Azure | ❌ NO |
| Gemma-3-27B (vision) | Google DeepMind | Exact reviewed public model card for this row could not be retrieved | Publicly unspecified in reviewed source | Publicly unspecified | Publicly unspecified | Publicly unspecified | Exact reviewed public API/model-card path not retrieved | ❌ NO |

---

## Section 4 — Table 3: Text / Intent Classification Models

| Model | Provider | Release | Params | MMLU Score | Latency Class | Context | Our Project Uses |
|---|---|---|---|---|---|---|---|
| qwen-turbo | Alibaba DashScope | Current reviewed runtime ID `2025-04-28` | Publicly unspecified | Publicly unspecified in reviewed source | Low | 131,072 in thinking mode; 1,000,000 in non-thinking mode | ✅ YES |
| qwen-plus | Alibaba DashScope | Current reviewed runtime ID `2025-12-01` | Publicly unspecified | Publicly unspecified in reviewed source | Medium | 1,000,000 | ❌ NO |
| qwen-max | Alibaba DashScope | Reviewed materials expose `2025-01-25` and older stable IDs | Publicly unspecified | Publicly unspecified in reviewed source | Higher / heavier tier | 32,768 | ❌ NO |
| qwen3-8b | Alibaba | Publicly unspecified in reviewed source | 8B (from model name) | Publicly unspecified | Fast open-weight tier | Publicly unspecified in reviewed source | ❌ NO |
| qwen2.5-7b-instruct | Alibaba | Sep 2024 generation | 7.61B | Publicly unspecified in reviewed source | Fast open-weight tier | 131,072 | ❌ NO |
| gpt-4o-mini | OpenAI | Jul 18, 2024 | Publicly unspecified | 82.0 | Fast | 128K | ❌ NO |
| gpt-3.5-turbo | OpenAI | Reviewed 2024 update page covers `gpt-3.5-turbo-0125`; DevDay page covers `gpt-3.5-turbo-1106` | Publicly unspecified | Publicly unspecified in reviewed source | Fast | 16K in reviewed DevDay update | ❌ NO |
| gemini-1.5-flash | Google | Reviewed provider materials show 2024 launch progression | Publicly unspecified | Publicly unspecified in reviewed source | Fast | Publicly unspecified in reviewed source | ❌ NO |
| claude-3-haiku | Anthropic | Mar 4, 2024 family announcement | Publicly unspecified | 73.8 in OpenAI’s July 2024 competitor comparison for Claude Haiku | Fastest | 200K at Claude 3 family launch | ❌ NO |
| llama-3.1-8b-instruct | Meta | Publicly unspecified in reviewed source | 8B (from model name) | Publicly unspecified in reviewed source | Fast open-weight tier | Publicly unspecified in reviewed source | ❌ NO |
| mistral-7b-instruct-v0.3 | Mistral AI | v0.3 model card reviewed; exact release date not stated in fetched excerpt | 7B | Publicly unspecified in reviewed source | Fast open-weight tier | Publicly unspecified in reviewed source | ❌ NO |
| phi-3-mini-128k | Microsoft | June 2024 update in reviewed model card | 3.8B | 69.7 | Fast / latency-bound scenarios | 128K | ❌ NO |

---

## Section 5 — Table 4: Text Embedding Models

| Model | Provider | Release | Dimensions | MTEB Score | Languages | Max Tokens | Output Types | Our Project Uses |
|---|---|---|---|---|---|---|---|---|
| text-embedding-v4 | Alibaba DashScope | Publicly unspecified in reviewed source | 1024 | Publicly unspecified in reviewed source | 100+ languages in reviewed provider summary | 8,192 tokens per batch | Dense | ✅ YES |
| text-embedding-v3 | Alibaba DashScope | Publicly unspecified in reviewed source | Publicly unspecified in reviewed source | Publicly unspecified in reviewed source | 50+ languages in reviewed provider summary | 8,192 tokens per batch | Dense text embeddings | ❌ NO |
| text-embedding-v2 | Alibaba DashScope | Exact row not found in reviewed public source | Publicly unspecified | Publicly unspecified | Publicly unspecified | Publicly unspecified | Publicly unspecified | ❌ NO |
| text-embedding-ada-002 | OpenAI | Dec 2022 generation; used as Jan 2024 baseline in reviewed OpenAI article | 1536 | 61.0 | Publicly unspecified in reviewed source | Publicly unspecified in reviewed source | Dense text embeddings | ❌ NO |
| text-embedding-3-small | OpenAI | Jan 25, 2024 | Publicly unspecified in reviewed article | 62.3 | Multilingual retrieval improvement is documented; exact language count not given | Publicly unspecified in reviewed article | Dense / shorten-able embeddings | ❌ NO |
| text-embedding-3-large | OpenAI | Jan 25, 2024 | Up to 3072 | 64.6 | Publicly unspecified in reviewed article | Publicly unspecified in reviewed article | Dense / shorten-able embeddings | ❌ NO |
| gemini-embedding-004 | Google | Exact requested SKU was not found in reviewed source; closest reviewed IDs were `text-embedding-004` / `text-embeddings-004` | Publicly unspecified | Publicly unspecified | Publicly unspecified | Publicly unspecified | Publicly unspecified | ❌ NO |
| voyage-3-large | Voyage AI | Publicly unspecified in reviewed docs excerpt | 1024 default (256 / 512 / 2048 also supported) | Publicly unspecified in reviewed source | Multilingual retrieval positioning | 120K total input tokens in reviewed docs | Float / int8 / uint8 / binary / ubinary | ❌ NO |
| voyage-3 | Voyage AI | Publicly unspecified in reviewed current docs | Publicly unspecified in reviewed current docs | Publicly unspecified | Publicly unspecified | Publicly unspecified | Publicly unspecified | ❌ NO |
| e5-mistral-7b-instruct | Microsoft / intfloat | Publicly unspecified in reviewed model card excerpt | Publicly unspecified in reviewed excerpt | Publicly unspecified aggregate MTEB score | Multilingual benchmark coverage is visible in reviewed card | Publicly unspecified in reviewed excerpt | Dense text embeddings | ❌ NO |
| bge-m3 | BAAI | Feb 2024 generation | 1024 | Reviewed source claims top multilingual performance, but no single aggregate MTEB value was given in the fetched excerpt | 100+ languages | 8192 | Dense + sparse + multi-vector | ❌ NO |
| gte-Qwen2-7B-instruct | Alibaba | Publicly unspecified in reviewed model card excerpt | Publicly unspecified in reviewed excerpt | Model card publishes many MTEB task metrics, but no single aggregate was captured in the reviewed excerpt | Multilingual benchmark coverage | Publicly unspecified in reviewed excerpt | Dense text embeddings | ❌ NO |
| nomic-embed-text-v1.5 | Nomic AI | Publicly unspecified in reviewed model card excerpt | Publicly unspecified in reviewed excerpt | Model card publishes many MTEB task metrics, but no single aggregate was captured in the reviewed excerpt | Publicly unspecified in reviewed excerpt | Publicly unspecified in reviewed excerpt | Dense text embeddings | ❌ NO |

| **Upgrade note** | **DashScope** | **Repo history** | **v4 = 1024 in current code; v3 exact dimension not found in reviewed source** | **Quantified MTEB delta between v3 and v4 was not found in reviewed public source** | **Current reviewed provider summary: v4 covers 100+ languages vs v3 50+ languages** | **Both reviewed at 8,192 tokens per batch** | **Dense** | **Repo upgraded from plan-era `text-embedding-v3` to runtime `text-embedding-v4`** |

`text-embedding-v3` appears in older plan files, while current code/config/tests use `text-embedding-v4`. The language-count improvement is visible in reviewed provider materials; a single quantified public MTEB delta between Alibaba v3 and v4 was not found in the reviewed source set.

---

## Section 6 — Table 5: Python Backend Libraries

Version-used values are repo-grounded. Because `requirements.txt` is unpinned, the “Version Used” column below records that reality explicitly instead of inventing resolved versions.

| Library | Version Used | Latest Version | Purpose in Project | Alternative | Why This Library Was Chosen |
|---|---|---:|---|---|---|
| fastapi | unpinned (`fastapi`) | 0.135.3 | Backend web framework, `/ws/realtime`, `/health`, `/config` | Starlette or Flask | Async-first API with built-in WebSocket support and minimal ceremony |
| uvicorn | unpinned (`uvicorn`) | 0.44.0 | ASGI server for local backend run path | Hypercorn | Small, standard FastAPI deployment path with WebSocket support |
| httpx | unpinned (`httpx`) | 0.28.1 | Async HTTP client for DashScope compatible-mode and native multimodal REST calls | aiohttp | Consistent async JSON client for short-lived provider requests |
| websocket-client | unpinned (`websocket-client`) | 1.9.0 | Actual backend DashScope realtime WebSocket client (`import websocket`) | websockets | Simple synchronous client used directly by `QwenRealtimeClient` |
| websockets | unpinned (`websockets`) | 16.0 | Declared dependency; no direct production imports found in inspected runtime files | websocket-client | Likely retained as optional/alternate WS stack, but not the active client path today |
| aiosqlite | unpinned (`aiosqlite`) | 0.22.1 | Async SQLite access for memory, learning, and bootstrap tables | sqlite3 | Matches the repo’s async architecture while keeping SQLite local and simple |
| python-dotenv | unpinned (`python-dotenv`) | 1.2.2 | Loads `.env` values into runtime settings | pydantic-settings | Lightweight env-file loading with almost no integration overhead |
| orjson | unpinned (`orjson`) | 3.11.8 | Declared fast JSON dependency; not heavily used in inspected production code yet | `json` or `ujson` | Chosen as a high-performance JSON option for future serialization-heavy paths |
| Pillow | unpinned (`pillow`) | 12.2.0 | JPEG decode/resize/compress in capture and realtime image utilities | OpenCV | Lighter-weight image handling for browser frame compression and inspection |
| pytest | not declared in checked-in dependency files; used throughout `tests/unit/*` | 9.0.3 | Unit-test framework across backend, memory, learning, and route tests | `unittest` | Strong fixture and mocking ecosystem with concise async-friendly tests |
| pytest-asyncio | not declared in checked-in dependency files; inferred from `@pytest.mark.asyncio` usage | 1.3.0 | Async test support for coroutines and async stores/clients | `pytest-anyio` | Direct fit for the repo’s `async`/`await` testing style |
| pytest-timeout | not declared in checked-in dependency files; referenced by project test command rules | 2.4.0 | Guards against hanging tests, matching repo test rules | custom per-test timeouts | Keeps realtime/network mock tests from stalling CI/dev workflows |
| pydantic | unpinned (`pydantic`) | 2.12.5 | Declared dependency; no direct inspected runtime imports in the current settings module | `dataclasses` or `attrs` | Kept available for validation-heavy future growth, even though current settings are env-based |
| numpy | unpinned (`numpy`) | 2.4.4 | Vector math for cosine similarity and PCM/image array operations | pure Python math / `array` | Efficient numeric operations for embeddings, frame checks, and PCM handling |
| dashscope | unpinned (`dashscope`) | 1.25.16 | Declared official SDK; directly used in access-check tooling and vendored references, while production app mainly uses REST/WS manually | direct REST/WS only | Official provider SDK kept available for tooling and provider-specific checks |
| mem0ai | unpinned (`mem0ai`) | 1.0.11 | Declared dependency aligned with memory research direction; current production path uses repo-local `Mem0Extractor` instead of direct runtime integration | custom local memory stack | Added for research alignment without forcing the core runtime away from SQLite and repo-local control |

---

## Section 7 — Table 6: Frontend Libraries & Web APIs

### Sub-table A — npm Libraries

| Library | Version Used | Purpose in Project | Alternative |
|---|---|---|---|
| @base-ui/react | ^1.3.0 | Headless UI primitives for frontend components | Radix UI |
| class-variance-authority | ^0.7.1 | Variant-based class composition for UI components | tailwind-variants |
| clsx | ^2.1.1 | Conditional className assembly | classnames |
| lucide-react | ^1.7.0 | Icon set for UI controls | Heroicons |
| next | 16.2.2 | Frontend application framework | Remix |
| react | 19.2.4 | Component runtime for UI and hooks | Preact |
| react-dom | 19.2.4 | Browser DOM renderer for React | Preact DOM |
| shadcn | ^4.1.2 | Component scaffolding/design system workflow | Radix UI + custom components |
| tailwind-merge | ^3.5.0 | Merges conflicting Tailwind class strings | custom merge utilities |
| tw-animate-css | ^1.4.0 | Animation utility classes | animate.css |
| @tailwindcss/postcss | ^4 | Tailwind/PostCSS integration in build pipeline | standalone Tailwind CLI |
| @types/node | ^20 | TypeScript type definitions for Node tooling | built-in TS lib types only |
| @types/react | ^19 | React TypeScript typings | built-in emitted types |
| @types/react-dom | ^19 | React DOM TypeScript typings | built-in emitted types |
| babel-plugin-react-compiler | 1.0.0 | React compiler integration in frontend build tooling | no compiler plugin |
| eslint | ^9 | Linting and code-quality checks | Biome |
| eslint-config-next | 16.2.2 | Next.js-specific lint config | custom ESLint config |
| tailwindcss | ^4 | Utility CSS framework | UnoCSS |
| typescript | ^5 | Static typing for frontend code | JavaScript only |

### Sub-table B — Browser Web APIs

| API | MDN Standard | Purpose in Project | Browser Support | Alternative |
|---|---|---|---|---|
| MediaDevices.getUserMedia | Media Capture and Streams | Camera and microphone capture for realtime session input | Modern Chrome/Edge, Firefox, and Safari; secure context required | Native app capture or file upload |
| HTMLVideoElement | HTML Standard | Live camera preview and frame source for JPEG capture | Broadly supported across all major browsers | Canvas-only preview |
| requestVideoFrameCallback | HTML / WICG video-rvfc | Intended fresher frame sampling; mentioned in code comment but not actively called | Modern support: Chrome/Edge 83+, Firefox 132+, Safari 15.4+ | `requestAnimationFrame` |
| WebSocket | WHATWG WebSockets | Browser-to-backend realtime session transport | Broadly supported across major browsers | WebRTC DataChannel or SSE + HTTP |
| AudioContext | Web Audio API | PCM playback, sample-rate control, and audio graph management | Broadly supported in modern browsers; older Safari needed prefixed history | `HTMLAudioElement` |
| AudioWorklet | Web Audio API | Off-main-thread mic capture and PCM chunk generation | Chrome/Edge 66+, Firefox 76+, Safari 14.1+ | `ScriptProcessorNode` (deprecated) |
| AudioBufferSourceNode | Web Audio API | Scheduled assistant PCM playback with gap management | Broadly supported in modern browsers | `HTMLAudioElement` |
| AudioBuffer | Web Audio API | Buffering and channel-copying raw PCM chunks before playback | Broadly supported in modern browsers | MediaSource or custom typed-array buffering |

---

## Section 8 — Table 7: Algorithms & Techniques

**Note:** when the repo does not cite a formal research paper for a technique, the citation cell says so explicitly instead of inventing one.

| Algorithm / Technique | Where Used in Project | Research Paper Citation | Previous / Simpler Alternative | Improvement Over Alternative |
|---|---|---|---|---|
| Semantic vector search (cosine similarity) | `core/memory/memory_store.py` | No explicit paper cited in repo; standard vector retrieval pattern | Keyword or exact-string matching | Retrieves semantically similar memories instead of only lexical matches |
| Three-tier memory architecture (STM / LTM / session-state) | `core/memory/memory_store.py`, `core/memory/memory_manager.py`, `core/memory/session_memory.py`, `core/memory/memory_context_composer.py` | Mem0-inspired design; also reflected in Plan 10 memory layering | Single flat memory table | Separates ephemeral, persistent, and in-session context for cleaner recall |
| Priority memory bootstrap (MemInsight) | `core/learning/offline_replay.py`, `core/memory/memory_store.py`, `core/memory/memory_manager.py`, `apps/backend/api/routes/realtime.py` | MemInsight (arXiv 2503.21760) | Uniform recall with no startup prioritization | Front-loads repeatedly useful facts at session start |
| Embedding-based fact deduplication | `core/memory/memory_store.py` | No explicit paper cited in repo; engineering use of embedding similarity | Append-only memory writes | Prevents duplicate long-term facts and updates near-identical identity facts |
| Ebbinghaus forgetting curve decay weighting | `core/learning/online_reflection.py`, `tests/unit/test_learning.py`, Plan 10 | Closest cited analogue: arXiv:2409.00872; title/citation pairing should be re-verified before publication | Flat correction counting | Weights recent corrections more heavily than old ones |
| Online correction accumulation per intent | `core/learning/online_reflection.py`, `apps/backend/api/routes/realtime.py` | Closest cited analogue only; supplied arXiv:2503.15494 title pairing was not verified from source | No per-intent correction history | Lets the assistant become more cautious for repeatedly corrected intents |
| THEANINE causal timeline replay (offline) | `core/learning/correction_store.py`, `core/learning/offline_replay.py`, Plan 10 | THEANINE (arXiv 2406.10996) | No persisted replay window | Reconstructs causal context around corrections using stored turn windows |
| Field-Theoretic thermodynamic patch decay scoring | `core/learning/rollback.py`, Plan 10 | Field-Theoretic Memory (arXiv 2602.21220) | Manual patch cleanup | Provides an explicit decay heuristic for rolling back weak patches |
| Per-intent failure score thresholding | `core/learning/online_reflection.py` | Closest cited analogue only; supplied arXiv:2503.15494 title pairing was not verified from source | Uniform behavior after mistakes | Activates extra caution only where correction pressure is concentrated |
| Verbosity mode adaptation (COMPACT / NORMAL / VERBOSE) | `core/learning/online_reflection.py`, `core/orchestrator/prompt_builder.py`, `apps/backend/api/routes/realtime.py` | AURA Behaviour-Adaptive Assistant (Nature 2026) as closest behavioral analogue | One fixed answer length | Adapts answer length to user style signals within session |
| Frame quality heuristic (brightness + coverage + contrast) | `core/orchestrator/capture_coach.py` | No explicit paper cited in repo; heuristic gate | Always sending every captured frame to vision model | Avoids expensive or misleading heavy-vision calls on obviously bad frames |
| Capture Coach spoken guidance policy | `core/orchestrator/capture_coach.py`, `apps/backend/api/routes/realtime.py` | No explicit paper cited in repo; UX policy | Silent failure or generic retry | Gives actionable spoken guidance like “Move closer” or “Move to better lighting” |
| Heavy vision routing (frame required flag) | `core/orchestrator/policy_router.py`, `apps/backend/api/routes/realtime.py` | No explicit paper cited in repo; routing policy | Sending all turns to the same model path | Preserves cheap chat path and only invokes vision when image context is required |
| OCR + translation pipeline (single prompt, multi-step) | `core/vision/page_reader.py`, `core/orchestrator/policy_router.py`, `apps/backend/services/dashscope/multimodal_client.py` | Closest provider/protocol analogue: Qwen2.5-Omni Technical Report (arXiv 2503.20215) | Separate OCR engine plus translation engine | Keeps visual text extraction and language transformation in one multimodal stack |
| LLM-based 9-class intent classification | `core/orchestrator/intent_classifier.py` | No explicit paper cited in repo; prompt-based classification pattern | Keyword-only routing | Handles multilingual and paraphrased intents more flexibly |
| Deterministic policy routing (intent → route target) | `core/orchestrator/policy_router.py` | No explicit paper cited in repo; engineering routing pattern | Letting one model decide everything turn-by-turn | Keeps routing auditable and predictable after classification |
| System prompt injection with memory context | `core/orchestrator/prompt_builder.py`, `apps/backend/api/routes/realtime.py`, `core/memory/memory_manager.py` | Mem0 (arXiv 2504.19413) / memory-augmented prompting family | Stateless prompting | Grounds answers in recalled facts and startup priority context |
| Silent turn guard (energy threshold + transcript filter) | `apps/frontend/hooks/useRealtimeSession.ts`, `apps/backend/api/routes/realtime.py` | No explicit paper cited in repo; runtime guard pattern | Responding to silence/noise as if it were a turn | Reduces empty or accidental responses after first-scene introduction |
| PCM 16-bit 24kHz mono streaming | `apps/backend/services/dashscope/realtime_client.py`, `apps/frontend/hooks/useRealtimeSession.ts`, `apps/frontend/public/worklets/mic-processor.js` | Closest provider/protocol analogue: Qwen2.5-Omni Technical Report (arXiv 2503.20215) / DashScope realtime protocol docs | Browser-native compressed media chunks | Matches provider PCM expectations for lower-friction realtime transport |
| Gapless AudioBufferSourceNode scheduling | `apps/frontend/hooks/useRealtimeSession.ts` | No explicit paper cited in repo; Web Audio engineering pattern | One-shot audio playback per blob without scheduling | Produces smoother assistant speech playback across arriving PCM chunks |
| Server-VAD (voice activity detection) | Planned/TODO in `apps/backend/services/dashscope/realtime_client.py` and Plan 08; not active in current runtime | Closest provider/protocol analogue: Qwen2.5-Omni / DashScope realtime docs | Client-side silence timeout only | Intended to support true streaming interruption once wired |
| Interrupt / barge-in (response.cancel on speech detection) | `apps/frontend/hooks/useRealtimeSession.ts`, `apps/frontend/lib/ws-client.ts`, `apps/backend/api/routes/realtime.py`, `apps/backend/services/dashscope/realtime_client.py` | Closest provider/protocol analogue: Qwen2.5-Omni / DashScope realtime docs | No interruption, wait until full reply finishes | Lets the user cut off assistant audio when they begin speaking again |
| AEC (acoustic echo cancellation via getUserMedia constraints) | `apps/frontend/hooks/useMicStream.ts` | No explicit paper cited in repo; Media Capture/WebRTC engineering practice | Raw mic capture without AEC | Reduces feedback/echo when listening and speaking on one device |

---

## Section 9 — Table 8: Database & Storage Schema

| Table Name | Columns | Purpose | Research Component It Supports |
|---|---|---|---|
| long_term_memories | `id`, `user_id`, `fact`, `embedding_json`, `category`, `priority`, `created_at`, `updated_at` | Persistent semantic memory store | Long-term memory, semantic recall, priority bootstrap |
| short_term_memories | `id`, `user_id`, `fact`, `embedding_json`, `category`, `created_at`, `expires_at` | Expiring recent-memory store | Short-term memory and recency-aware recall |
| transcript_log | `id`, `session_id`, `turn_id`, `user_transcript`, `assistant_response`, `intent_at_time`, `route_target`, `created_at` | Persisted chronological turn history | THEANINE-style replay windows and offline analysis |
| correction_log | `id`, `session_id`, `turn_id`, `user_transcript`, `assistant_response`, `correction_signal`, `intent_at_time`, `created_at` | Correction-only audit log | Online learning and offline replay triggers |
| reflection_log | `id`, `session_id`, `turn_id`, `intent`, `failure_score`, `verbosity_mode`, `created_at` | Per-turn reflection snapshots | Ebbinghaus-style online reflection and verbosity adaptation |
| patch_store | `id`, `scope`, `target`, `change_description`, `before_value`, `after_value`, `status`, `score`, `created_at`, `applied_at` | Candidate/adopted/rolled-back behavior patches | Offline replay patching and rollback control |

---

## Section 10 — Table 9: Feature vs Existing System

**Important comparison note:** some comparator names are not equally well documented. `AIDEN` and `ColorInsightX` are research-prototype comparators, and `Smart AI Vision Aid` is mapped to the closest matching public product the delegated audit could verify (Vision-Aid / SHG Smart Vision Glasses). Where public materials did not verify a feature, cells use `⚠️ publicly unspecified` rather than overclaiming.

| Feature | Ally Vision v2 | Seeing AI | Be My Eyes AI | AIDEN | ColorInsightX | Smart AI Vision Aid | Envision Glasses |
|---|---|---|---|---|---|---|---|
| Zero hardware requirement | ✅ | ✅ app-based phone software | ✅ app-based phone software | ✅ paper prototype described as phone-based assistant | ✅ mobile research prototype | ❌ closest matched public product is dedicated smart glasses | ❌ dedicated glasses hardware |
| Spoken frame quality guidance (Capture Coach) | ✅ | ✅ audio capture/document cues are documented, but not repo-style coaching | ⚠️ publicly unspecified on reviewed product materials | ✅ directional TTS guidance such as moving the camera is described in the paper | ⚠️ publicly unspecified; reviewed article describes TTS feedback, not framing coaching | ❌ closest matched public product documents obstacle alerts, not framing guidance | ⚠️ Smart Guidance exists for capture, but reviewed page does not describe repo-style spoken framing policy |
| Persistent cross-session memory (SQLite + embeddings) | ✅ | ❌ reviewed public materials describe saved faces only, not repo-like semantic memory | ⚠️ publicly unspecified in reviewed product materials | ❌ reviewed paper states no personal data are stored | ❌ reviewed article describes CVD-profile personalization, not cross-session semantic memory | ❌ closest matched product documents face storage only, not repo-like semantic memory | ⚠️ Ally is said to “learn over time,” but the reviewed product page does not document a repo-like memory layer |
| Within-session self-adaptation (Ebbinghaus decay) | ✅ | ❌ not found in reviewed public materials | ❌ not found in reviewed public materials | ⚠️ user training is described, but model self-adaptation is publicly unspecified | ❌ profile-based personalization only; no in-session decay/adaptation is documented | ⚠️ publicly unspecified | ⚠️ publicly unspecified; no Ebbinghaus-style mechanism is documented |
| Offline behavioral replay (THEANINE) | ✅ | ❌ not found in reviewed public materials | ❌ not found in reviewed public materials | ⚠️ publicly unspecified | ⚠️ publicly unspecified | ⚠️ publicly unspecified | ❌ not found in reviewed public materials |
| 9-intent LLM routing | ✅ | ❌ reviewed materials describe fixed channels/features, not an explicit 9-intent router | ❌ reviewed materials describe image-description/chat flows, not an explicit 9-intent router | ❌ reviewed paper describes 3 core functions, not a 9-intent router | ❌ reviewed article describes a narrower color/object pipeline | ❌ closest matched product lists a small fixed feature set, not a 9-intent router | ❌ reviewed product feature list does not expose a repo-like 9-intent router |
| 113-language support (speech + text) | ⚠️ multilingual support is real, but the exact 113-language count is verified for a newer Omni public SKU, not this exact repo runtime SKU | ❌ reviewed public materials list 18 languages with plans toward 36, not 113 | ❌ reviewed product materials discuss many volunteer languages, but not a verified 113-language AI spec | ❌ reviewed paper says multilingual support, but no 113-language claim | ⚠️ publicly unspecified language count | ❌ reviewed public materials mention English, Hindi, and regional Indian languages, not 113 | ❌ reviewed public materials say over 60 languages, not 113 |
| Camera-assisted web search | ⚠️ search wrapper exists, but current realtime route still falls back to knowledge + disclaimer instead of a documented live-search path | ❌ not found in reviewed public materials | ❌ reviewed product materials describe image description / follow-up chat, not web search | ❌ reviewed paper focuses on OCR / scene Q&A / object finding, not web search | ❌ reviewed article focuses on color/object support, not web search | ❌ closest matched public product lists read/navigate/object/face features only | ❌ reviewed product page describes on-device assistance, not camera-assisted web search |
| Medicine safety check | ❌ no explicit medicine-safety workflow exists in current repo code | ❌ not found in reviewed public materials | ❌ reviewed terms explicitly say not to rely on it for medication ID/dosing or allergen checks | ❌ reviewed paper includes reading / expiry examples but not a medicine-safety checker | ❌ not found in reviewed article | ❌ closest matched public product does not advertise medicine-safety workflows | ❌ not found in reviewed public materials |
| Server-side VAD barge-in | ⚠️ partial — interrupt exists, but `server_vad` remains TODO and runtime sets `turn_detection=None` | ⚠️ publicly unspecified architecture for VAD/barge-in | ⚠️ publicly unspecified architecture for VAD/barge-in | ⚠️ publicly unspecified architecture for VAD/barge-in | ⚠️ publicly unspecified architecture for VAD/barge-in | ⚠️ publicly unspecified architecture for VAD/barge-in | ⚠️ publicly unspecified architecture for VAD/barge-in |
| Three-tier memory (STM + LTM + session) | ✅ | ❌ not found in reviewed public materials | ❌ not found in reviewed public materials | ❌ reviewed paper explicitly avoids personal-data storage | ❌ not found in reviewed article | ⚠️ publicly unspecified | ❌ no public evidence of a repo-like three-tier memory architecture |
| Open-source deployable (no cloud lock-in for storage) | ✅ SQLite local storage, open repo | ❌ closed product | ❌ centralized hosted service; no self-hosted storage option found | ⚠️ research architecture is described, but an OSS/self-host storage layer is publicly unspecified | ⚠️ paper/prototype comparator; OSS deployment details publicly unspecified | ⚠️ publicly unspecified for closest matched public product | ❌ closed product |

---

## Section 11 — Evidence Notes (for paper citations)

### 1. Mem0 (arXiv 2504.19413)

Mem0 presents a long-term conversational-memory workflow built around extracting, consolidating, and retrieving salient user facts, and reports stronger long-horizon memory behavior than full-context baselines. This repo implements a narrower analogue rather than a full Mem0 reproduction: `Mem0Extractor` turns recent turns into `{fact, category, tier}` records, `MemoryManager` embeds and stores them, and `MemoryStore` retrieves them with cosine similarity across short-term, long-term, and session context. The clearest supporting behavior here is operational rather than benchmark-level: facts are auto-extracted, persisted into SQLite, and later reintroduced into answer context through multi-tier recall.

### 2. MemInsight (arXiv 2503.21760)

MemInsight claims autonomous memory augmentation improves semantic representation and retrieval quality, especially when the agent learns which memories matter most over time. The closest repo analogue is priority-memory promotion rather than full autonomous augmentation: repeated recall topics are elevated to `priority=1` and then injected as startup context for later sessions. The measurable proof point in this codebase is that frequently reused memories are promoted and preloaded at session start, which can be verified through the `priority` field in memory tables and the startup `Remembered context:` prompt injection path.

### 3. THEANINE (arXiv 2406.10996)

THEANINE argues that useful recall should preserve temporal and causal structure, not just isolated facts, so the model can replay memory timelines around important events. The repo implements a lighter replay-window analogue: it logs chronological turns, reconstructs a `3 before + anchor + 3 after` correction window, and uses that ordered window to derive a candidate behavioral patch. The behavior that supports this claim is the presence of seven-turn causal replay packets and generated patch candidates after correction events, rather than a claim of full paper-level reproduction.

### 4. Field-Theoretic Memory (arXiv 2602.21220)

Field-Theoretic Memory proposes a continuous, decay-aware memory formulation using field-style or thermodynamic intuitions rather than static recall alone. This repo does not implement field dynamics directly; its closest related idea is a decay-style rollback heuristic in which patches are judged by whether post-patch correction pressure improves relative to pre-patch behavior. The evidence here is therefore modest and should be framed conservatively: weak patches are retired when correction pressure does not improve, which is observable through `stable`, `monitoring`, and `rollback` states in the patch lifecycle.

### 5. Ebbinghaus Forgetting Curve for LLM (arXiv 2409.00872)

The supplied arXiv ID `2409.00872` appears to resolve to a different title than the one listed in the prompt, so the citation metadata should be rechecked before publication. Even so, the repo does implement an Ebbinghaus-style idea directly: newer corrections contribute more to per-intent failure scores than older ones, and that reflection state is persisted and reused. The supporting behavior is that `failure_score` decays over time and shifts more strongly on recent corrections than older ones, which is visible in the online-reflection logic and corresponding tests.

### 6. Online Reinforcement from Human Corrections (arXiv 2503.15494)

The supplied `2503.15494` title/ID pairing was not verified from source and should be corrected before it is cited as a paper title. The repo still has a clear correction-driven adaptation loop that matches the broad idea: user corrections are logged, aggregated by intent, and converted into an `intent_penalty` warning once repeated failures cross a threshold. The evidence for implementation is behavioral rather than bibliographic: repeated corrections on the same intent make later prompts more cautious for that intent, which can be inspected through correction counts and threshold-triggered prompt warnings.

### 7. Qwen2.5-Omni Technical Report (arXiv 2503.20215)

The Qwen2.5-Omni technical report describes an end-to-end streaming multimodal model family that accepts text, image, audio, and video and can generate text plus natural speech concurrently. This repo uses newer DashScope runtime models (`qwen3-omni-flash-realtime` and `qwen3.6-plus`), so the report is best treated as a provider/protocol analogue rather than proof of exact model identity. The implementation evidence is strong at the protocol level: the repo streams PCM audio in, receives PCM audio out, attaches frames to multimodal turns, and supports interruption through `response.cancel`, which collectively demonstrate a Qwen-Omni-style realtime interaction architecture.

### 8. AURA Behaviour-Adaptive Assistant (Nature 2026)

AURA describes a behavior-adaptive accessibility assistant that changes how it speaks based on user interaction signals such as replay, skip, or listening behavior. The repo’s closest analogue is narrower: it adapts verbosity only (`COMPACT`, `NORMAL`, `VERBOSE`) from textual and correction-derived cues, and then injects that mode into prompts. The key observable behavior is that the saved `verbosity_mode` changes prompting and expected answer length within-session, but the repo does not currently demonstrate the broader speech-rate or language-complexity adaptation claimed by the paper.
