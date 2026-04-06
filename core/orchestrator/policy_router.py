"""
Ally Vision v2 — Policy router.

Maps IntentCategory to RouteTarget and injects
system instructions into Qwen turns.

Unimplemented targets (WEB_SEARCH, MEMORY_WRITE,
MEMORY_READ, DOCUMENT_QA) fall back to REALTIME_CHAT
until Plans 07-09 implement those services.
"""

from __future__ import annotations

import enum
import logging
from dataclasses import dataclass

from core.orchestrator.intent_classifier import IntentCategory

logger = logging.getLogger("ally-policy-router")


class RouteTarget(str, enum.Enum):
    REALTIME_CHAT = "REALTIME_CHAT"
    HEAVY_VISION = "HEAVY_VISION"
    WEB_SEARCH = "WEB_SEARCH"
    MEMORY_WRITE = "MEMORY_WRITE"
    MEMORY_READ = "MEMORY_READ"
    DOCUMENT_QA = "DOCUMENT_QA"


@dataclass
class RoutingDecision:
    target: RouteTarget
    intent: IntentCategory
    requires_frame: bool
    system_instructions: str


_UNIMPLEMENTED = {
    RouteTarget.WEB_SEARCH,
    RouteTarget.MEMORY_WRITE,
    RouteTarget.MEMORY_READ,
    RouteTarget.DOCUMENT_QA,
}

_ROUTING_TABLE: dict[IntentCategory, tuple[RouteTarget, bool, str]] = {
    IntentCategory.SCENE_DESCRIBE: (
        RouteTarget.REALTIME_CHAT,
        True,
        "Describe what you see in the camera image. "
        "Be specific about objects, their positions, and distances.",
    ),
    IntentCategory.READ_TEXT: (
        RouteTarget.HEAVY_VISION,
        True,
        "Read all visible text in the image. Be precise and complete.",
    ),
    IntentCategory.SCAN_PAGE: (
        RouteTarget.HEAVY_VISION,
        True,
        "Capture and describe this document page for later reference.",
    ),
    IntentCategory.WEB_SEARCH: (
        RouteTarget.WEB_SEARCH,
        False,
        "Search the web for this information.",
    ),
    IntentCategory.MEMORY_SAVE: (
        RouteTarget.MEMORY_WRITE,
        False,
        "Save this information to memory.",
    ),
    IntentCategory.MEMORY_RECALL: (
        RouteTarget.MEMORY_READ,
        False,
        "Recall relevant stored information.",
    ),
    IntentCategory.DOCUMENT_QA: (
        RouteTarget.DOCUMENT_QA,
        False,
        "Answer from the scanned document.",
    ),
    IntentCategory.GENERAL_CHAT: (
        RouteTarget.REALTIME_CHAT,
        False,
        "",
    ),
}


def route(intent: IntentCategory) -> RoutingDecision:
    """
    Return a RoutingDecision for the given intent.
    Unimplemented targets are logged and fall back to REALTIME_CHAT.
    """
    target, requires_frame, instructions = _ROUTING_TABLE[intent]

    if target in _UNIMPLEMENTED:
        logger.info(
            "Predicted route %s for intent %s not implemented yet → applying REALTIME_CHAT fallback",
            target.value,
            intent.value,
        )
        return RoutingDecision(
            target=RouteTarget.REALTIME_CHAT,
            intent=intent,
            requires_frame=False,
            system_instructions="",
        )

    return RoutingDecision(
        target=target,
        intent=intent,
        requires_frame=requires_frame,
        system_instructions=instructions,
    )
