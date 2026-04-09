"""
Ally Vision v2 — Policy router.

Maps IntentCategory to RouteTarget and injects
system instructions into Qwen turns.

Only DOCUMENT_QA remains unimplemented and falls back
to REALTIME_CHAT until a later plan wires it.
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
    TRANSLATE = "TRANSLATE"
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
        RouteTarget.REALTIME_CHAT,
        False,
        "You are Ally, a voice assistant for blind and visually impaired users. "
        "The user is asking a question that requires current, real-world information "
        "such as live scores, news, weather, prices, or recent events. "
        "You MUST answer the user's actual question directly. "
        "Do NOT describe the camera scene. "
        "Do NOT say you cannot access the internet. "
        "Use your built-in knowledge to give the best available answer. "
        "If the answer may be time-sensitive (e.g. live cricket score), clearly say: "
        '"As of my last update, [answer]. For the live score, please check '
        'a live cricket app or website." '
        "Always be specific, helpful, and concise. "
        "Speak in the same language the user used.",
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
    IntentCategory.TRANSLATE: (
        RouteTarget.REALTIME_CHAT,
        False,
        "Translate what the user said or what is visible "
        "in the image to the requested language. "
        "If no target language specified, detect the source "
        "language and translate to English. "
        "Speak the translation clearly.",
    ),
    IntentCategory.GENERAL_CHAT: (
        RouteTarget.REALTIME_CHAT,
        False,
        "You are Ally, a voice assistant for blind and visually impaired users. "
        "Answer the user's question directly and helpfully. "
        "Do NOT describe the camera scene unless the user explicitly asks about it. "
        "Do NOT volunteer information about what you see. "
        "Respond in the same language the user used. "
        "Keep responses concise and clear — you are speaking, not writing.",
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
