# Ally Vision Paper Suite Generation

## TL;DR
> **Summary**: Produce a survey paper, a system/journal paper, two figure-prompt files, and a shared 50-reference bibliography for Ally Vision v2 using an evidence-locked workflow grounded in current code, tests, notebooks, and verified literature.
> **Deliverables**:
> - Rewritten `docs/Survey paper/main.tex`
> - New `docs/Survey paper/journal.tex`
> - `docs/Survey paper/image_prompt_1.md`
> - `docs/Survey paper/image_prompt_2.md`
> - `docs/Survey paper/references.bib`
> - `docs/Survey paper/evidence_ledger.csv`
> - `docs/Survey paper/comparison_matrix.csv`
> - `docs/Survey paper/literature_corpus.csv`
> - `docs/Survey paper/sample_style_notes.md`
> **Effort**: XL
> **Parallel**: YES - 2 waves
> **Critical Path**: Task 1 -> Task 2/3/4/5 -> Task 6/7/8/9 -> Task 10

## Context
### Original Request
Create two publication-style LaTeX manuscripts plus two figure-prompt files from the Ally Vision v2 repo, local sample PDFs, comparison notebooks, and 50 relevant peer-reviewed papers, then compile both manuscripts cleanly and report final counts.

### Interview Summary
No user clarification round was needed because the request already fixed the outputs, the sequencing, the paper-specific requirements, and the verification target. Repo exploration resolved the remaining discoverable unknowns: the current runtime is DashScope-only + SQLite-only, `main.tex` is a legacy paper asset rather than current implementation truth, no `.bib` file exists, the comparison evidence lives in 10 notebooks under `docs/comparisons/`, and the local machine is an HP OMEN 16-wf1xxx with Intel i7-14650HX and RTX 4060 Laptop GPU. The plan therefore treats the work as an evidence-locked paper-authoring workflow rather than a free-form writing task.

### Metis Review (gaps addressed)
Metis identified five planning gaps that this plan resolves up front: (1) the survey and journal papers need distinct theses, so the survey is defined as a field landscape paper while the journal paper is defined as an Ally Vision system/design paper; (2) the 50-paper corpus must be precise, so this plan requires 50 unique peer-reviewed entries in a shared bibliography plus a structured corpus manifest, but no copyrighted full-text PDFs committed to git; (3) notebook-derived metrics must not be presented as fresh reruns unless rerun evidence exists, so every notebook value is tagged `historical-extracted`; (4) missing LaTeX tooling must be handled as an explicit bootstrap gate; and (5) unsupported claims must be blocked through a claim taxonomy, an evidence ledger, and final banned-claim audits.

## Work Objectives
### Core Objective
Generate a fully referenced, evidence-backed paper suite that describes the Ally Vision domain and the Ally Vision system accurately, using current code as the source of truth and verified literature as the external framing layer.

### Deliverables
- Rewritten survey manuscript in `docs/Survey paper/main.tex`, preserving the existing author/title/preamble constraints and replacing the body from `\begin{abstract}` onward.
- New system/journal manuscript in `docs/Survey paper/journal.tex` using IEEE two-column conference format.
- Two figure-prompt files with unique figure IDs and placement notes aligned to the manuscripts.
- Shared bibliography in `docs/Survey paper/references.bib` with exactly 50 unique peer-reviewed entries.
- Support artifacts: `evidence_ledger.csv`, `comparison_matrix.csv`, `literature_corpus.csv`, and `sample_style_notes.md` under `docs/Survey paper/`.
- Clean LaTeX builds for both manuscripts with zero undefined-reference / undefined-citation warnings.

### Definition of Done (verifiable conditions with commands)
- `pdflatex --version` and `bibtex --version` succeed on this Windows machine.
- `docs/Survey paper/references.bib` contains exactly 50 BibTeX entries, and `docs/Survey paper/literature_corpus.csv` contains exactly 50 unique reference rows.
- `docs/Survey paper/main.tex` contains the required survey sections, at least 3 numbered equations, at least 1 `booktabs` comparison table, and 12-15 survey figure placeholders that match `image_prompt_1.md`.
- `docs/Survey paper/journal.tex` contains the required journal sections, at least 2 numbered equations, at least 3 `booktabs` result tables, and 10-14 journal figure placeholders that match `image_prompt_2.md`.
- Both LaTeX logs are free of `Undefined citations`, `Reference ... undefined`, `LaTeX Error`, `Emergency stop`, and `File ... not found`.
- Final evidence summary records page count, figure count, table count, equation count, and bibliography count for both manuscripts.

### Must Have
- Claim taxonomy enforced: every nontrivial statement is `code-verified`, `test-verified`, `notebook-measured`, `literature-backed`, or clearly labeled `future-work`.
- Survey paper thesis: a field survey of blind-first multimodal assistive systems, using Ally Vision as the motivating system and comparison anchor.
- Journal paper thesis: a system/design paper describing Ally Vision’s current architecture, comparison-driven component choices, and documented limitations.
- Shared bibliography backend: BibTeX only, stored in `docs/Survey paper/references.bib` and used by both papers.
- Corpus policy: exactly 50 unique peer-reviewed entries; arXiv-only preprints may be used for discovery but must not appear in the final 50 unless matched to a peer-reviewed venue version.
- Notebook policy: notebook numbers are allowed only as `historical-extracted` evidence unless the executor explicitly reruns and records current evidence.
- Figure policy: missing legacy `methodology.png` / `survey.png` are not restored; they are replaced with new placeholder figures aligned to the prompt files.
- Humanization policy: enforce the user’s banned-phrase rules and sentence-variety constraints in both manuscripts.

### Must NOT Have (guardrails, AI slop patterns, scope boundaries)
- No claims that the current system uses LiveKit, Deepgram, ElevenLabs, FAISS, local models, Bedrock, always-on sensing, internet search, face recognition, Braille output, or any other capability absent from current code.
- No fabricated latency, accuracy, reliability, or benchmark numbers.
- No use of README/Markdown/sample PDFs as implementation proof when code/tests disagree.
- No inline `thebibliography` block in the final survey paper.
- No copyrighted full-text paper PDFs committed into the repo as part of the corpus workflow.
- No manual-only acceptance criteria such as “read the PDF and confirm it looks right.”

## Verification Strategy
> ZERO HUMAN INTERVENTION - all verification is agent-executed.
- Test decision: tests-after + PowerShell/BibTeX/LaTeX log audits + focused pytest verification of cited backend behavior
- QA policy: Every task has agent-executed scenarios
- Evidence: `.sisyphus/evidence/task-{N}-{slug}.{ext}`

## Execution Strategy
### Parallel Execution Waves
> Target: 5-8 tasks per wave. <3 per wave (except final) = under-splitting.
> Extract shared dependencies as Wave-1 tasks for max parallelism.

Wave 1: bootstrap toolchain/workspace, extract code evidence, extract notebook evidence, extract sample-style constraints, assemble corpus + shared bibliography

Wave 2: author survey prompt file, rewrite survey paper, author journal prompt file, write journal paper, compile/fix/audit both papers

### Dependency Matrix (full, all tasks)
| Task | Depends On | Blocks |
|------|------------|--------|
| 1 | None | 2, 3, 4, 5, 6, 7, 8, 9, 10 |
| 2 | 1 | 7, 9, 10 |
| 3 | 1 | 7, 9, 10 |
| 4 | 1 | 6, 7, 8, 9, 10 |
| 5 | 1 | 7, 9, 10 |
| 6 | 1, 4 | 7, 10 |
| 7 | 1, 2, 3, 4, 5, 6 | 10 |
| 8 | 1, 4 | 9, 10 |
| 9 | 1, 2, 3, 4, 5, 8 | 10 |
| 10 | 1, 2, 3, 4, 5, 6, 7, 8, 9 | Final Verification |

### Agent Dispatch Summary (wave → task count → categories)
- Wave 1 -> 5 tasks -> `unspecified-high`, `deep`, `writing`
- Wave 2 -> 5 tasks -> `writing`, `deep`, `unspecified-high`

## TODOs
> Implementation + Test = ONE task. Never separate.
> EVERY task MUST have: Agent Profile + Parallelization + QA Scenarios.

- [ ] 1. Bootstrap the authoring workspace and LaTeX toolchain

  **What to do**: Verify whether `pdflatex` and `bibtex` are already available. If either command is missing, install MiKTeX via `winget install --id MiKTeX.MiKTeX -e --source winget`, then enable automatic package installation with `initexmf --set-config-value=[MPM]AutoInstall=t`. If the current PowerShell session does not pick up the new PATH immediately, resolve `pdflatex.exe`, `bibtex.exe`, and `initexmf.exe` from `C:\Program Files\MiKTeX\miktex\bin\x64\` and use those full paths for verification/build commands in the same session. Create the support artifacts `docs/Survey paper/evidence_ledger.csv`, `docs/Survey paper/comparison_matrix.csv`, `docs/Survey paper/literature_corpus.csv`, `docs/Survey paper/references.bib`, and `docs/Survey paper/sample_style_notes.md` with fixed headers/skeleton sections before any manuscript drafting begins.
  **Must NOT do**: Must not start writing `main.tex`, `journal.tex`, or either image-prompt file before the toolchain and support files exist; must not keep the legacy inline bibliography strategy as the final approach.

  **Recommended Agent Profile**:
  - Category: `unspecified-high` - Reason: Windows toolchain bootstrap plus document-workspace scaffolding is precise but not code-architecture-heavy.
  - Skills: `[]` - No extra skill is required beyond disciplined shell execution and file setup.
  - Omitted: [`superpowers:brainstorming`] - Planning is already complete; execution should not reopen design decisions.

  **Parallelization**: Can Parallel: NO | Wave 1 | Blocks: 2, 3, 4, 5, 6, 7, 8, 9, 10 | Blocked By: None

  **References** (executor has NO interview context - be exhaustive):
  - Tool availability check: local environment currently lacks `pdflatex` and `bibtex`; this was verified during planning.
  - Existing paper directory: `docs/Survey paper/main.tex` - only checked-in TeX source, currently uses legacy inline bibliography.
  - Existing paper assets: `docs/Survey paper/Transformers in Vision A Survey.pdf`, `docs/Survey paper/JP1.pdf`, `docs/Survey paper/JP2.pdf`, `docs/Survey paper/JP3.pdf` - local inputs that later tasks will analyze.
  - Repo rule: `AGENTS.md` - code is source of truth; `.md` files are not implementation proof.

  **Acceptance Criteria** (agent-executable only):
  - [ ] `pdflatex --version` exits `0` in PowerShell.
  - [ ] `bibtex --version` exits `0` in PowerShell.
  - [ ] `docs/Survey paper/evidence_ledger.csv` exists and its header is exactly `evidence_id,claim_type,section,target_artifact,source_kind,source_path,source_locator,verification_status,notes`.
  - [ ] `docs/Survey paper/comparison_matrix.csv` exists and its header is exactly `row_id,source_notebook,category,option_name,metric_name,metric_value,metric_unit,evidence_status,notes`.
  - [ ] `docs/Survey paper/literature_corpus.csv` exists and its header is exactly `ref_key,tier,title,authors,year,venue,peer_reviewed,doi_or_url,abstract_url,method_url,relevance_note`.
  - [ ] `docs/Survey paper/references.bib` exists as UTF-8 text and is ready for BibTeX entries.
  - [ ] `docs/Survey paper/sample_style_notes.md` exists with the headings `# Sample Style Notes`, `## Survey Sample`, `## Journal Samples`, and `## Legacy Main.tex Constraints`.

  **QA Scenarios** (MANDATORY - task incomplete without these):
  ```
  Scenario: Happy path bootstrap
    Tool: Bash
    Steps: Run `Get-Command pdflatex, bibtex`; if either is missing, run `winget install --id MiKTeX.MiKTeX -e --source winget`, then `initexmf --set-config-value=[MPM]AutoInstall=t`; if the commands are still not on PATH, resolve them from `C:\Program Files\MiKTeX\miktex\bin\x64\`; finally run `pdflatex --version` and `bibtex --version`, then verify the five support files and CSV headers with `Get-Content`.
    Expected: Both binaries resolve; all five support files exist with the exact headers/headings above.
    Evidence: .sisyphus/evidence/task-01-toolchain-bootstrap.txt

  Scenario: Failure path toolchain detection
    Tool: Bash
    Steps: Before installation, run `Get-Command pdflatex, bibtex -ErrorAction SilentlyContinue`; record the missing-command state; then rerun the bootstrap command chain.
    Expected: The bootstrap script branches into installation instead of proceeding to authoring with missing tools.
    Evidence: .sisyphus/evidence/task-01-toolchain-bootstrap-error.txt
  ```

  **Commit**: NO | Message: `chore(latex): bootstrap paper workspace` | Files: `docs/Survey paper/evidence_ledger.csv`, `docs/Survey paper/comparison_matrix.csv`, `docs/Survey paper/literature_corpus.csv`, `docs/Survey paper/references.bib`, `docs/Survey paper/sample_style_notes.md`

- [ ] 2. Build the code-and-test evidence ledger for the current Ally Vision runtime

  **What to do**: Perform a full repo-ingestion pass over every repo-tracked file under `apps/`, `core/`, `shared/`, `scripts/`, `tests/`, root config/docs files (including `.env.example`, `README.md`, `AGENTS.md`, `requirements*.txt`, `pyproject.toml`, `pytest.ini`), and any additional root architecture docs if they exist. Then populate `docs/Survey paper/evidence_ledger.csv` with evidence rows for architecture, runtime message flow, model selection, memory behavior, learning/correction behavior, explicit limitations, and legacy exclusions. Mark rows as `code-verified` when backed by current source and `test-verified` only when backed by a passing targeted test file. Include explicit negative/limitation rows for unsupported capabilities (for example LiveKit/Deepgram/FAISS/local-model claims, absent infrastructure layer, and `DOCUMENT_QA` falling back to realtime chat).
  **Must NOT do**: Must not cite README, sample PDFs, or legacy `main.tex` as implementation proof; must not mark a claim `test-verified` without a passing targeted pytest run.

  **Recommended Agent Profile**:
  - Category: `deep` - Reason: This task requires precise understanding of the live code path and disciplined differentiation between code-backed and test-backed claims.
  - Skills: `[]` - No additional skill is required if the agent follows the source-of-truth rule.
  - Omitted: [`superpowers:test-driven-development`] - The task validates existing behavior; it does not introduce new implementation work.

  **Parallelization**: Can Parallel: YES | Wave 1 | Blocks: 7, 9, 10 | Blocked By: 1

  **References** (executor has NO interview context - be exhaustive):
  - Runtime config truth: `shared/config/settings.py`
  - Backend entry/lifespan: `apps/backend/main.py`
  - Main websocket route: `apps/backend/api/routes/realtime.py`
  - Realtime transport contract: `apps/backend/services/dashscope/realtime_client.py`
  - Heavy vision transport: `apps/backend/services/dashscope/multimodal_client.py`
  - Shared HTTP clients: `apps/backend/services/shared_http.py`
  - Frontend session/runtime path: `apps/frontend/app/page.tsx`, `apps/frontend/hooks/useRealtimeSession.ts`, `apps/frontend/hooks/useMicStream.ts`, `apps/frontend/public/worklets/mic-processor.js`, `apps/frontend/hooks/useCameraCapture.ts`, `apps/frontend/lib/ws-client.ts`
  - Orchestration: `core/orchestrator/intent_classifier.py`, `core/orchestrator/policy_router.py`, `core/orchestrator/capture_coach.py`, `core/orchestrator/prompt_builder.py`
  - Memory subsystem: `core/memory/memory_manager.py`, `core/memory/memory_store.py`, `core/memory/embedding_client.py`, `core/memory/mem0_extractor.py`, `core/memory/session_memory.py`
  - Learning subsystem: `core/learning/online_reflection.py`, `core/learning/correction_store.py`, `core/learning/offline_replay.py`, `core/learning/patch_store.py`, `core/learning/rollback.py`
  - Vision helpers: `core/vision/live_scene_reader.py`, `core/vision/page_reader.py`, `core/vision/framing_judge.py`
  - Schema/bootstrap: `apps/backend/db/bootstrap.py`
  - Test coverage anchors: `tests/unit/test_realtime_route.py`, `tests/unit/test_realtime_client.py`, `tests/unit/test_memory_store.py`, `tests/unit/test_learning.py`, `tests/unit/test_settings.py`, `tests/conftest.py`
  - Environment template: `.env.example`

  **Acceptance Criteria** (agent-executable only):
  - [ ] `.sisyphus/evidence/task-02-read-inventory.txt` exists and lists every repo-tracked file read from `apps/`, `core/`, `shared/`, `scripts/`, and `tests/`, plus the root files reviewed during ingestion.
  - [ ] `docs/Survey paper/evidence_ledger.csv` contains at least 40 non-header rows.
  - [ ] At least 12 rows are tagged `test-verified` and cite one of the targeted unit-test files.
  - [ ] At least 5 rows explicitly document limitations/negative claims (for example no local models, no FAISS/vector DB, no LiveKit, no Deepgram, no checked-in `infrastructure/` implementation layer).
  - [ ] The following targeted tests exit `0`: `tests/unit/test_realtime_route.py`, `tests/unit/test_realtime_client.py`, `tests/unit/test_memory_store.py`, `tests/unit/test_learning.py`, and `tests/unit/test_settings.py`.
  - [ ] No row in `evidence_ledger.csv` uses `.md` or `.pdf` as `source_kind` for an implementation claim.

  **QA Scenarios** (MANDATORY - task incomplete without these):
  ```
  Scenario: Happy path evidence extraction
    Tool: Bash
    Steps: First create `.sisyphus/evidence/task-02-read-inventory.txt` from the repo-tracked file inventory under `apps/`, `core/`, `shared/`, `scripts/`, `tests/`, and root config/docs files after the ingestion pass; then populate `evidence_ledger.csv`; then run `C:\ally-vision-v2\.venv\Scripts\pytest.exe tests/unit/test_realtime_route.py -v --timeout=30 -x`, `C:\ally-vision-v2\.venv\Scripts\pytest.exe tests/unit/test_realtime_client.py -v --timeout=30 -x`, `C:\ally-vision-v2\.venv\Scripts\pytest.exe tests/unit/test_memory_store.py -v --timeout=30 -x`, `C:\ally-vision-v2\.venv\Scripts\pytest.exe tests/unit/test_learning.py -v --timeout=30 -x`, and `C:\ally-vision-v2\.venv\Scripts\pytest.exe tests/unit/test_settings.py -v --timeout=30 -x`; finally run a CSV audit script that counts rows by `claim_type` and rejects `.md`/`.pdf` implementation sources.
    Expected: The read inventory exists, all five pytest commands pass, and the ledger has the required row counts with no forbidden implementation sources.
    Evidence: .sisyphus/evidence/task-02-code-evidence.txt

  Scenario: Failure path unsupported-claim guard
    Tool: Bash
    Steps: Run a search against `evidence_ledger.csv` for forbidden implementation-source patterns such as `,code-verified,.*\.md,` or unsupported-current-state notes missing from the ledger.
    Expected: The audit finds zero forbidden implementation-source rows and confirms the presence of explicit limitation rows before manuscript writing begins.
    Evidence: .sisyphus/evidence/task-02-code-evidence-error.txt
  ```

  **Commit**: NO | Message: `docs(evidence): capture current runtime claims` | Files: `docs/Survey paper/evidence_ledger.csv`

- [ ] 3. Extract notebook-backed comparison evidence into a reusable matrix

  **What to do**: Read all 10 notebooks in `docs/comparisons/` and extract their compared options, metric names, numeric values where present, winner statements, and caveats into `docs/Survey paper/comparison_matrix.csv`. Every row sourced from a notebook must be tagged `historical-extracted` unless the notebook is explicitly rerun and current evidence is captured; do not assume rerun status by default. Record one summary/winner row for each notebook and preserve important caveats such as sparse quantitative grounding, manual top-5 chart selection, and the likely stale `category10_self_correction_comparison_chart3.png` artifact.
  **Must NOT do**: Must not present notebook results as fresh current-machine benchmarks unless they are actually rerun and recorded as such; must not fabricate values missing from notebook cells.

  **Recommended Agent Profile**:
  - Category: `deep` - Reason: The task requires structured extraction from notebook JSON plus careful distinction between explicit numbers, qualitative selections, and stale artifacts.
  - Skills: `[]` - No extra skill is needed if the agent can work carefully with notebook JSON/text.
  - Omitted: [`superpowers:systematic-debugging`] - This is evidence extraction, not bug triage.

  **Parallelization**: Can Parallel: YES | Wave 1 | Blocks: 7, 9, 10 | Blocked By: 1

  **References** (executor has NO interview context - be exhaustive):
  - `docs/comparisons/Realtime_Model_Comparison.ipynb`
  - `docs/comparisons/Heavy_Vision_Model_Comparison.ipynb`
  - `docs/comparisons/Category_3_-_Intent_Classification_LLM.ipynb`
  - `docs/comparisons/Category_4_-_Embedding_Model_Comparison.ipynb`
  - `docs/comparisons/Category_5_-_Memory_Architecture_Comparison.ipynb`
  - `docs/comparisons/Category_6_-_ASR_Transcription_Comparison.ipynb`
  - `docs/comparisons/Category_7_-_TTS_Voice_Comparison.ipynb`
  - `docs/comparisons/Category_8_-_WebSocket_Architecture_Comparison.ipynb`
  - `docs/comparisons/Category_9_-_Capture_Coach_Comparison.ipynb`
  - `docs/comparisons/Category_10_-_Self_Correction_Comparison.ipynb`
  - Artifact caveat: `docs/comparisons/charts/category10_self_correction_comparison_chart3.png`

  **Acceptance Criteria** (agent-executable only):
  - [ ] `docs/Survey paper/comparison_matrix.csv` contains rows for all 10 source notebooks.
  - [ ] Each of the 10 notebooks contributes at least one winner/selection row with a non-empty `option_name` and `notes` field.
  - [ ] All notebook-derived rows have `evidence_status=historical-extracted` unless an explicit rerun note is added.
  - [ ] `comparison_matrix.csv` includes rows covering at least the following categories: realtime, heavy vision, intent classification, embeddings, memory architecture, ASR, TTS, transport, capture coach, and self-correction.
  - [ ] A note about the likely stale `category10_self_correction_comparison_chart3.png` artifact is present in either `comparison_matrix.csv` or `sample_style_notes.md`.

  **QA Scenarios** (MANDATORY - task incomplete without these):
  ```
  Scenario: Happy path notebook extraction
    Tool: Bash
    Steps: Populate `comparison_matrix.csv`, then run a CSV audit script that counts unique `source_notebook` values, counts winner rows, and verifies `evidence_status` values.
    Expected: 10 unique notebook sources are present, 10 winner rows exist, and notebook rows default to `historical-extracted`.
    Evidence: .sisyphus/evidence/task-03-notebook-matrix.txt

  Scenario: Failure path stale-artifact/caveat audit
    Tool: Bash
    Steps: Search `comparison_matrix.csv` and `sample_style_notes.md` for `category10_self_correction_comparison_chart3.png` and for notebook categories with missing winner notes.
    Expected: The stale-artifact caveat is recorded and no notebook category is missing a winner/selection note.
    Evidence: .sisyphus/evidence/task-03-notebook-matrix-error.txt
  ```

  **Commit**: NO | Message: `docs(evidence): extract comparison notebook data` | Files: `docs/Survey paper/comparison_matrix.csv`

- [ ] 4. Analyze the sample documents and freeze the writing/structure rules

  **What to do**: Read `Transformers in Vision A Survey.pdf`, `JP1.pdf`, `JP2.pdf`, `JP3.pdf`, and the existing `main.tex`, then turn the findings into `docs/Survey paper/sample_style_notes.md`. Capture the exact structural skeletons, abstract rhythms, section-transition patterns, citation placement habits, equation/table/figure treatment, and conclusion style that the final papers must emulate. Also record the hard constraints from the legacy `main.tex`: missing `fig/` assets, inline bibliography, out-of-sync stack references, and the requirement to preserve only the preamble/title/author region while replacing the body from `\begin{abstract}` onward.
  **Must NOT do**: Must not treat sample PDFs as factual evidence for the Ally Vision implementation; must not copy citation keys or factual claims from the samples without independent verification.

  **Recommended Agent Profile**:
  - Category: `writing` - Reason: This is a style-analysis and manuscript-structure task, not a runtime-code task.
  - Skills: `[]` - No extra skill is required if the agent keeps style notes separate from factual evidence.
  - Omitted: [`superpowers:writing-plans`] - The execution plan already exists; this task is one artifact within it.

  **Parallelization**: Can Parallel: YES | Wave 1 | Blocks: 6, 7, 8, 9, 10 | Blocked By: 1

  **References** (executor has NO interview context - be exhaustive):
  - Survey sample: `docs/Survey paper/Transformers in Vision A Survey.pdf`
  - Journal samples: `docs/Survey paper/JP1.pdf`, `docs/Survey paper/JP2.pdf`, `docs/Survey paper/JP3.pdf`
  - Existing legacy TeX: `docs/Survey paper/main.tex`
  - Current system truth for mismatch checks: `shared/config/settings.py`, `apps/backend/api/routes/realtime.py`, `apps/backend/services/dashscope/realtime_client.py`, `apps/backend/services/dashscope/multimodal_client.py`

  **Acceptance Criteria** (agent-executable only):
  - [ ] `docs/Survey paper/sample_style_notes.md` contains the headings `## Survey Sample`, `## Journal Samples`, `## Legacy Main.tex Constraints`, `## Survey Thesis`, `## Journal Thesis`, and `## Non-Overlap Rules`.
  - [ ] `sample_style_notes.md` explicitly states that sample PDFs are style exemplars, not implementation proof.
  - [ ] `sample_style_notes.md` explicitly states that `main.tex` is legacy and must not be used as source-of-truth for the current stack.
  - [ ] `sample_style_notes.md` records that `JP2.pdf` and `JP3.pdf` require duplicate/mislabeled-copy caution.
  - [ ] The survey thesis and journal thesis are both present and materially different.

  **QA Scenarios** (MANDATORY - task incomplete without these):
  ```
  Scenario: Happy path style-note audit
    Tool: Bash
    Steps: Populate `sample_style_notes.md`, then run `Select-String` checks for the required headings, the phrase `STYLE EXEMPLAR ONLY`, the phrase `LEGACY / NOT SOURCE OF TRUTH`, and the duplicate-warning note for `JP2`/`JP3`.
    Expected: All required headings and warnings are present.
    Evidence: .sisyphus/evidence/task-04-style-notes.txt

  Scenario: Failure path thesis-overlap audit
    Tool: Bash
    Steps: Compare the `## Survey Thesis` and `## Journal Thesis` sections in `sample_style_notes.md` with a diff/string-equality check.
    Expected: The two thesis sections are not identical and the `## Non-Overlap Rules` section explains the division of labor between the papers.
    Evidence: .sisyphus/evidence/task-04-style-notes-error.txt
  ```

  **Commit**: NO | Message: `docs(style): capture sample paper rules` | Files: `docs/Survey paper/sample_style_notes.md`

- [ ] 5. Assemble the 50-paper peer-reviewed corpus and shared BibTeX library

  **What to do**: Using the current codebase, comparison notebooks, and sample-style notes as the query anchor, collect exactly 50 unique peer-reviewed papers that are genuinely relevant to Ally Vision’s problem space and architecture. For every search batch, run Tavily and a page-fetch/web-fetch path in parallel; for every candidate that survives triage, retrieve and verify the abstract page with page fetch plus the best available metadata page before adding it to the corpus. Populate `docs/Survey paper/literature_corpus.csv` with one row per paper and `docs/Survey paper/references.bib` with matching BibTeX entries. Use the tiering scheme from planning (`tier1` direct technical match, `tier2` closely related domain, `tier3` foundational), and sort the final corpus/BibTeX order by tier (`tier1` first, then `tier2`, then `tier3`). Require a DOI or stable URL for every entry; arXiv-only preprints must be excluded from the final 50 unless a peer-reviewed venue version is identified.
  **Must NOT do**: Must not count duplicate titles/DOIs toward the 50; must not commit downloaded copyrighted PDFs into the repo; must not include vendor docs or non-peer-reviewed blog posts as part of the final 50.

  **Recommended Agent Profile**:
  - Category: `writing` - Reason: This is structured research acquisition and bibliography authoring.
  - Skills: `[]` - The task can be executed with web research tools plus careful metadata validation.
  - Omitted: [`librarian`] - Remote-code lookup is not the bottleneck; the required work is bibliography assembly, not library-internals inspection.

  **Parallelization**: Can Parallel: YES | Wave 1 | Blocks: 7, 9, 10 | Blocked By: 1

  **References** (executor has NO interview context - be exhaustive):
  - Corpus output: `docs/Survey paper/literature_corpus.csv`
  - Shared BibTeX output: `docs/Survey paper/references.bib`
  - Query anchors from code/system: `shared/config/settings.py`, `apps/backend/api/routes/realtime.py`, `apps/backend/services/dashscope/realtime_client.py`, `apps/backend/services/dashscope/multimodal_client.py`, `core/memory/memory_manager.py`, `core/learning/online_reflection.py`, `apps/frontend/hooks/useRealtimeSession.ts`
  - Query anchors from notebooks: all files listed in Task 3
  - Style/non-overlap guidance: `docs/Survey paper/sample_style_notes.md`

  **Acceptance Criteria** (agent-executable only):
  - [ ] `docs/Survey paper/literature_corpus.csv` contains exactly 50 non-header rows.
  - [ ] Every corpus row has non-empty `ref_key`, `tier`, `title`, `authors`, `year`, `venue`, `peer_reviewed`, `doi_or_url`, and `relevance_note` fields.
  - [ ] Every corpus row has `peer_reviewed=true`.
  - [ ] `docs/Survey paper/references.bib` contains exactly 50 BibTeX entries whose keys match the 50 `ref_key` values in `literature_corpus.csv`.
  - [ ] Every BibTeX entry contains author, title, year, venue (`journal` or `booktitle`), and either `doi` or `url`.
  - [ ] Every BibTeX entry includes a commented relevance annotation line immediately above the entry.
  - [ ] `literature_corpus.csv` is ordered by `tier1` rows first, then `tier2`, then `tier3`.

  **QA Scenarios** (MANDATORY - task incomplete without these):
  ```
  Scenario: Happy path corpus audit
    Tool: Bash
    Steps: Populate `literature_corpus.csv` and `references.bib` using the dual-search workflow (Tavily + page fetch per search batch), then run a CSV/BibTeX audit script that counts rows and entries, cross-checks keys, verifies required fields, and confirms tier ordering.
    Expected: Exactly 50 unique corpus rows and 50 matching BibTeX entries exist; all required metadata fields are present and the rows are tier-sorted.
    Evidence: .sisyphus/evidence/task-05-corpus-bib.txt

  Scenario: Failure path duplicate/non-peer-reviewed audit
    Tool: Bash
    Steps: Run a duplicate detector over `title` and `doi_or_url`, and a rule check for rows where `peer_reviewed` is not `true` or `doi_or_url` contains only an arXiv identifier with no peer-reviewed venue.
    Expected: Zero duplicates and zero non-peer-reviewed final entries remain.
    Evidence: .sisyphus/evidence/task-05-corpus-bib-error.txt
  ```

  **Commit**: YES | Message: `docs(research): assemble corpus and bibliography assets` | Files: `docs/Survey paper/literature_corpus.csv`, `docs/Survey paper/references.bib`, `docs/Survey paper/sample_style_notes.md`, `docs/Survey paper/evidence_ledger.csv`, `docs/Survey paper/comparison_matrix.csv`

- [ ] 6. Create the survey-paper figure prompt file with aligned figure IDs

  **What to do**: Write `docs/Survey paper/image_prompt_1.md` before touching the survey manuscript body. Create 12-15 survey figure entries using the exact figure-ID scheme `placeholder_fig_s01` through `placeholder_fig_s15` (use only as many IDs as needed, but do not skip numbers). Each entry must contain: `FIGURE_ID: placeholder_fig_sXX`, one 80-150 word prompt describing the figure in publication-diagram detail, and one placement note in the exact requested format `[PLACEMENT: Section X.Y — "Section Title" — insert ABOVE/BELOW paragraph beginning with "..."]`. Base the figures on the survey section plan, the comparison matrix, and the actual Ally Vision architecture rather than on the missing legacy `methodology.png`/`survey.png` assets.
  **Must NOT do**: Must not leave ambiguous prompt text; must not introduce demo-screenshot placeholders in the survey prompt file; must not use figure IDs that fail to match the later `main.tex` placeholders.

  **Recommended Agent Profile**:
  - Category: `writing` - Reason: This is structured technical writing tightly coupled to the survey manuscript outline.
  - Skills: `[]` - No extra skill is required if the agent can follow a fixed schema.
  - Omitted: [`frontend-design:frontend-design`] - These are publication-diagram prompts, not UI screens.

  **Parallelization**: Can Parallel: YES | Wave 2 | Blocks: 7, 10 | Blocked By: 1, 4

  **References** (executor has NO interview context - be exhaustive):
  - Survey style rules: `docs/Survey paper/sample_style_notes.md`
  - Code/system anchors: `apps/backend/api/routes/realtime.py`, `apps/backend/services/dashscope/realtime_client.py`, `apps/backend/services/dashscope/multimodal_client.py`, `apps/frontend/hooks/useRealtimeSession.ts`, `core/memory/memory_manager.py`, `core/learning/online_reflection.py`
  - Extracted evidence: `docs/Survey paper/evidence_ledger.csv`, `docs/Survey paper/comparison_matrix.csv`, `docs/Survey paper/literature_corpus.csv`

  **Acceptance Criteria** (agent-executable only):
  - [ ] `docs/Survey paper/image_prompt_1.md` contains between 12 and 15 `FIGURE_ID:` entries.
  - [ ] Every survey figure ID is unique and follows the pattern `placeholder_fig_sNN` with no numbering gaps.
  - [ ] Every figure entry contains exactly one placement line matching the prefix `[PLACEMENT:`.
  - [ ] Every prompt paragraph is between 80 and 150 words.
  - [ ] The set of figure IDs in `image_prompt_1.md` is ready to be mirrored exactly in `main.tex`.

  **QA Scenarios** (MANDATORY - task incomplete without these):
  ```
  Scenario: Happy path survey prompt audit
    Tool: Bash
    Steps: Populate `image_prompt_1.md`, then run a parser that counts `FIGURE_ID:` lines, checks uniqueness/contiguity of `placeholder_fig_sNN`, validates each `[PLACEMENT:` line, and counts prompt words.
    Expected: Entry count is 12-15, IDs are unique/contiguous, and every prompt falls within the 80-150 word range.
    Evidence: .sisyphus/evidence/task-06-survey-prompts.txt

  Scenario: Failure path schema mismatch audit
    Tool: Bash
    Steps: Search `image_prompt_1.md` for missing placement lines, duplicate figure IDs, or any `leave BLANK` text.
    Expected: No schema violations are present and no journal/demo placeholder syntax appears in the survey prompt file.
    Evidence: .sisyphus/evidence/task-06-survey-prompts-error.txt
  ```

  **Commit**: YES | Message: `docs(survey): add survey figure prompts` | Files: `docs/Survey paper/image_prompt_1.md`

- [ ] 7. Rewrite `main.tex` as the survey paper, from `\begin{abstract}` onward

  **What to do**: Rewrite `docs/Survey paper/main.tex` starting exactly at `\begin{abstract}` and continuing through `\end{document}` while preserving everything above `\begin{abstract}` except for adding missing `\usepackage{}` lines if truly required. Replace the legacy inline bibliography with BibTeX usage (`\bibliographystyle{IEEEtran}` + `\bibliography{references}`), align all survey figure placeholders to `image_prompt_1.md`, and enforce this exact survey section structure: `Introduction`; `Background and Problem Formulation`; `Visual Perception and Scene Understanding`; `Speech and Language Interfaces`; `Multimodal Fusion Architectures`; `Edge Deployment and Latency Constraints`; `Evaluation Methodologies and Benchmarks`; `Open Problems and Future Directions`; `Conclusion`. Use Ally Vision as the motivating/current-system anchor, not as the entire paper. Cite all 50 corpus references across the survey body.
  **Must NOT do**: Must not change the title, author block, affiliation, email, IEEE document class declaration, or pre-existing package lines; must not leave `thebibliography` in the final file; must not use banned phrases (`leverages`, `robust`, `seamlessly`, `cutting-edge`, `groundbreaking`, `novel approach`) or start sentences with `In this paper`.

  **Recommended Agent Profile**:
  - Category: `writing` - Reason: This is the main survey-manuscript authoring task with strict structural and stylistic constraints.
  - Skills: `[]` - No additional skill is required beyond disciplined manuscript writing and LaTeX editing.
  - Omitted: [`superpowers:brainstorming`] - The design decisions are fixed; this task is pure execution.

  **Parallelization**: Can Parallel: YES | Wave 2 | Blocks: 10 | Blocked By: 1, 2, 3, 4, 5, 6

  **References** (executor has NO interview context - be exhaustive):
  - File to modify: `docs/Survey paper/main.tex`
  - Survey prompt alignment: `docs/Survey paper/image_prompt_1.md`
  - Shared bibliography: `docs/Survey paper/references.bib`
  - Corpus manifest: `docs/Survey paper/literature_corpus.csv`
  - Style rules and thesis: `docs/Survey paper/sample_style_notes.md`
  - Current-system evidence: `docs/Survey paper/evidence_ledger.csv`
  - Comparison evidence for tables/discussion: `docs/Survey paper/comparison_matrix.csv`
  - Legacy mismatch reminder: the current codebase is described by `shared/config/settings.py`, `apps/backend/api/routes/realtime.py`, `apps/backend/services/dashscope/realtime_client.py`, `apps/backend/services/dashscope/multimodal_client.py`, not by the old LiveKit/Deepgram/FAISS references in the legacy body.

  **Acceptance Criteria** (agent-executable only):
  - [ ] `main.tex` retains the original title/author/preamble region above `\begin{abstract}`; no diff hunks appear before `\begin{abstract}` except newly added package lines if required.
  - [ ] The abstract contains exactly 4 sentences and is between 230 and 270 words.
  - [ ] `main.tex` contains all 9 required section headings listed above.
  - [ ] `main.tex` contains at least 3 `\begin{equation}` environments.
  - [ ] `main.tex` contains at least 1 `\begin{table}` with `\toprule`, `\midrule`, and `\bottomrule`.
  - [ ] `main.tex` contains between 12 and 15 `\includegraphics` placeholders whose filenames match the `FIGURE_ID` set in `image_prompt_1.md` exactly.
  - [ ] `main.tex` uses `\bibliography{references}` and no longer contains `\begin{thebibliography}`.
  - [ ] All 50 keys from `literature_corpus.csv` are cited at least once in `main.tex`.
  - [ ] `main.tex` contains no `\begin{itemize}` or `\begin{enumerate}` environments in the manuscript body.
  - [ ] The banned phrases list produces zero matches, and `state-of-the-art` appears no more than 2 times.

  **QA Scenarios** (MANDATORY - task incomplete without these):
  ```
  Scenario: Happy path survey manuscript audit
    Tool: Bash
    Steps: Rewrite `main.tex`, then run a LaTeX-source audit that checks section headings, equation count, table markers, figure-ID parity against `image_prompt_1.md`, abstract sentence/word count, bibliography command, and citation-key coverage against `literature_corpus.csv`.
    Expected: All required structure checks pass and all 50 corpus keys are cited in the survey manuscript.
    Evidence: .sisyphus/evidence/task-07-survey-tex.txt

  Scenario: Failure path preamble/banned-language audit
    Tool: Bash
    Steps: Run `git diff --unified=0 -- "docs/Survey paper/main.tex"` to inspect changes before `\begin{abstract}`, then run a banned-phrase scan for `In this paper`, `leverages`, `robust`, `seamlessly`, `cutting-edge`, `groundbreaking`, and `novel approach`.
    Expected: No unauthorized changes appear before `\begin{abstract}` and the banned-phrase scan returns zero matches.
    Evidence: .sisyphus/evidence/task-07-survey-tex-error.txt
  ```

  **Commit**: YES | Message: `docs(survey): rewrite ally vision survey manuscript` | Files: `docs/Survey paper/main.tex`, `docs/Survey paper/image_prompt_1.md`, `docs/Survey paper/references.bib`

- [ ] 8. Create the journal-paper figure prompt file with demo-image placeholders

  **What to do**: Write `docs/Survey paper/image_prompt_2.md` using the exact figure-ID scheme `placeholder_fig_j01` through `placeholder_fig_j14` (use only as many IDs as needed, but do not skip numbers). Create 10-14 entries focused on system architecture diagrams, methodology flowcharts, result charts, latency distributions, confusion/ablation visuals, and qualitative demo panels. For all demo-image entries, use the exact placement syntax `[PLACEMENT: Section — leave BLANK — to be replaced with real screenshot/demo image]`. Ensure the prompt file distinguishes between evidence-based analytical figures and future screenshot slots.
  **Must NOT do**: Must not reuse survey figure IDs or survey placement text; must not omit the `leave BLANK` marker on demo-image entries; must not create fewer than 2 demo-image placeholder entries.

  **Recommended Agent Profile**:
  - Category: `writing` - Reason: This is manuscript-support writing with a stricter schema for demo-image placeholders.
  - Skills: `[]` - No additional skill is required.
  - Omitted: [`frontend-design:frontend-design`] - These are paper figure prompts, not product mockups.

  **Parallelization**: Can Parallel: YES | Wave 2 | Blocks: 9, 10 | Blocked By: 1, 4

  **References** (executor has NO interview context - be exhaustive):
  - Journal structure rules: `docs/Survey paper/sample_style_notes.md`
  - Current system evidence: `docs/Survey paper/evidence_ledger.csv`
  - Comparison evidence: `docs/Survey paper/comparison_matrix.csv`
  - Shared bibliography/corpus: `docs/Survey paper/references.bib`, `docs/Survey paper/literature_corpus.csv`

  **Acceptance Criteria** (agent-executable only):
  - [ ] `docs/Survey paper/image_prompt_2.md` contains between 10 and 14 `FIGURE_ID:` entries.
  - [ ] Every journal figure ID is unique and follows `placeholder_fig_jNN` with no numbering gaps.
  - [ ] At least 2 entries use the exact marker `[PLACEMENT: Section — leave BLANK — to be replaced with real screenshot/demo image]`.
  - [ ] Every non-demo prompt paragraph is between 80 and 150 words.
  - [ ] No survey figure ID (`placeholder_fig_sNN`) appears in `image_prompt_2.md`.

  **QA Scenarios** (MANDATORY - task incomplete without these):
  ```
  Scenario: Happy path journal prompt audit
    Tool: Bash
    Steps: Populate `image_prompt_2.md`, then run a parser that counts entries, validates unique/contiguous `placeholder_fig_jNN` IDs, counts `leave BLANK` markers, and checks word counts for non-demo entries.
    Expected: Entry count is 10-14, IDs are valid, and at least 2 demo-image placeholders are present.
    Evidence: .sisyphus/evidence/task-08-journal-prompts.txt

  Scenario: Failure path cross-file ID audit
    Tool: Bash
    Steps: Compare `image_prompt_1.md` and `image_prompt_2.md` for overlapping figure IDs and scan `image_prompt_2.md` for missing `leave BLANK` markers on demo-image entries.
    Expected: No ID collisions exist and all demo-image entries use the exact required placement marker.
    Evidence: .sisyphus/evidence/task-08-journal-prompts-error.txt
  ```

  **Commit**: YES | Message: `docs(journal): add journal figure prompts` | Files: `docs/Survey paper/image_prompt_2.md`

- [ ] 9. Author `journal.tex` as the Ally Vision system/design paper

  **What to do**: Create `docs/Survey paper/journal.tex` as a new IEEE two-column conference paper using `\documentclass[conference]{IEEEtran}` and a package set compatible with the local sample/preamble pattern. The manuscript must use this exact section structure: `Abstract`; `Introduction`; `Related Work`; `System Architecture`; `Methodology`; `Experimental Setup`; `Results and Discussion`; `Conclusion`. Under `Related Work`, include 4-5 subsections that build toward Ally Vision’s need. Under `Results and Discussion`, include at least 3 `booktabs` tables built from `comparison_matrix.csv`, one ablation subsection, and one explicit limitations paragraph. Use the local HP OMEN 16-wf1xxx / i7-14650HX / RTX 4060 / ~13.7 GB RAM hardware only in `Experimental Setup`; do not present hardware as performance proof by itself. Cite at least 30 unique keys from `references.bib` and keep the journal thesis distinct from the survey thesis.
  **Must NOT do**: Must not duplicate survey-paper section flow or prose; must not present notebook numbers as freshly rerun results unless they were actually rerun and re-tagged; must not use banned phrases or leave placeholder metadata.

  **Recommended Agent Profile**:
  - Category: `writing` - Reason: This is the main system-paper authoring task with strong evidence and non-overlap constraints.
  - Skills: `[]` - No extra skill is required.
  - Omitted: [`superpowers:brainstorming`] - The manuscript thesis is fixed by this plan.

  **Parallelization**: Can Parallel: YES | Wave 2 | Blocks: 10 | Blocked By: 1, 2, 3, 4, 5, 8

  **References** (executor has NO interview context - be exhaustive):
  - New file to create: `docs/Survey paper/journal.tex`
  - Journal prompt alignment: `docs/Survey paper/image_prompt_2.md`
  - Shared bibliography: `docs/Survey paper/references.bib`
  - Corpus manifest: `docs/Survey paper/literature_corpus.csv`
  - Style rules and thesis split: `docs/Survey paper/sample_style_notes.md`
  - Current-system evidence: `docs/Survey paper/evidence_ledger.csv`
  - Notebook-result evidence: `docs/Survey paper/comparison_matrix.csv`
  - Hardware source resolved during planning: local system reports `OMEN by HP Gaming Laptop 16-wf1xxx`, Intel `i7-14650HX`, `NVIDIA GeForce RTX 4060 Laptop GPU`, ~13.7 GB RAM.

  **Acceptance Criteria** (agent-executable only):
  - [ ] `journal.tex` exists and begins with `\documentclass[conference]{IEEEtran}`.
  - [ ] `journal.tex` contains all 8 required section headings listed above.
  - [ ] `journal.tex` contains at least 4 `\subsection{}` blocks under `Related Work`.
  - [ ] `journal.tex` contains at least 2 `\begin{equation}` environments.
  - [ ] `journal.tex` contains at least 3 `\begin{table}` environments with `\toprule`, `\midrule`, and `\bottomrule`.
  - [ ] `journal.tex` contains between 10 and 14 `\includegraphics` placeholders whose filenames match the `FIGURE_ID` set in `image_prompt_2.md` exactly.
  - [ ] At least 2 figure placeholders correspond to demo-image entries with the `leave BLANK` placement rule.
  - [ ] `journal.tex` cites at least 30 unique keys from `references.bib`.
  - [ ] `journal.tex` contains no `\begin{itemize}` or `\begin{enumerate}` environments in the manuscript body.
  - [ ] The banned phrases list produces zero matches, and `state-of-the-art` appears no more than 2 times.

  **QA Scenarios** (MANDATORY - task incomplete without these):
  ```
  Scenario: Happy path journal manuscript audit
    Tool: Bash
    Steps: Create `journal.tex`, then run a LaTeX-source audit that checks documentclass, section headings, subsection count, equation count, table count, figure-ID parity against `image_prompt_2.md`, and unique citation-key count.
    Expected: All structure checks pass and at least 30 unique bibliography keys are cited.
    Evidence: .sisyphus/evidence/task-09-journal-tex.txt

  Scenario: Failure path overlap/banned-language audit
    Tool: Bash
    Steps: Compare `journal.tex` against `sample_style_notes.md` thesis notes and scan for banned phrases plus unresolved placeholders like `TODO`, `TBD`, or fake citation keys.
    Expected: The journal manuscript reflects the system/design thesis, not the survey thesis, and no banned-language/placeholders remain.
    Evidence: .sisyphus/evidence/task-09-journal-tex-error.txt
  ```

  **Commit**: YES | Message: `docs(journal): author ally vision system manuscript` | Files: `docs/Survey paper/journal.tex`, `docs/Survey paper/image_prompt_2.md`, `docs/Survey paper/references.bib`

- [ ] 10. Compile both manuscripts, resolve every reference/package error, and publish a build summary

  **What to do**: Before the first compile, create or refresh `docs/Survey paper/fig/` and generate compile-safe placeholder PNG assets for every `placeholder_fig_sNN` and `placeholder_fig_jNN` filename referenced by `main.tex` and `journal.tex`. Generate the PNGs from the figure IDs themselves (for example a plain white/gray canvas with the figure ID centered in black text) so `\includegraphics{...}` resolves without changing manuscript prose. After the placeholder assets exist, run a clean compile sequence from `docs/Survey paper/`: delete prior aux/build files, run `pdflatex -interaction=nonstopmode <file>.tex`, `bibtex <file>`, and `pdflatex -interaction=nonstopmode <file>.tex` twice more for `main.tex` and `journal.tex`. Fix every undefined citation, undefined label, missing package, missing figure path, Windows path escaping issue, and bibliography mismatch until both logs are clean. Produce a final build summary in `.sisyphus/evidence/task-10-build-summary.txt` containing page count, figure count, table count, equation count, and bibliography count for each paper.
  **Must NOT do**: Must not claim success after a warm build if a clean build still fails; must not leave `.aux`, `.log`, `.bbl`, `.blg`, `.out`, or `.pdf` files staged for commit; must not skip BibTeX if either manuscript uses the shared bibliography.

  **Recommended Agent Profile**:
  - Category: `unspecified-high` - Reason: This is a build/audit/fix loop combining shell execution and precise source corrections.
  - Skills: `[]` - No extra skill is required.
  - Omitted: [`superpowers:verification-before-completion`] - The task itself already encodes explicit verification gates.

  **Parallelization**: Can Parallel: NO | Wave 2 | Blocks: Final Verification | Blocked By: 1, 2, 3, 4, 5, 6, 7, 8, 9

  **References** (executor has NO interview context - be exhaustive):
  - Survey manuscript: `docs/Survey paper/main.tex`
  - Journal manuscript: `docs/Survey paper/journal.tex`
  - Shared bibliography: `docs/Survey paper/references.bib`
  - Survey prompts: `docs/Survey paper/image_prompt_1.md`
  - Journal prompts: `docs/Survey paper/image_prompt_2.md`
  - Corpus manifest: `docs/Survey paper/literature_corpus.csv`
  - Evidence sources for fix-backtracking: `docs/Survey paper/evidence_ledger.csv`, `docs/Survey paper/comparison_matrix.csv`, `docs/Survey paper/sample_style_notes.md`

  **Acceptance Criteria** (agent-executable only):
  - [ ] `docs/Survey paper/fig/` exists and contains one PNG for every `\includegraphics` placeholder referenced by `main.tex` and `journal.tex`.
  - [ ] A clean build sequence completes for `main.tex` with all commands exiting `0`.
  - [ ] A clean build sequence completes for `journal.tex` with all commands exiting `0`.
  - [ ] `main.log` contains zero matches for `Undefined citations`, `Reference .* undefined`, `LaTeX Error`, `Emergency stop`, and `File .* not found`.
  - [ ] `journal.log` contains zero matches for the same error patterns.
  - [ ] `.sisyphus/evidence/task-10-build-summary.txt` records page count, figure count, table count, equation count, and bibliography count for both papers.
  - [ ] `git status --short` shows no staged or modified LaTeX build artifacts (`.aux`, `.bbl`, `.blg`, `.log`, `.out`, `.pdf`).

  **QA Scenarios** (MANDATORY - task incomplete without these):
  ```
  Scenario: Happy path clean-build verification
    Tool: Bash
    Steps: Parse `main.tex` and `journal.tex` for every `\includegraphics{placeholder_fig_*}` reference; generate matching PNGs into `docs/Survey paper/fig/`; then in `docs/Survey paper/`, delete old aux/build files, run `pdflatex -interaction=nonstopmode main.tex`, `bibtex main`, `pdflatex -interaction=nonstopmode main.tex`, `pdflatex -interaction=nonstopmode main.tex`, then repeat the same sequence for `journal.tex`; parse `main.log` and `journal.log` for banned warning/error patterns; generate `.sisyphus/evidence/task-10-build-summary.txt` from log/source counts.
    Expected: All referenced placeholder PNGs exist before compilation, both clean build pipelines complete with zero forbidden warning/error matches, and the summary file is populated.
    Evidence: .sisyphus/evidence/task-10-build-summary.txt

  Scenario: Failure path stale-build-artifact audit
    Tool: Bash
    Steps: After a successful build, run `git status --short` and search for staged or modified `.aux`, `.bbl`, `.blg`, `.log`, `.out`, or `.pdf` files; also rerun the warning-pattern scan after deleting aux files to prove clean-build stability.
    Expected: No build artifacts remain staged/dirty and the clean rebuild reproduces the same warning-free result.
    Evidence: .sisyphus/evidence/task-10-build-summary-error.txt
  ```

  **Commit**: YES | Message: `chore(latex): fix references and validate manuscript builds` | Files: `docs/Survey paper/main.tex`, `docs/Survey paper/journal.tex`, `docs/Survey paper/references.bib`, `docs/Survey paper/image_prompt_1.md`, `docs/Survey paper/image_prompt_2.md`, `docs/Survey paper/evidence_ledger.csv`, `docs/Survey paper/comparison_matrix.csv`, `docs/Survey paper/literature_corpus.csv`, `docs/Survey paper/sample_style_notes.md`

## Final Verification Wave (MANDATORY — after ALL implementation tasks)
> 4 review agents run in PARALLEL. ALL must APPROVE. Present consolidated results to user and get explicit "okay" before completing.
> **Do NOT auto-proceed after verification. Wait for user's explicit approval before marking work complete.**
> **Never mark F1-F4 as checked before getting user's okay.** Rejection or user feedback -> fix -> re-run -> present again -> wait for okay.
- [ ] F1. Plan Compliance Audit — oracle
  - Tool: `task(subagent_type="oracle")`
  - Steps: Compare the completed artifacts against this plan’s required deliverables, task-level acceptance criteria, and dependency expectations; verify that every required file exists and that Task 10’s summary backs the claimed completion.
  - Expected: Oracle returns an explicit approval verdict with zero missing deliverables or unmet acceptance criteria.
  - Evidence: `.sisyphus/evidence/f1-plan-compliance.md`
- [ ] F2. Code Quality Review — unspecified-high
  - Tool: `task(category="unspecified-high")`
  - Steps: Inspect `main.tex`, `journal.tex`, `references.bib`, both image-prompt files, and the support CSV/notes files for structural cleanliness, placeholder leakage, malformed BibTeX, banned phrases, and obvious LaTeX/source quality issues.
  - Expected: Reviewer returns `APPROVE` with no blocking manuscript-quality issues.
  - Evidence: `.sisyphus/evidence/f2-quality-review.md`
- [ ] F3. Real Manual QA — unspecified-high (+ playwright if UI)
  - Tool: `task(category="unspecified-high")`
  - Steps: Re-run the clean build sequence independently, inspect the generated PDFs/logs/text extraction outputs, and verify that page/figure/table/equation/reference counts in `.sisyphus/evidence/task-10-build-summary.txt` match the actual artifacts.
  - Expected: Independent QA confirms the build is reproducible and the summary counts are accurate.
  - Evidence: `.sisyphus/evidence/f3-manual-qa.md`
- [ ] F4. Scope Fidelity Check — deep
  - Tool: `task(category="deep")`
  - Steps: Audit the final manuscripts against `evidence_ledger.csv`, `comparison_matrix.csv`, and the banned-current-state list from this plan; verify that unsupported capabilities and unlabeled future-work claims do not appear as implemented current behavior.
  - Expected: Reviewer returns `APPROVE` with zero unsupported-current-state claims.
  - Evidence: `.sisyphus/evidence/f4-scope-fidelity.md`

## Commit Strategy
- Do not commit generated LaTeX build artifacts (`.aux`, `.bbl`, `.blg`, `.log`, `.out`, `.pdf`).
- First commit point: shared research assets (`references.bib`, `literature_corpus.csv`, `comparison_matrix.csv`, `evidence_ledger.csv`, `sample_style_notes.md`).
- Second commit point: survey outputs (`image_prompt_1.md`, `main.tex`).
- Third commit point: journal outputs (`image_prompt_2.md`, `journal.tex`).
- Final commit point: compilation fixes and source-only cleanup after Task 10.

## Success Criteria
- Survey manuscript accurately reflects the current field landscape and uses Ally Vision only as a motivating/current-system anchor.
- Journal manuscript accurately reflects the checked-in Ally Vision implementation and comparison-driven design rationale.
- Exactly 50 unique peer-reviewed references exist in the shared BibTeX file and are traceable through the corpus manifest.
- Both manuscripts compile cleanly in the local Windows environment after toolchain bootstrap.
- Every quantitative claim in the final PDFs is traceable either to current code/test evidence, notebook-extracted evidence, or verified literature.
