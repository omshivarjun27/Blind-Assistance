"""Tests for Plan 05: PromptBuilder."""

from __future__ import annotations


def test_build_system_prompt_base_only():
    from core.orchestrator.prompt_builder import build_system_prompt

    result = build_system_prompt("Describe the scene.")
    assert result == "Describe the scene."


def test_build_system_prompt_combines_memory():
    from core.orchestrator.prompt_builder import build_system_prompt

    result = build_system_prompt(
        "Answer the question.",
        memory_context="User's doctor is Dr. Sharma.",
    )
    assert "Answer the question." in result
    assert "Dr. Sharma" in result


def test_build_system_prompt_combines_document():
    from core.orchestrator.prompt_builder import build_system_prompt

    result = build_system_prompt(
        "Summarize.",
        document_context="Page 1: Introduction to AI.",
    )
    assert "Summarize." in result
    assert "Introduction to AI" in result


def test_build_system_prompt_no_blank_sections():
    from core.orchestrator.prompt_builder import build_system_prompt

    result = build_system_prompt("Base.", memory_context="", document_context="")
    assert result == "Base."
    assert "\n\n\n" not in result


def test_build_search_query_strips_search_for():
    from core.orchestrator.prompt_builder import build_search_query

    assert build_search_query("search for the weather") == "the weather"


def test_build_search_query_strips_look_up():
    from core.orchestrator.prompt_builder import build_search_query

    assert build_search_query("look up pizza recipes") == "pizza recipes"


def test_build_search_query_no_prefix():
    from core.orchestrator.prompt_builder import build_search_query

    assert build_search_query("current temperature") == "current temperature"


def test_build_memory_fact_strips_remember():
    from core.orchestrator.prompt_builder import build_memory_fact

    result = build_memory_fact("remember my doctor is Dr Sharma")
    assert "Dr Sharma" in result
    assert "remember" not in result.lower()


def test_build_memory_fact_strips_save_this():
    from core.orchestrator.prompt_builder import build_memory_fact

    result = build_memory_fact("save this my birthday is January 5")
    assert "birthday" in result


def test_build_memory_fact_strips_please_memorize_that():
    from core.orchestrator.prompt_builder import build_memory_fact

    result = build_memory_fact("please memorize that my name is Om")
    assert result == "my name is Om"
