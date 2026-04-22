"""Automatic fact extraction via DashScope-compatible chat completions."""

from __future__ import annotations

import json
import logging

import httpx

from apps.backend.services.shared_http import get_compat_http_client
from shared.config import settings

logger = logging.getLogger(__name__)


class Mem0Extractor:
    def __init__(self, api_key: str, base_url: str, model: str) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model
        self._http: httpx.AsyncClient | None = None

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
        system_prompt = """
You are a personal fact extractor for an AI assistant.
Your ONLY job: extract personal facts about the USER from
the conversation below. Output a JSON array.

Rules:
- Extract ONLY facts about the USER (not about their surroundings)
- Output clean, normalized facts — NOT raw sentences
- Each fact must be a simple statement like:
    "User's name is Om Shivarajan"
    "User lives in Hosur"
    "User's doctor is Dr. Sharma"
- If no personal facts exist -> output []
- Never include scene descriptions as facts
- Never include questions as facts
- Extract from ANY language (Kannada, Hindi, English, Tamil)
- If user said their name in any language -> normalize to English fact

Output format (ONLY JSON, no markdown, no explanation):
[
  {"fact": "User's name is Om Shivarajan", "category": "NAME", "tier": "long"},
  {"fact": "User lives in Hosur", "category": "LOCATION", "tier": "long"}
]

Categories: NAME, LOCATION, MEDICAL, PREFERENCE, RELATIONSHIP, GENERAL

Examples of correct extraction:
User: "My name is Om Shivarajan" -> [{"fact":"User's name is Om Shivarajan","category":"NAME","tier":"long"}]
User: "So my name is Om Shivarajan. Can you store it?" -> [{"fact":"User's name is Om Shivarajan","category":"NAME","tier":"long"}]
User: "ನನ್ನ ಹೆಸರು ಓಂ ಶಿವರಾಜನ್" -> [{"fact":"User's name is Om Shivarajan","category":"NAME","tier":"long"}]
User: "मेरा नाम ओम है" -> [{"fact":"User's name is Om","category":"NAME","tier":"long"}]
User: "Actually my city is Bengaluru, update that" -> [{"fact":"User's city is Bengaluru","category":"LOCATION","tier":"long"}]
User: "ok." -> []
User: "嗯。" -> []
Scene: "You are wearing glasses..." -> []
""".strip()
        user_message = (
            f'USER said: "{user_transcript}"\n'
            f'ASSISTANT said: "{assistant_transcript}"\n'
            "Extract personal facts about the USER only."
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
            resp = await self._get_http().post(
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
                ):
                    valid.append(
                        {
                            "fact": str(fact["fact"]),
                            "category": str(fact["category"]),
                            "tier": str(fact.get("tier", "long")),
                        }
                    )
            return valid
        except Exception as exc:
            logger.warning("Mem0Extractor.extract failed: %s", exc)
            return []

    def _get_http(self) -> httpx.AsyncClient:
        shared = get_compat_http_client()
        if shared is not None:
            return shared
        if self._http is None:
            self._http = httpx.AsyncClient(timeout=8.0)
        return self._http

    async def close(self) -> None:
        if self._http is not None:
            await self._http.aclose()
            self._http = None
