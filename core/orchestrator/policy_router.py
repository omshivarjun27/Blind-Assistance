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
        "You are Ally, a voice assistant for blind and visually impaired users. "
        "The user has just opened the app or pointed their camera at a scene. "
        "Describe what you see in the camera clearly and concisely — focus on "
        "people, objects, text, and spatial layout. Speak naturally. "
        "This is a ONE-TIME scene description for this turn only. "
        "After this turn, do NOT describe the scene again unless the user "
        "explicitly asks you to. Wait for the user's question and answer it directly.",
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
        "Answer the user's question directly, helpfully, and concisely. "
        "Do NOT describe the camera scene. Do NOT mention what you see. "
        "Do NOT say you cannot browse the internet or access live data. "
        "Use your knowledge to give the best available answer. "
        "If the answer may be time-sensitive (live scores, weather, prices), "
        'say: "Based on my last update: [answer]. For live data, please use '
        'a dedicated app." '
        "Speak in the same language the user used. Keep it brief — you are "
        "speaking, not writing.",
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
