"""
Ally Vision v2 — Intent classifier using qwen-turbo.

Classifies user transcript into one of 8 intent categories.
Uses DashScope compatible mode (text-only, fast, cheap).
Falls back to GENERAL_CHAT on any error — never blocks a turn.

IMPORTANT: Classification uses the PREVIOUS turn's transcript.
Current turn transcript arrives WITH the Qwen response, not before.
"""

from __future__ import annotations

import enum
import logging
from dataclasses import dataclass
from typing import Optional

import httpx

logger = logging.getLogger("ally-intent-classifier")

_LABELS = [
    "SCENE_DESCRIBE",
    "READ_TEXT",
    "SCAN_PAGE",
    "MEMORY_SAVE",
    "MEMORY_RECALL",
    "DOCUMENT_QA",
    "TRANSLATE",
    "GENERAL_CHAT",
]

_CLASSIFICATION_PROMPT = (
    "Classify this user request into exactly one of: "
    "SCENE_DESCRIBE, READ_TEXT, SCAN_PAGE, "
    "MEMORY_SAVE, MEMORY_RECALL, DOCUMENT_QA, "
    "TRANSLATE, GENERAL_CHAT. "
    "TRANSLATE covers: translate this, what language is this, "
    "translate to Hindi, translate to English, etc. "
    "Reply with ONLY the category name, nothing else.\n"
    "Request: {transcript}"
)


class IntentCategory(str, enum.Enum):
    SCENE_DESCRIBE = "SCENE_DESCRIBE"
    READ_TEXT = "READ_TEXT"
    SCAN_PAGE = "SCAN_PAGE"
    MEMORY_SAVE = "MEMORY_SAVE"
    MEMORY_RECALL = "MEMORY_RECALL"
    DOCUMENT_QA = "DOCUMENT_QA"
    TRANSLATE = "TRANSLATE"
    GENERAL_CHAT = "GENERAL_CHAT"


@dataclass
class ClassificationResult:
    intent: IntentCategory
    confidence: str  # "high" or "low"
    raw_label: str
    error: Optional[str] = None


def _fallback(error: Optional[str] = None) -> ClassificationResult:
    return ClassificationResult(
        intent=IntentCategory.GENERAL_CHAT,
        confidence="low",
        raw_label="",
        error=error,
    )


class IntentClassifier:
    """
    Classifies user speech transcript using qwen-turbo.
    Falls back silently to GENERAL_CHAT on any failure.
    """

    def __init__(
        self,
        api_key: str,
        model: str = "qwen-turbo",
        base_url: str = "https://dashscope-intl.aliyuncs.com/compatible-mode/v1",
    ) -> None:
        self._api_key = api_key
        self._model = model
        self._base_url = base_url.rstrip("/")

    @classmethod
    def from_settings(cls) -> "IntentClassifier":
        from shared.config.settings import DASHSCOPE_COMPAT_BASE, get_api_key

        return cls(
            api_key=get_api_key(),
            base_url=DASHSCOPE_COMPAT_BASE,
        )

    async def classify(self, transcript: str) -> ClassificationResult:
        """
        Classify transcript. Returns GENERAL_CHAT on empty input or error.
        Never raises — always returns a result.
        Timeout: 3 seconds.
        """
        if not transcript or not transcript.strip():
            return ClassificationResult(
                intent=IntentCategory.GENERAL_CHAT,
                confidence="high",
                raw_label="",
            )

        prompt = _CLASSIFICATION_PROMPT.format(transcript=transcript.strip())

        try:
            async with httpx.AsyncClient(timeout=3.0) as client:
                resp = await client.post(
                    f"{self._base_url}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self._api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": self._model,
                        "messages": [{"role": "user", "content": prompt}],
                        "max_tokens": 20,
                    },
                )
                resp.raise_for_status()
                data = resp.json()
                raw = data["choices"][0]["message"]["content"].strip().upper()
                raw_clean = raw.strip(".,!? ")

                if raw_clean in _LABELS:
                    return ClassificationResult(
                        intent=IntentCategory(raw_clean),
                        confidence="high",
                        raw_label=raw,
                    )

                logger.debug(
                    "Unexpected classifier label: %r → GENERAL_CHAT",
                    raw,
                )
                return ClassificationResult(
                    intent=IntentCategory.GENERAL_CHAT,
                    confidence="low",
                    raw_label=raw,
                )

        except Exception as exc:
            logger.warning("Intent classification failed: %s", exc)
            return _fallback(error=str(exc))
