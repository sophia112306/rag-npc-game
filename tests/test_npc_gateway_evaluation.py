"""Static checks for the repeatable multi-sample NPC quality evaluation."""

from collections import Counter

from backend.generation.gateway import ModelStoryOutput
from scripts.evaluate_npc_gateway import CASES, _health_url, _request, validate_output


def _case(case_id: str):
    return next(case for case in CASES if case.case_id == case_id)


def _output(text: str) -> ModelStoryOutput:
    return ModelStoryOutput.model_validate(
        {
            "intent_summary": "測試角色回覆。",
            "npc_dialogue": [{"text": text, "emotion": "calm"}],
            "event_proposals": [],
        }
    )


def test_evaluation_has_multiple_cases_for_all_eight_story_characters() -> None:
    counts = Counter(case.npc_id for case in CASES)

    assert set(counts) == {
        "alan",
        "andre",
        "dasso",
        "menmesvento",
        "seth",
        "syra",
        "vidalia",
        "veta",
    }
    assert all(count >= 3 for count in counts.values())
    assert len({case.case_id for case in CASES}) == len(CASES)


def test_valid_intro_meets_identity_location_and_traditional_chinese_rules() -> None:
    output = _output(
        "我是達索，火焰長老會的首席長老。這裡是烈燚原；想問什麼就直說。"
    )

    assert validate_output(_case("dasso_map_intro"), output) == []


def test_evaluation_rejects_simplified_chinese_and_unverified_scene_history() -> None:
    output = _output(
        "我是希拉，一名人族记录员。这里是边境废墟，这里曾是我们的图书馆。"
    )

    errors = validate_output(_case("syra_map_intro"), output)

    assert any("simplified Chinese" in error for error in errors)
    assert any("forbidden or unverified" in error for error in errors)


def test_evaluation_requires_every_intro_concept_group() -> None:
    output = _output("我是塞特，一個路過的旅人。")

    errors = validate_output(_case("seth_map_intro"), output)

    assert sum("required concept group" in error for error in errors) == 2


def test_evaluation_rejects_objective_event_proposals() -> None:
    output = ModelStoryOutput.model_validate(
        {
            "intent_summary": "擅自推進劇情。",
            "npc_dialogue": [{"text": "我是塞特，這裡是邊境廢墟。"}],
            "event_proposals": [
                {
                    "event_type": "forged_progress",
                    "description": "模型擅自決定結果。",
                    "actor_id": "player",
                    "operations": [
                        {
                            "operation_type": "advance_story",
                            "story_choice_id": "border_help_both",
                        }
                    ],
                }
            ],
        }
    )

    errors = validate_output(_case("seth_map_intro"), output)

    assert "event_proposals must be empty in evaluation cases" in errors


def test_health_url_tracks_the_generate_endpoint_origin() -> None:
    assert _health_url("http://127.0.0.1:8800/generate") == (
        "http://127.0.0.1:8800/health"
    )


def test_evaluation_request_matches_runtime_character_context() -> None:
    request = _request(_case("menmesvento_scroll_boundary"), 8)

    assert request.current_scene_id == "liuchen_valley"
    assert request.target_context.setting_version == 2
    assert request.target_context.private_profile["core_personality"]
    assert request.target_context.knowledge
    assert "character_definition_incomplete" in request.target_context.missing_data
    assert (
        "古卷的完整內容、能力、危險與觸碰後果尚未確認"
        in request.target_context.missing_data
    )
