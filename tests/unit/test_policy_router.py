"""Tests for Plan 05: PolicyRouter."""

from __future__ import annotations


def test_scene_describe_routes_to_realtime_with_frame():
    from core.orchestrator.intent_classifier import IntentCategory
    from core.orchestrator.policy_router import RouteTarget, route

    decision = route(IntentCategory.SCENE_DESCRIBE)
    assert decision.target == RouteTarget.REALTIME_CHAT
    assert decision.requires_frame is True
    assert decision.system_instructions != ""


def test_read_text_routes_to_heavy_vision():
    from core.orchestrator.intent_classifier import IntentCategory
    from core.orchestrator.policy_router import RouteTarget, route

    decision = route(IntentCategory.READ_TEXT)
    assert decision.target == RouteTarget.HEAVY_VISION
    assert decision.requires_frame is True


def test_general_chat_no_frame_needed():
    from core.orchestrator.intent_classifier import IntentCategory
    from core.orchestrator.policy_router import RouteTarget, route

    decision = route(IntentCategory.GENERAL_CHAT)
    assert decision.target == RouteTarget.REALTIME_CHAT
    assert decision.requires_frame is False
    assert "Do NOT describe the camera scene" in decision.system_instructions


def test_translate_routes_to_realtime_chat_with_instructions():
    from core.orchestrator.intent_classifier import IntentCategory
    from core.orchestrator.policy_router import RouteTarget, route

    decision = route(IntentCategory.TRANSLATE)
    assert decision.target == RouteTarget.REALTIME_CHAT
    assert decision.requires_frame is False
    assert "Translate" in decision.system_instructions


def test_all_intents_have_routing():
    """Every IntentCategory must produce a RoutingDecision without error."""
    from core.orchestrator.intent_classifier import IntentCategory
    from core.orchestrator.policy_router import route

    for intent in IntentCategory:
        decision = route(intent)
        assert decision is not None
        assert decision.target is not None


def test_scan_page_routes_to_heavy_vision():
    from core.orchestrator.intent_classifier import IntentCategory
    from core.orchestrator.policy_router import RouteTarget, route

    decision = route(IntentCategory.SCAN_PAGE)
    assert decision.target == RouteTarget.HEAVY_VISION
    assert decision.requires_frame is True


def test_memory_write_is_implemented():
    from core.orchestrator.intent_classifier import IntentCategory
    from core.orchestrator.policy_router import RouteTarget, route

    decision = route(IntentCategory.MEMORY_SAVE)
    assert decision.target == RouteTarget.MEMORY_WRITE


def test_memory_read_is_implemented():
    from core.orchestrator.intent_classifier import IntentCategory
    from core.orchestrator.policy_router import RouteTarget, route

    decision = route(IntentCategory.MEMORY_RECALL)
    assert decision.target == RouteTarget.MEMORY_READ
