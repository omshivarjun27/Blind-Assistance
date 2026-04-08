"""Ally Vision v2 — DashScope text-embedding-v4 client."""

from __future__ import annotations

import httpx

from shared.config import settings


class EmbeddingError(Exception):
    pass


class EmbeddingClient:
    def __init__(
        self, api_key: str, base_url: str, model: str, dimensions: int
    ) -> None:
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._dimensions = dimensions

    @classmethod
    def from_settings(cls) -> "EmbeddingClient":
        return cls(
            api_key=settings.get_api_key(),
            base_url=settings.DASHSCOPE_COMPAT_BASE,
            model=settings.EMBEDDING_MODEL,
            dimensions=settings.EMBEDDING_DIMENSIONS,
        )

    async def embed(self, text: str) -> list[float]:
        """Embed text using text-embedding-v4.

        Returns list[float] of length self._dimensions.
        Raises EmbeddingError on any failure.
        Never returns an empty list silently.
        """
        url = f"{self._base_url}/embeddings"
        payload = {
            "model": self._model,
            "input": text,
            "dimensions": self._dimensions,
            "encoding_format": "float",
        }
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(url, json=payload, headers=headers)
                response.raise_for_status()
                data = response.json()
                embedding: list[float] = data["data"][0]["embedding"]
                if len(embedding) != self._dimensions:
                    raise EmbeddingError(
                        f"Expected {self._dimensions} dims, got {len(embedding)}"
                    )
                return embedding
        except EmbeddingError:
            raise
        except Exception as exc:
            raise EmbeddingError(f"Embedding call failed: {exc}") from exc
