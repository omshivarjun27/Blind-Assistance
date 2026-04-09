"""In-memory session memory for recent turns and objects seen."""

from __future__ import annotations

import collections
import datetime


class SessionMemory:
    def __init__(self, max_turns: int = 20) -> None:
        self._turns: collections.deque[dict[str, str]] = collections.deque(
            maxlen=max_turns
        )
        self._objects: collections.deque[dict[str, str]] = collections.deque(
            maxlen=max_turns
        )

    def add_turn(
        self,
        user_transcript: str,
        assistant_response: str,
        vision_objects: list[str] | None = None,
    ) -> None:
        timestamp = datetime.datetime.utcnow().isoformat()
        self._turns.append(
            {
                "user": user_transcript,
                "assistant": assistant_response,
                "timestamp": timestamp,
            }
        )
        if vision_objects:
            for object_desc in vision_objects:
                self._objects.append(
                    {
                        "object_desc": object_desc,
                        "timestamp": timestamp,
                    }
                )

    def get_recent(self, n: int = 5) -> list[dict[str, str]]:
        if n <= 0:
            return []
        return list(self._turns)[-n:]

    def get_objects_seen(self) -> list[dict[str, str]]:
        return list(self._objects)

    def clear(self) -> None:
        self._turns.clear()
        self._objects.clear()
