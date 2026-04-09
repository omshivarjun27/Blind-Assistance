# Plan 10 — Learning Layer for Ally Vision v2

## 0. Repo audit findings before planning (source of truth)

This section records the required reads/searches before any plan content.

### 0.1 Files read completely

- `apps/backend/api/routes/realtime.py`
- `core/orchestrator/intent_classifier.py`
- `core/orchestrator/policy_router.py`
- `core/orchestrator/prompt_builder.py`
- `core/memory/memory_store.py`
- `shared/config/settings.py`
- `tests/unit/test_realtime_route.py`

The following requested paths do **not** exist in the repo at planning time:

- `core/memory/embedding_store.py`
- `apps/backend/db/sqlite.py`
- `apps/backend/db/bootstrap.py`

### 0.2 Exact line findings from current code

#### `apps/backend/api/routes/realtime.py`

- `_is_memory_query` exists at `93-98`
- `_is_search_query` exists at `123-125`
- `_is_effective_silence` exists at `128-130`
- `make_silent_pcm` exists at `203-206`
- `_is_silent_audio` exists at `209-210`
- session init begins at `263` with:
  - `default_instructions = route(IntentCategory.GENERAL_CHAT).system_instructions` at `263`
  - `memory_manager = MemoryManager.from_settings()` at `271`
  - `pending_image_b64` / `pending_instructions` at `282-283`
  - `_scene_described_once` at `284`
  - `_last_instructions` at `285`
- no correction logging exists anywhere in the route
- no reflection / patch / replay hook exists anywhere in the route
- no post-session learning task exists; disconnect cleanup is only:
  - `session_memory.clear()` at `619`
  - `client.close()` at `620`
- current auto memory extraction runs after each non-memory turn via `_defer_auto_extract(...)` at `507-514`

#### `core/orchestrator/intent_classifier.py`

- classifier prompt text is at `35-44`
- `WEB_SEARCH` is in `_LABELS` at `27`
- `IntentCategory.WEB_SEARCH` is defined at `51`
- module docstring still says classification uses the previous turn transcript at `8-9`, which is now stale relative to current route behavior
- `qwen-turbo` default model is at `85`

#### `core/orchestrator/policy_router.py`

- `RouteTarget.WEB_SEARCH` exists at `26`
- `_UNIMPLEMENTED` contains only `DOCUMENT_QA` at `40-42`
- `SCENE_DESCRIBE` route exists at `45-55`
- `WEB_SEARCH` route exists at `66-78`
- `GENERAL_CHAT` route exists at `103-116`

#### `core/orchestrator/prompt_builder.py`

- `build_system_prompt(...)` exists at `23-37`
- current signature is only:
  - `base_instructions`
  - `memory_context`
  - `document_context`
- there is no `verbosity_mode` parameter
- there is no `intent_penalty` parameter
- `build_search_query(...)` already exists at `40-46`

#### `core/memory/memory_store.py`

- long-term table creation begins at `69-80`
- short-term table creation begins at `99-114`
- `initialize_all()` is `55-116`
- `save_fact(...)` is `122-219`
- `recall_facts(...)` is `221-273`
- `purge_expired()` is `275-283`
- there is no correction, reflection, patch, priority, or replay table in this store

#### `core/memory/memory_manager.py` (from internal architecture audit)

- `auto_extract_and_store()` already exists at `39-69`
- `recall_all_tiers()` already exists at `71-88`
- current `save()` / `recall()` compatibility path exists at `90-120`
- there is no startup priority-memory bootstrap method yet

#### `shared/config/settings.py`

- `QWEN_TURBO_MODEL` exists at `56`
- `EMBEDDING_MODEL` is `text-embedding-v4` at `59`
- `EMBEDDING_DIMENSIONS` is `1024` at `60`
- there are no learning-specific settings yet (no decay factor, reflection threshold, patch monitor window, or priority-memory threshold)

#### `tests/unit/test_realtime_route.py`

- current regression count is 34 route tests
- there are no learning / correction / reflection / replay tests in this file
- no correction-signal assertions exist

### 0.3 Search results for requested symbols

Search results across `apps/` and `core/` confirm:

- `correction` / `corrections` → **no production matches**
- `reflection` / `online_reflection` / `offline_replay` → **no production matches**
- `patch_store` / `correction_store` / `weak_turn` → **no production matches**
- `routing_threshold` → **no production matches**
- `decay` → **no production matches in production code**

The only existing learning-path file is:

- `core/learning/__init__.py:1` → placeholder only (`# Ally Vision v2`)

### 0.4 Existing vs missing Plan 10 modules

Already exists:

- `core/learning/__init__.py` (placeholder only; needs export content)

Missing and must be created:

- `core/learning/correction_store.py`
- `core/learning/online_reflection.py`
- `core/learning/patch_store.py`
- `core/learning/rollback.py`
- `core/learning/offline_replay.py`
- `tests/unit/test_learning.py`

Also absent but required by this plan’s DB bootstrap design:

- `apps/backend/db/bootstrap.py` (must be created)

Hard gap identified during planning:

- there is currently **no persisted turn-history source** for offline replay windows
- there is currently **no priority flag / priority read path** for next-session memory preload

## 1. Context: what is true now

Plans complete:

- 00 master plan
- 01 scaffold + settings
- 02 realtime client
- 03 websocket route
- 04 frontend capture
- 05 orchestrator
- 06 heavy vision
- 06b heavy vision fixes / scene-lock elimination prep
- 07 memory layer
- 08 search

Plan 09 is dropped from scope.
Plan 10 is the learning layer.

Last known code commit for this planning context:

- `ab2d419` — scene-lock bug elimination

What is working now:

- per-turn synchronous classification in the realtime route
- one-time scene intro + silence guard
- memory save/recall with three tiers already live
- search route prompt path already live
- `text-embedding-v4` semantic retrieval
- 91 tests passing in the user’s stated baseline context

What Plan 10 must add:

- within-session online adaptation from corrections
- across-session offline replay and patch generation
- research-grounded decay / timeline / rollback behavior
- no blocking of the audio path
- no fine-tuning; prompt / routing / threshold adaptation only

## 2. External verification of the 5 research references

### 2.1 Ebbinghaus / arXiv 2409.00872

Source checked:

- `https://arxiv.org/abs/2409.00872`

Prompt claim to verify:

- “Does it use a decay weight on correction frequency?”

Status:

- **UNCONFIRMED**

Reason:

- available Tavily extraction exposed the paper title but did not surface a readable abstract or explicit formula supporting a correction-frequency decay rule
- no reliable evidence was recovered for the exact claim

Planning consequence:

- use the forgetting-curve idea as a design inspiration, but clearly mark the explicit formula as our system design choice, not a quoted formula from the paper

### 2.2 THEANINE / arXiv 2406.10996

Source checked:

- `https://arxiv.org/abs/2406.10996`

Prompt claim to verify:

- “Does it link memory entries by timestamp + causal chain?”

Status:

- **CONFIRMED**

Evidence:

- Tavily extraction exposed the abstract text stating that THEANINE “manages large-scale memories by linking them based on their temporal and cause-effect relation” and augments generation with “memory timelines”

Planning consequence:

- use THEANINE as the basis for timeline-linked offline replay around corrections and the 3-turn-before / 3-turn-after causal window

### 2.3 Field-Theoretic Memory / arXiv 2602.21220

Source checked:

- `https://arxiv.org/abs/2602.21220`

Prompt claim to verify:

- “Does it use thermodynamic decay for stale facts?”

Status:

- **CONFIRMED**

Evidence:

- Tavily extraction surfaced the abstract describing memories as “continuous fields,” where they “decay thermodynamically based on importance”

Planning consequence:

- use this as the basis for rollback scoring and automatic retirement of weak patches

### 2.4 Meta-Adaptive Context Engineering / Semantic Scholar 2025

Source checked:

- Semantic Scholar title search via Tavily

Prompt claim to verify:

- “Does it adapt routing/prompt strategy per user?”

Status:

- **UNCONFIRMED**

Reason:

- the provided Semantic Scholar URL was incomplete and the search results did not return a definitive source for this exact title/claim

Planning consequence:

- keep the per-user patch/adaptation concept, but label it as an informed design direction rather than a directly re-verified paper detail

### 2.5 MemInsight / arXiv 2503.21760

Source checked:

- `https://arxiv.org/abs/2503.21760`

Prompt claim to verify:

- “Does it restructure stored memory based on usage patterns?”

Status:

- **UNCONFIRMED for that exact claim**

What is confirmed:

- MemInsight is explicitly about autonomous memory augmentation
- it adapts memory representations and retrieval structure using generated attributes

What is not explicitly confirmed from the extracted text:

- a direct “usage-pattern-based restructuring” claim in the wording requested by the prompt

Planning consequence:

- use MemInsight as support for autonomous memory augmentation and priority restructuring, but clearly mark the “recalled 3+ times → promote to priority memory” rule as our system design choice

## 3. Goal

Build the learning layer for Ally Vision v2 so the system improves over time:

- **online**, within a session, based on recent corrections and user style signals
- **offline**, across sessions, via replay, patch generation, and selective promotion of high-value memories

The system must remain:

- non-blocking for the realtime audio path
- never-raises at runtime
- prompt/routing/threshold adaptive only
- safe to fail open (normal app behavior continues if learning fails)

## 4. Research-to-module mapping (exactly one paper per module)

This plan maps the 5 research directions one-to-one to the 5 Plan 10 modules.

1. **Ebbinghaus forgetting curve** → `core/learning/online_reflection.py`
2. **THEANINE timeline memory** → `core/learning/correction_store.py`
3. **Field-Theoretic Memory** → `core/learning/rollback.py`
4. **Meta-Adaptive Context Engineering** → `core/learning/patch_store.py`
5. **MemInsight** → `core/learning/offline_replay.py`

## 5. Files to create

### 5.1 `core/learning/correction_store.py`

**Research basis:** THEANINE timeline memory

Purpose:

- capture corrections as timestamped events
- preserve the exact turn and nearby context needed for later causal replay

This module owns **two tables**, not one:

1. `transcript_log` — complete persisted turn history needed for replay windows
2. `correction_log` — correction-only audit trail

`transcript_log` schema:

- `id INTEGER PRIMARY KEY AUTOINCREMENT`
- `session_id TEXT NOT NULL`
- `turn_id TEXT`
- `user_transcript TEXT`
- `assistant_response TEXT`
- `intent_at_time TEXT`
- `route_target TEXT`
- `created_at TEXT NOT NULL`

SQLite table: `correction_log`

Columns:

- `id INTEGER PRIMARY KEY AUTOINCREMENT`
- `session_id TEXT NOT NULL`
- `turn_id TEXT`
- `user_transcript TEXT`
- `assistant_response TEXT`
- `correction_signal TEXT`
- `intent_at_time TEXT`
- `created_at TEXT NOT NULL`

Correction signals to detect (minimum set):

- English:
  - `that's wrong`
  - `no that's not right`
  - `incorrect`
  - `not what I asked`
  - `wrong answer`
  - `try again`
  - `that's not it`
  - `stop`
  - `no no`
- Kannada/Hindi equivalents should also be added during implementation

Methods:

- `async log_turn(session_id, turn_id, transcript, response, intent, route_target)`
- `async log_correction(session_id, turn_id, transcript, response, signal, intent)`
- `async get_corrections(session_id=None, limit=50) -> list[dict]`
- `async correction_count_by_intent() -> dict[str, int]`
- `async get_turn_window(session_id, turn_id, before=3, after=3) -> list[dict]`

Behavior rules:

- never raise
- return empty list / empty dict on failure
- store timestamps as UTC ISO strings
- `get_turn_window(...)` must use persisted `transcript_log`, not session memory

### 5.2 `core/learning/online_reflection.py`

**Research basis:** Ebbinghaus forgetting curve

Purpose:

- adapt routing caution and verbosity within the current session
- weight recent corrections more heavily than older ones

Core formula:

```text
weight = 1.0 / (1 + decay_factor * turns_since_correction)
decay_factor = 0.3
```

Example behavior:

- turns_since = 0 → weight = 1.0
- turns_since = 1 → ~0.77
- turns_since = 10 → 0.25

SQLite table: `reflection_log`

Columns:

- `id INTEGER PRIMARY KEY AUTOINCREMENT`
- `session_id TEXT NOT NULL`
- `turn_id TEXT`
- `intent TEXT`
- `failure_score REAL DEFAULT 0.0`
- `verbosity_mode TEXT DEFAULT 'NORMAL'`
- `created_at TEXT NOT NULL`

Methods:

- `record_turn(session_id, turn_id, intent, was_corrected, turns_since_last_correction)`
- `get_intent_penalty(intent) -> bool`
- `get_verbosity_mode(session_id) -> Literal["COMPACT", "NORMAL", "VERBOSE"]`
- `update_verbosity(session_id, signal: str)`

Online policy:

- maintain per-intent failure score from weighted recent corrections
- if `failure_score[intent] > 1.5`, mark intent as penalty-on
- penalty-on means prompt builder prepends:
  - `The user has corrected this type of answer before. Be especially careful and clear.`

Verbosity adaptation rules:

- signals like `shorter`, `brief`, `just tell me` → `COMPACT`
- signals like `explain more`, `tell me more`, `what else` → `VERBOSE`
- default → `NORMAL`

### 5.3 `core/learning/patch_store.py`

**Research basis:** Meta-Adaptive Context Engineering

Purpose:

- store small behavior patches that adapt routing and prompt strategy per user / intent over time

SQLite table: `patch_store`

Columns:

- `id INTEGER PRIMARY KEY AUTOINCREMENT`
- `scope TEXT NOT NULL`  (`routing`, `prompt`, `threshold`)
- `target TEXT`
- `change_description TEXT`
- `before_value TEXT`
- `after_value TEXT`
- `status TEXT DEFAULT 'pending'`
- `score REAL DEFAULT 0.0`
- `created_at TEXT NOT NULL`
- `applied_at TEXT`

Methods:

- `async create_patch(scope, target, before, after, description)`
- `async activate_patch(patch_id)`
- `async rollback_patch(patch_id)`
- `async get_active_patches(target=None) -> list[dict]`
- `async get_patch_history() -> list[dict]`

Patch rules:

- patches never change model weights
- patches only change prompt text, routing thresholds, or prompt selection strategy
- patches are initially `pending`
- patches become `active` only after replay decides they are worth trying

### 5.4 `core/learning/rollback.py`

**Research basis:** Field-Theoretic Memory

Purpose:

- decide whether patches persist or decay away

Key rule:

```text
decay_score = corrections_after / max(1, corrections_before)
if decay_score >= 1.0: rollback
if decay_score < 0.5: stable
```

Monitoring window:

- 10 turns after patch activation

Methods:

- `async evaluate_patch(patch_id, corrections_before, corrections_after) -> Literal["stable", "rollback"]`
- `async auto_rollback_weak_patches() -> list[int]`

Behavior:

- rollback weak or neutral patches automatically
- keep strong stable patches active
- never block runtime turns

### 5.5 `core/learning/offline_replay.py`

**Research basis:** MemInsight autonomous augmentation

Purpose:

- replay corrected sessions offline
- generate candidate patches
- promote highly reused memory topics to session-start priority

Methods:

- `async run_replay(session_id)`
- `async promote_priority_memories(session_id)`

`run_replay(session_id)` flow:

1. load all `correction_log` rows for `session_id`
2. for each correction, load 3 turns before + 3 turns after from persisted `transcript_log`
3. build a causal replay packet for `qwen-turbo`
4. ask for JSON:
   - `{root_cause, suggested_scope, suggested_change}`
5. if a valid patch is suggested, create it in `patch_store`

`promote_priority_memories(session_id)` flow:

1. count memory topics asked/recalled during the session
2. if a topic was recalled 3+ times, mark it as `priority`
3. next-session memory bootstrap should surface priority memories first

Priority-memory implementation rule:

- this module may decide *what* to promote, but persistence must happen through `MemoryStore`
- it must call a dedicated `mark_priority_facts(...)` / equivalent store API, not mutate SQLite ad hoc

Important note:

- the prompt explicitly asks for “usage pattern” promotion; that exact paper claim was not directly confirmed, so this promotion logic is a **system design choice informed by MemInsight**, not a direct quote from the paper

### 5.6 `tests/unit/test_learning.py`

Create a dedicated learning-layer test file covering:

- `CorrectionStore`
  - `test_log_correction_stores_row`
  - `test_get_corrections_returns_list`
  - `test_correction_count_by_intent_returns_dict`
- `OnlineReflection`
  - `test_ebbinghaus_weight_decays_with_turns`
  - `test_failure_score_exceeds_threshold_after_3_corrections`
  - `test_verbosity_mode_defaults_to_normal`
  - `test_verbosity_compact_set_on_signal`
  - `test_verbosity_verbose_set_on_signal`
  - `test_intent_penalty_false_below_threshold`
- `PatchStore`
  - `test_create_patch_returns_id`
  - `test_activate_patch_changes_status`
  - `test_rollback_patch_changes_status`
- `Rollback`
  - `test_stable_patch_when_fewer_corrections_after`
  - `test_rollback_triggered_when_decay_score_gte_1`
- `OfflineReplay`
  - `test_run_replay_creates_patch_on_correction`
  - `test_promote_priority_memories_tags_frequent_topics`
- `PromptBuilder`
  - `test_compact_verbosity_appends_short_instruction`
  - `test_verbose_verbosity_appends_detailed_instruction`
  - `test_intent_penalty_prepends_warning`

All tests must be mocked; zero real network calls.

## 6. Files to edit

### 6.0 `core/learning/__init__.py`

Current state:

- placeholder only at line `1`

Edit to export the five learning modules cleanly.

### 6.1 `shared/config/settings.py`

Add learning-specific knobs with safe defaults:

- `LEARNING_DECAY_FACTOR = 0.3`
- `LEARNING_FAILURE_THRESHOLD = 1.5`
- `LEARNING_PATCH_MONITOR_TURNS = 10`
- `LEARNING_PRIORITY_PROMOTION_MIN_RECALLS = 3`

These are additive only; existing model settings remain unchanged.

### 6.2 `apps/backend/db/bootstrap.py` (create, since absent)

Because this path does not exist, create it rather than edit it.

Purpose:

- centralize creation of:
  - `transcript_log`
  - `correction_log`
  - `reflection_log`
  - `patch_store`

Create helper(s) such as:

- `async bootstrap_learning_tables(db_path: str) -> None`

Tables must match the schema in the prompt.

Planning note:

- do **not** invent `apps/backend/db/sqlite.py` unless implementation truly needs it; current repo already uses `aiosqlite` directly in stores

### 6.3 `core/memory/memory_store.py`

Required additive edits:

1. extend `long_term_memories` with a `priority INTEGER DEFAULT 0` column
2. expose:
   - `async mark_priority_facts(user_id, facts: list[str]) -> int`
   - `async get_priority_facts(user_id, top_k=5) -> list[str]`
3. keep existing save/recall behavior backward-compatible

Rationale:

- without a persisted priority flag, offline replay cannot preload anything at the next session start

### 6.4 `core/memory/memory_manager.py`

Required additive edits:

1. add `async get_startup_memory_context(user_id: str, top_k: int = 5) -> str | None`
   - loads priority facts first from `MemoryStore`
   - returns a joined memory-context string or `None`
2. keep `save()` and `recall()` unchanged

Rationale:

- this is the explicit session-start read path Momus identified as missing

### 6.5 `apps/backend/api/routes/realtime.py`

Additive changes only.

Add session-scope objects near current `memory_manager` init:

- `correction_store = CorrectionStore.from_settings()`
- `online_reflection = OnlineReflection.from_settings()`
- `patch_store = PatchStore.from_settings()`
- `offline_replay = OfflineReplay.from_settings()`

Startup bootstrap additions:

1. initialize learning tables via `bootstrap_learning_tables(...)`
2. fetch startup priority memory via `memory_manager.get_startup_memory_context("default")`
3. if non-empty, merge that into the initial default prompt using `build_system_prompt(...)`

Add correction-signal detection helper (or import it from correction store)

After each completed turn:

1. log the turn to `transcript_log`
   - session_id
   - turn_id
   - current user transcript
   - assistant response
   - routed intent / target
1. detect whether the current transcript is a correction signal
2. if corrected:
   - log row to `correction_log`
   - record failure in `online_reflection`
3. if not corrected:
   - record success / non-correction in `online_reflection`
4. query `get_intent_penalty(predicted_intent)`
5. query `get_verbosity_mode(session_id)`
6. feed both into `build_system_prompt(...)`

On websocket disconnect:

- schedule:
  - `asyncio.create_task(offline_replay.run_replay(session_id))`
  - `asyncio.create_task(offline_replay.promote_priority_memories(session_id))`

Guardrails:

- no removal of existing route logic
- no blocking in the turn path
- failures in learning paths must log and continue only

### 6.6 `core/orchestrator/prompt_builder.py`

Extend `build_system_prompt(...)` with **optional** params only:

- `verbosity_mode: str = "NORMAL"`
- `intent_penalty: bool = False`

Behavior:

- `COMPACT` → append `Keep your answer under 2 sentences.`
- `VERBOSE` → append `Give a thorough, detailed explanation.`
- `NORMAL` → no extra verbosity suffix
- `intent_penalty=True` → prepend:
  - `The user has corrected this type of answer before. Be especially careful and clear.`

Default behavior must remain backward-compatible.

## 7. Test execution plan

Run exactly:

```powershell
C:\ally-vision-v2\.venv\Scripts\pytest.exe tests\unit\test_learning.py -v --timeout=30 -x
C:\ally-vision-v2\.venv\Scripts\pytest.exe tests\unit\test_prompt_builder.py -v --timeout=30 -x
C:\ally-vision-v2\.venv\Scripts\pytest.exe tests\unit\test_realtime_route.py -v --timeout=30 -x
C:\ally-vision-v2\.venv\Scripts\pytest.exe tests\unit\test_policy_router.py -v --timeout=30 -x
```

All 91 existing tests must still pass.

## 8. Task-level QA map (required before final sign-off)

This section addresses Momus’s QA concern: each new/edit target has an explicit tool, steps, and expected result.

### QA — `core/learning/correction_store.py`

- Tool: `pytest`
- Steps:
  1. run `test_log_correction_stores_row`
  2. run `test_get_corrections_returns_list`
  3. run `test_correction_count_by_intent_returns_dict`
  4. add and run `test_log_turn_stores_transcript_history`
  5. add and run `test_get_turn_window_returns_3_before_3_after`
- Expected:
  - both `correction_log` and `transcript_log` rows persist correctly
  - replay windows return the right chronological context

### QA — `core/learning/online_reflection.py`

- Tool: `pytest`
- Steps:
  1. run decay-weight tests
  2. run failure-threshold tests
  3. run verbosity-mode tests
- Expected:
  - weight decays monotonically with turns-since-correction
  - penalty turns on only after threshold
  - verbosity mode flips correctly on compact / verbose signals

### QA — `core/learning/patch_store.py`

- Tool: `pytest`
- Steps:
  1. create patch
  2. activate patch
  3. rollback patch
- Expected:
  - patch state transitions are persisted exactly (`pending` → `active` → `rolled_back`)

### QA — `core/learning/rollback.py`

- Tool: `pytest`
- Steps:
  1. evaluate a stronger patch (`corrections_after < corrections_before`)
  2. evaluate a weak patch (`decay_score >= 1.0`)
- Expected:
  - stable patch returns `stable`
  - weak patch returns `rollback`

### QA — `core/learning/offline_replay.py`

- Tool: `pytest`
- Steps:
  1. feed a mocked correction timeline into `run_replay(session_id)`
  2. assert a patch row is created
  3. feed a mocked repeated topic pattern into `promote_priority_memories(session_id)`
  4. assert priority facts are marked through `MemoryStore`
- Expected:
  - replay uses persisted transcript windows
  - candidate patches are created
  - frequent topics are promoted to priority state

### QA — `apps/backend/db/bootstrap.py`

- Tool: Python + SQLite inspection
- Steps:
  1. initialize learning tables on a temp DB
  2. inspect `sqlite_master`
- Expected:
  - `transcript_log`, `correction_log`, `reflection_log`, and `patch_store` exist

### QA — `core/memory/memory_store.py` / `memory_manager.py`

- Tool: `pytest`
- Steps:
  1. test priority flag persistence
  2. test `get_priority_facts()` ordering
  3. test `get_startup_memory_context()` output
- Expected:
  - priority memories persist across restart boundaries
  - startup context surfaces priority memories first

### QA — `apps/backend/api/routes/realtime.py`

- Tool: `pytest` + manual browser/websocket gates
- Steps:
  1. verify correction detection logs a row
  2. verify verbosity and intent-penalty are injected into prompts
  3. verify disconnect schedules offline replay tasks
  4. run the binary PASS/FAIL gates below
- Expected:
  - learning hooks never block a turn
  - correction / replay / priority bootstrap are observable end-to-end

## 9. Gate checks

### Gate 1 — Ebbinghaus decay (online)

Say the correction signal 3 times for the same intent.
Next answer on that intent should sound cautious / careful.

PASS:

- cautious prefix or clearly more careful wording is heard

### Gate 2 — Verbosity adaptation (online)

Say:

- `give me a shorter answer`

Next answer should be ≤ 2 sentences.

PASS:

- answer is noticeably shorter

### Gate 3 — Correction logging

After a correction, inspect SQLite:

```powershell
python -c "import sqlite3; conn=sqlite3.connect('data/sqlite/memory.db'); print(conn.execute('SELECT * FROM correction_log').fetchall())"
```

PASS:

- correction row exists

### Gate 4 — Priority memory promotion

Ask about the same topic 3 times in one session, end session, restart, start again.

PASS:

- relevant memory is surfaced immediately on the next session

### Gate 5 — Offline replay patch creation

End a session with at least one correction, then inspect:

```powershell
python -c "import sqlite3; conn=sqlite3.connect('data/sqlite/memory.db'); print(conn.execute('SELECT * FROM patch_store').fetchall())"
```

PASS:

- at least one `pending` patch row exists with a description

## 10. Quality self-check

Before implementation is claimed complete, verify:

- all 5 research directions map one-to-one to the 5 learning modules
- Ebbinghaus formula is explicit:
  - `1 / (1 + 0.3 * turns_since_correction)`
- THEANINE causal window is used only in offline replay
- Field-theoretic decay is used only in rollback / patch stability
- MemInsight-style promotion happens only after session end
- Meta-adaptive changes flow through `patch_store`
- no fine-tuning anywhere
- all new modules are never-raises
- `bootstrap.py` creates all 4 learning tables, including `transcript_log`
- `realtime.py` changes are additive only
- `prompt_builder.py` params are optional with defaults
- offline replay only runs on disconnect
- no always-on background threads
- all existing tests remain green
- offline replay has a persisted transcript-history source
- priority memories have both a persisted flag and an explicit session-start read path

## 11. Commit rule

Commit only the plan file:

```powershell
git add .sisyphus/plans/10-learning.md
git commit -m "plan: write plan 10 learning layer"
```

If a longer multi-line message is desired, it must still stage only the plan file.

## 12. Stop rule

STOP. Say: `PLAN 10 PROMETHEUS COMPLETE`
Wait for instruction.
