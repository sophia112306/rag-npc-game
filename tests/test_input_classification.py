"""Player text classification keeps structured intent and negation explicit."""

from uuid import uuid4

import pytest

from backend.orchestration.game_orchestrator import GameOrchestrator
from backend.schemas.player_action import PlayerAction


def _action(
    message: str,
    *,
    target_npc_id: str | None = None,
    action_mode: str = "dialogue",
) -> PlayerAction:
    return PlayerAction(
        session_id="classification",
        action_id=uuid4(),
        message=message,
        target_npc_id=target_npc_id,
        action_mode=action_mode,
    )


@pytest.mark.parametrize(
    ("action", "expected_type", "expected_intent"),
    (
        (
            _action("命脈之泉要怎麼調查？", target_npc_id="vidalia"),
            "dialogue",
            "dialogue",
        ),
        (_action("調查命脈之泉"), "inspect", "inspect"),
        (_action("我不是要調查命脈之泉"), "dialogue", "dialogue"),
        (_action("使用塵歸令"), "use_item", "use_item"),
        (_action("不要使用塵歸令"), "dialogue", "dialogue"),
        (_action("前往符石林", action_mode="movement"), "movement", "move"),
        (
            _action("設定測試場景", action_mode="scene_command"),
            "interaction",
            "scene_command",
        ),
    ),
)
def test_structured_and_free_text_intent_classification(
    action,
    expected_type,
    expected_intent,
) -> None:
    parsed = GameOrchestrator._parse_action(action)

    assert parsed.action_type == expected_type
    assert parsed.intent == expected_intent
