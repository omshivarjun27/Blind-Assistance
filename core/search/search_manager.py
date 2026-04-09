import logging

import httpx

from shared.config import settings

logger = logging.getLogger(__name__)

_FALLBACK = "I was unable to search for that right now."


class SearchError(Exception):
    pass


class SearchManager:
    def __init__(self, api_key: str, base_url: str, model: str) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model

    @classmethod
    def from_settings(cls) -> "SearchManager":
        return cls(
            api_key=settings.get_api_key(),
            base_url=settings.DASHSCOPE_COMPAT_BASE,
            model=settings.QWEN_TURBO_MODEL,
        )

    async def search(self, query: str) -> str:
        """
        Call qwen-turbo with enable_search=True via compat chat/completions.
        Always returns a string. Never raises.
        """
        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": query}],
            "enable_search": True,
            "search_options": {"forced_search": True},
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.post(
                    f"{self.base_url}/chat/completions",
                    json=payload,
                    headers=headers,
                )
                resp.raise_for_status()
                content = resp.json()["choices"][0]["message"]["content"]
                return content.strip() if content else _FALLBACK
        except Exception as exc:
            logger.warning("SearchManager.search failed for %r: %s", query, exc)
            return _FALLBACK
