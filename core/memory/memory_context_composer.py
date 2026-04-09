"""Helpers for composing structured memory context."""

from __future__ import annotations


def compose_memory_context(
    session_turns: list[dict[str, str]],
    st_facts: str | None,
    lt_facts: str | None,
    objects_seen: list[dict[str, str]],
) -> str:
    parts: list[str] = []
    if session_turns or objects_seen:
        section = ["From this session:"]
        for turn in session_turns:
            section.append(f"  User: {turn.get('user', '')}")
            section.append(f"  Ally: {turn.get('assistant', '')}")
        for obj in objects_seen:
            section.append(f"  Saw: {obj.get('object_desc', '')}")
        parts.append("\n".join(section))
    if st_facts:
        parts.append(f"From recent memory:\n  {st_facts}")
    if lt_facts:
        parts.append(f"From long-term memory:\n  {lt_facts}")
    return "\n\n".join(parts)
