# Ally Vision v2 — Agent Rules

## Project
Blind-first voice+vision web assistant.
DashScope only. SQLite only. No local models.
Runs on laptop browser. Voice + camera + memory.

## Two-Agent System

PROMETHEUS (Claude Sonnet 4.6 via Anthropic API direct)
  Role: Writes plan files ONLY. Never executes code.
  Use: Before every new implementation plan.
  Output: One .sisyphus/plans/NN-name.md file.

HEPHAESTUS (GPT-5.4 via ChatGPT Plus OAuth)
  Role: Executes plans ONLY. Never writes plans.
  Use: After Prometheus writes a plan.
  Output: Working code + passing tests + git commit.

## Gate Phrase
Hephaestus MUST NOT advance to next plan until
user physically verifies and types exact phrase:
  real world verified and codebase verified and continue

## Absolute Rules
1. NEVER run: pytest tests/ (all at once)
   ALWAYS run: pytest tests/unit/[file].py -v --timeout=30 -x
2. NEVER commit .env
3. NEVER edit code without reading it first
4. NEVER delete files before verifying zero callers
5. NEVER use .md files as source of truth for code
6. NEVER use Bedrock (caps context, 10x cost)
7. NEVER add always-on processing features
8. ALWAYS run LSP diagnostics after file edits
9. ALWAYS verify DashScope docs with Tavily
10. ALWAYS commit plan files separately from code

## Paths
Project:  C:/ally-vision-v2/
Venv:     C:/ally-vision-v2/.venv/Scripts/
Python:   C:/ally-vision-v2/.venv/Scripts/python.exe
Pytest:   C:/ally-vision-v2/.venv/Scripts/pytest.exe
Plans:    .sisyphus/plans/

## Profile Switch
PROFILE=dev  → qwen3.5-omni-flash-realtime + qwen3.5-flash
PROFILE=exam → qwen3.5-omni-plus-realtime  + qwen3.6-plus

## Stack
Backend:  FastAPI + Python 3.11 + aiosqlite
Frontend: Next.js + React + TypeScript + Tailwind
Cloud:    DashScope only (one API key)
Storage:  SQLite only (no FAISS, no vector DB)
