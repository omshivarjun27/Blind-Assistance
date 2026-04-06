"""
Ally Vision v2 — Prompt builder utilities.

Combines base instructions with optional memory and document
context. Extracts clean search queries and memory facts.
"""

from __future__ import annotations

import re

_SEARCH_PREFIXES = re.compile(
    r"^(search\s+(for\s+)?|look\s+up\s+|find\s+(online\s+)?)",
    re.IGNORECASE,
)

_MEMORY_PREFIXES = re.compile(
    r"^(remember\s+(that\s+)?|save\s+(this\s+)?|note\s+(that\s+)?)",
    re.IGNORECASE,
)


def build_system_prompt(
    base_instructions: str,
    memory_context: str = "",
    document_context: str = "",
) -> str:
    """
    Combine base instructions with optional memory and document context.
    Avoids leading/trailing blank sections.
    """
    parts = [base_instructions.strip()]
    if memory_context.strip():
        parts.append(f"Relevant memory:\n{memory_context.strip()}")
    if document_context.strip():
        parts.append(f"Document context:\n{document_context.strip()}")
    return "\n\n".join(p for p in parts if p)


def build_search_query(transcript: str) -> str:
    """
    Extract clean search query from user speech.
    Strips leading search-intent phrases.
    """
    cleaned = _SEARCH_PREFIXES.sub("", transcript.strip())
    return cleaned.strip()


def build_memory_fact(transcript: str) -> str:
    """
    Extract fact to save from user speech.
    Strips leading memory-save phrases.
    """
    cleaned = _MEMORY_PREFIXES.sub("", transcript.strip())
    return cleaned.strip()
