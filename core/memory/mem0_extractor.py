"""Automatic fact extraction via DashScope-compatible chat completions."""

from __future__ import annotations

import json
import logging

import httpx

from shared.config import settings

logger = logging.getLogger(__name__)


class Mem0Extractor:
    def __init__(self, api_key: str, base_url: str, model: str) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model

    @classmethod
    def from_settings(cls) -> "Mem0Extractor":
        return cls(
            api_key=settings.get_api_key(),
            base_url=settings.DASHSCOPE_COMPAT_BASE,
            model=settings.QWEN_TURBO_MODEL,
        )

    async def extract(
        self, user_transcript: str, assistant_transcript: str
    ) -> list[dict[str, str]]:
        """
        Call qwen-turbo to extract persistent user facts.
        Returns list of {fact: str, category: str, tier: "long"|"short"}.
        Returns [] on any failure — never raises.
        """
        system_prompt = (
            "Extract persistent user facts from this exchange only. "
            'Return a JSON array [{"fact": str, "category": str, "tier": str}] or []. '
            "Categories: IDENTITY, LOCATION, HEALTH, PREFERENCE, RELATIONSHIP, CONVERSATION, OBSERVATION. "
            "tier=long for persistent facts (name, address, preferences, relationships). "
            "tier=short for temporary observations and recent state. "
            "Never extract assistant statements as user facts. "
            "Return only [] if nothing is extractable."
        )
        user_message = (
            f"User said: {user_transcript}\nAssistant replied: {assistant_transcript}"
        )
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        try:
            async with httpx.AsyncClient(timeout=8.0) as client:
                resp = await client.post(
                    f"{self.base_url}/chat/completions",
                    json=payload,
                    headers=headers,
                )
                resp.raise_for_status()
                content = resp.json()["choices"][0]["message"]["content"]
                content = content.strip()
                if content.startswith("```"):
                    parts = content.split("```")
                    if len(parts) >= 2:
                        content = parts[1]
                    if content.startswith("json"):
                        content = content[4:]
                    content = content.strip()
                facts = json.loads(content)
                if not isinstance(facts, list):
                    return []
                valid: list[dict[str, str]] = []
                for fact in facts:
                    if (
                        isinstance(fact, dict)
                        and "fact" in fact
                        and "category" in fact
                        and "tier" in fact
                    ):
                        valid.append(fact)
                return valid
        except Exception as exc:
            logger.warning("Mem0Extractor.extract failed: %s", exc)
            return []
