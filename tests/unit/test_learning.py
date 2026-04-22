import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import aiosqlite
import pytest

from apps.backend.db.bootstrap import bootstrap_learning_tables
from core.learning import (
    CorrectionStore,
    OfflineReplay,
    OnlineReflection,
    PatchStore,
    Rollback,
)
from core.orchestrator.prompt_builder import build_system_prompt


async def _make_learning_db(tmp_path, name: str = "learning.sqlite") -> str:
    db_path = str(tmp_path / name)
    await bootstrap_learning_tables(db_path)
    return db_path


@pytest.mark.asyncio
async def test_log_correction_stores_row(tmp_path):
    db_path = await _make_learning_db(tmp_path)
    store = CorrectionStore(db_path=db_path)

    await store.log_correction(
        session_id="s1",
        turn_id="t1",
        transcript="that's wrong",
        response="answer",
        signal="that's wrong",
        intent="GENERAL_CHAT",
    )

    async with aiosqlite.connect(db_path) as db:
        cursor = await db.execute(
            "SELECT correction_signal, intent_at_time FROM correction_log"
        )
        row = await cursor.fetchone()

    assert row == ("that's wrong", "GENERAL_CHAT")


@pytest.mark.asyncio
async def test_log_turn_stores_transcript_history(tmp_path):
    db_path = await _make_learning_db(tmp_path)
    store = CorrectionStore(db_path=db_path)

    await store.log_turn(
        session_id="s1",
        turn_id="t1",
        transcript="hello",
        response="hi",
        intent="GENERAL_CHAT",
        route_target="RouteTarget.REALTIME_CHAT",
    )

    async with aiosqlite.connect(db_path) as db:
        cursor = await db.execute(
            "SELECT user_transcript, assistant_response FROM transcript_log"
        )
        row = await cursor.fetchone()

    assert row == ("hello", "hi")


@pytest.mark.asyncio
async def test_get_corrections_returns_list(tmp_path):
    db_path = await _make_learning_db(tmp_path)
    store = CorrectionStore(db_path=db_path)

    await store.log_correction("s1", "t1", "wrong", "answer", "wrong", "GENERAL")
    result = await store.get_corrections()

    assert isinstance(result, list)
    assert len(result) == 1
    assert result[0]["session_id"] == "s1"


@pytest.mark.asyncio
async def test_get_corrections_filtered_by_session(tmp_path):
    db_path = await _make_learning_db(tmp_path)
    store = CorrectionStore(db_path=db_path)

    await store.log_correction("s1", "t1", "wrong", "answer", "wrong", "GENERAL")
    await store.log_correction("s2", "t2", "wrong", "answer", "wrong", "GENERAL")

    result = await store.get_corrections(session_id="s1")

    assert len(result) == 1
    assert result[0]["session_id"] == "s1"


@pytest.mark.asyncio
async def test_correction_count_by_intent_returns_dict(tmp_path):
    db_path = await _make_learning_db(tmp_path)
    store = CorrectionStore(db_path=db_path)

    await store.log_correction("s1", "t1", "wrong", "answer", "wrong", "GENERAL")
    await store.log_correction("s1", "t2", "wrong", "answer", "wrong", "GENERAL")
    await store.log_correction("s1", "t3", "wrong", "answer", "wrong", "SEARCH")

    result = await store.correction_count_by_intent()

    assert result == {"GENERAL": 2, "SEARCH": 1}


@pytest.mark.asyncio
async def test_get_turn_window_returns_3_before_3_after(tmp_path):
    db_path = await _make_learning_db(tmp_path)
    store = CorrectionStore(db_path=db_path)

    for idx in range(1, 8):
        await store.log_turn(
            session_id="s1",
            turn_id=f"t{idx}",
            transcript=f"user-{idx}",
            response=f"assistant-{idx}",
            intent="GENERAL_CHAT",
            route_target="RouteTarget.REALTIME_CHAT",
        )

    result = await store.get_turn_window("s1", "t4")

    assert [row["turn_id"] for row in result] == [
        "t1",
        "t2",
        "t3",
        "t4",
        "t5",
        "t6",
        "t7",
    ]


@pytest.mark.asyncio
async def test_ebbinghaus_weight_decays_with_turns(tmp_path):
    db_path = await _make_learning_db(tmp_path)
    reflection = OnlineReflection(
        db_path=db_path, decay_factor=0.3, failure_threshold=1.5
    )

    reflection.record_turn("s1", "t1", "FAST", True, 0)
    reflection.record_turn("s1", "t2", "SLOW", True, 10)
    await asyncio.sleep(0.1)

    assert pytest.approx(reflection._failure_scores["FAST"], rel=1e-3) == 0.34
    assert pytest.approx(reflection._failure_scores["SLOW"], rel=1e-3) == 0.34


@pytest.mark.asyncio
async def test_failure_score_exceeds_threshold_after_3_corrections(tmp_path):
    db_path = await _make_learning_db(tmp_path)
    reflection = OnlineReflection(
        db_path=db_path, decay_factor=0.3, failure_threshold=1.0
    )

    reflection.record_turn("s1", "t1", "GENERAL_CHAT", True, 0)
    reflection.record_turn("s1", "t2", "GENERAL_CHAT", True, 0)
    reflection.record_turn("s1", "t3", "GENERAL_CHAT", True, 0)
    await asyncio.sleep(0.1)

    assert reflection.get_intent_penalty("GENERAL_CHAT") is True


def test_verbosity_mode_defaults_to_normal(tmp_path):
    reflection = OnlineReflection(db_path=str(tmp_path / "learning.sqlite"))
    assert reflection.get_verbosity_mode("s1") == "NORMAL"


def test_verbosity_compact_set_on_signal(tmp_path):
    reflection = OnlineReflection(db_path=str(tmp_path / "learning.sqlite"))
    reflection.update_verbosity("s1", "give me a shorter answer")
    assert reflection.get_verbosity_mode("s1") == "COMPACT"


def test_verbosity_modes_are_session_scoped(tmp_path):
    reflection = OnlineReflection(db_path=str(tmp_path / "learning.sqlite"))
    reflection.update_verbosity("s1", "give me a shorter answer")
    assert reflection.get_verbosity_mode("s1") == "COMPACT"
    assert reflection.get_verbosity_mode("s2") == "NORMAL"


def test_verbosity_verbose_set_on_signal(tmp_path):
    reflection = OnlineReflection(db_path=str(tmp_path / "learning.sqlite"))
    reflection.update_verbosity("s1", "please explain more")
    assert reflection.get_verbosity_mode("s1") == "VERBOSE"


def test_intent_penalty_false_below_threshold(tmp_path):
    reflection = OnlineReflection(
        db_path=str(tmp_path / "learning.sqlite"),
        decay_factor=0.3,
        failure_threshold=1.5,
    )
    reflection.record_turn("s1", "t1", "GENERAL_CHAT", True, 10)
    assert reflection.get_intent_penalty("GENERAL_CHAT") is False


def test_intent_penalty_true_above_threshold(tmp_path):
    reflection = OnlineReflection(
        db_path=str(tmp_path / "learning.sqlite"),
        decay_factor=0.3,
        failure_threshold=1.0,
    )
    reflection.record_turn("s1", "t1", "GENERAL_CHAT", True, 0)
    reflection.record_turn("s1", "t2", "GENERAL_CHAT", True, 0)
    reflection.record_turn("s1", "t3", "GENERAL_CHAT", True, 0)
    assert reflection.get_intent_penalty("GENERAL_CHAT") is True


@pytest.mark.asyncio
async def test_create_patch_returns_positive_id(tmp_path):
    db_path = await _make_learning_db(tmp_path)
    store = PatchStore(db_path=db_path)

    patch_id = await store.create_patch(
        scope="prompt",
        target="GENERAL_CHAT",
        before={"description": "before"},
        after={"description": "after"},
        description="root cause",
    )

    assert patch_id > 0


@pytest.mark.asyncio
async def test_activate_patch_changes_status_to_active(tmp_path):
    db_path = await _make_learning_db(tmp_path)
    store = PatchStore(db_path=db_path)
    patch_id = await store.create_patch(
        scope="prompt",
        target="GENERAL_CHAT",
        before={"description": "before"},
        after={"description": "after"},
        description="root cause",
    )

    changed = await store.activate_patch(patch_id)
    active = await store.get_active_patches()

    assert changed is True
    assert len(active) == 1
    assert active[0]["status"] == "active"


@pytest.mark.asyncio
async def test_rollback_patch_changes_status_to_rolled_back(tmp_path):
    db_path = await _make_learning_db(tmp_path)
    store = PatchStore(db_path=db_path)
    patch_id = await store.create_patch(
        scope="prompt",
        target="GENERAL_CHAT",
        before={"description": "before"},
        after={"description": "after"},
        description="root cause",
    )
    await store.activate_patch(patch_id)

    changed = await store.rollback_patch(patch_id)
    history = await store.get_patch_history()

    assert changed is True
    assert history[0]["status"] == "rolled_back"


@pytest.mark.asyncio
async def test_get_active_patches_returns_only_active(tmp_path):
    db_path = await _make_learning_db(tmp_path)
    store = PatchStore(db_path=db_path)
    active_id = await store.create_patch(
        scope="prompt",
        target="GENERAL_CHAT",
        before={"description": "before"},
        after={"description": "after"},
        description="root cause",
    )
    rolled_back_id = await store.create_patch(
        scope="routing",
        target="READ_TEXT",
        before={"description": "before"},
        after={"description": "after"},
        description="root cause",
    )
    await store.activate_patch(active_id)
    await store.activate_patch(rolled_back_id)
    await store.rollback_patch(rolled_back_id)

    active = await store.get_active_patches()

    assert [row["id"] for row in active] == [active_id]


@pytest.mark.asyncio
async def test_get_patch_history_returns_all(tmp_path):
    db_path = await _make_learning_db(tmp_path)
    store = PatchStore(db_path=db_path)
    await store.create_patch(
        scope="prompt",
        target="GENERAL_CHAT",
        before={"description": "before"},
        after={"description": "after"},
        description="root cause",
    )
    await store.create_patch(
        scope="threshold",
        target="READ_TEXT",
        before={"description": "before"},
        after={"description": "after"},
        description="root cause",
    )

    history = await store.get_patch_history()

    assert len(history) == 2


@pytest.mark.asyncio
async def test_stable_patch_when_fewer_corrections_after(tmp_path):
    mock_patch_store = AsyncMock()
    rollback = Rollback(
        db_path=str(tmp_path / "learning.sqlite"),
        patch_store=mock_patch_store,
        correction_store=AsyncMock(),
    )

    verdict = await rollback.evaluate_patch(
        1, corrections_before=4, corrections_after=1
    )

    assert verdict == "stable"
    mock_patch_store.rollback_patch.assert_not_awaited()


@pytest.mark.asyncio
async def test_monitoring_when_decay_is_between_0_5_and_1(tmp_path):
    mock_patch_store = AsyncMock()
    rollback = Rollback(
        db_path=str(tmp_path / "learning.sqlite"),
        patch_store=mock_patch_store,
        correction_store=AsyncMock(),
    )

    verdict = await rollback.evaluate_patch(
        1, corrections_before=4, corrections_after=3
    )

    assert verdict == "monitoring"
    mock_patch_store.rollback_patch.assert_not_awaited()


@pytest.mark.asyncio
async def test_rollback_triggered_when_decay_score_gte_1(tmp_path):
    mock_patch_store = AsyncMock()
    rollback = Rollback(
        db_path=str(tmp_path / "learning.sqlite"),
        patch_store=mock_patch_store,
        correction_store=AsyncMock(),
    )

    verdict = await rollback.evaluate_patch(
        1, corrections_before=2, corrections_after=3
    )

    assert verdict == "rollback"
    mock_patch_store.rollback_patch.assert_awaited_once_with(1)


@pytest.mark.asyncio
async def test_run_replay_creates_patch_on_correction(tmp_path):
    mock_correction_store = AsyncMock()
    mock_correction_store.get_corrections = AsyncMock(
        return_value=[
            {
                "turn_id": "t1",
                "correction_signal": "that's wrong",
                "intent_at_time": "GENERAL_CHAT",
            }
        ]
    )
    mock_correction_store.get_turn_window = AsyncMock(
        return_value=[
            {"user_transcript": f"u{idx}", "assistant_response": f"a{idx}"}
            for idx in range(6)
        ]
    )
    mock_patch_store = AsyncMock()
    mock_memory_store = AsyncMock()

    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = {
        "choices": [
            {
                "message": {
                    "content": json.dumps(
                        {
                            "root_cause": "prompt was vague",
                            "suggested_scope": "prompt",
                            "suggested_change": "be more specific",
                        }
                    )
                }
            }
        ]
    }
    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=mock_response)

    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        replay = OfflineReplay(
            db_path=str(tmp_path / "learning.sqlite"),
            correction_store=mock_correction_store,
            patch_store=mock_patch_store,
            priority_min_recalls=3,
            turbo_model="qwen-turbo",
            api_key="test",
            base_url="https://example.com/compatible-mode/v1",
            memory_store=mock_memory_store,
        )
        await replay.run_replay("s1")

    mock_patch_store.create_patch.assert_awaited_once()


@pytest.mark.asyncio
async def test_run_replay_skips_patch_on_malformed_json(tmp_path):
    mock_correction_store = AsyncMock()
    mock_correction_store.get_corrections = AsyncMock(
        return_value=[
            {
                "turn_id": "t1",
                "correction_signal": "that's wrong",
                "intent_at_time": "GENERAL_CHAT",
            }
        ]
    )
    mock_correction_store.get_turn_window = AsyncMock(
        return_value=[
            {"user_transcript": f"u{idx}", "assistant_response": f"a{idx}"}
            for idx in range(6)
        ]
    )
    mock_patch_store = AsyncMock()

    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = {
        "choices": [{"message": {"content": "not json"}}]
    }
    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=mock_response)

    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        replay = OfflineReplay(
            db_path=str(tmp_path / "learning.sqlite"),
            correction_store=mock_correction_store,
            patch_store=mock_patch_store,
            priority_min_recalls=3,
            turbo_model="qwen-turbo",
            api_key="test",
            base_url="https://example.com/compatible-mode/v1",
            memory_store=AsyncMock(),
        )
        await replay.run_replay("s1")

    mock_patch_store.create_patch.assert_not_awaited()


@pytest.mark.asyncio
async def test_promote_priority_memories_tags_frequent_topics(tmp_path):
    db_path = await _make_learning_db(tmp_path)
    async with aiosqlite.connect(db_path) as db:
        for idx in range(3):
            await db.execute(
                """
                INSERT INTO transcript_log (
                    session_id,
                    turn_id,
                    user_transcript,
                    assistant_response,
                    intent_at_time,
                    route_target,
                    created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "s1",
                    f"t{idx}",
                    "what is my name?",
                    "Your name is Om. I remember it clearly.",
                    "MEMORY_RECALL",
                    "RouteTarget.MEMORY_READ",
                    f"2026-01-01T00:00:0{idx}",
                ),
            )
        await db.commit()

    mock_memory_store = AsyncMock()
    mock_memory_store.mark_priority_facts = AsyncMock(return_value=1)
    replay = OfflineReplay(
        db_path=db_path,
        correction_store=AsyncMock(),
        patch_store=AsyncMock(),
        priority_min_recalls=3,
        turbo_model="qwen-turbo",
        api_key="test",
        base_url="https://example.com/compatible-mode/v1",
        memory_store=mock_memory_store,
    )

    await replay.promote_priority_memories("s1")

    mock_memory_store.mark_priority_facts.assert_awaited_once_with(
        user_id="default",
        facts=["Your name is Om."],
    )


def test_compact_verbosity_appends_short_instruction():
    result = build_system_prompt("Base.", verbosity_mode="COMPACT")
    assert result.endswith("Keep your answer under 2 sentences.")


def test_verbose_verbosity_appends_detailed_instruction():
    result = build_system_prompt("Base.", verbosity_mode="VERBOSE")
    assert result.endswith("Give a thorough, detailed explanation.")


def test_normal_verbosity_no_change():
    result = build_system_prompt("Base.", verbosity_mode="NORMAL")
    assert result == "Base."


def test_intent_penalty_prepends_warning():
    result = build_system_prompt("Base.", intent_penalty=True)
    assert result.startswith("Let me be careful here…")


def test_no_penalty_no_prepend():
    result = build_system_prompt("Base.", intent_penalty=False)
    assert not result.startswith("Let me be careful here…")
