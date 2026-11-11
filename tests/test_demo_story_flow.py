"""End-to-end fallback story choices, validation, and persistence."""

from uuid import uuid4

from fastapi.testclient import TestClient

from backend.content.reveal_policy import LEGACY_PUBLIC_CLUE_ALIASES, normalize_legacy_demo_state
from backend.database.models import ActionRecord
from backend.database.repository import SqlAlchemyGameRepository
from backend.generation.scene_image_jobs import SceneImageCoordinator
from backend.main import create_app
from backend.schemas.game_state import GameState
from backend.schemas.player_view import project_player_view


def _start(client: TestClient, session_id: str) -> dict:
    response = client.post("/api/game/start", json={"session_id": session_id})
    assert response.status_code == 201
    return response.json()


def _choice(client: TestClient, session_id: str, choice_id: str) -> dict:
    response = client.get(f"/api/game/{session_id}/choices")
    assert response.status_code == 200
    return next(
        choice for choice in response.json() if choice["choice_id"] == choice_id
    )


def _submit_choice(
    client: TestClient,
    session_id: str,
    state_version: int,
    choice_id: str,
) -> dict:
    choice = _choice(client, session_id, choice_id)
    response = client.post(
        "/api/game/turn",
        json={
            "session_id": session_id,
            "action_id": str(uuid4()),
            "message": choice["message"],
            "input_type": "text",
            "target_npc_id": choice["target_npc_id"],
            "action_mode": choice["action_mode"],
            "destination_scene_id": choice["destination_scene_id"],
            "story_choice_id": choice["choice_id"],
            "expected_state_version": state_version,
        },
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_fire_branch_reaches_lieyi_and_resumes_after_restart(tmp_path) -> None:
    database_url = f"sqlite+aiosqlite:///{tmp_path / 'fire-demo.db'}"
    session_id = "fire-demo"

    with TestClient(create_app(database_url)) as client:
        state = _start(client, session_id)
        spring = _submit_choice(
            client,
            session_id,
            state["state_version"],
            "travel_to_minglin_life_spring",
        )
        assert spring["state"]["current_scene_id"] == "minglin_life_spring"
        assert spring["state"]["story_progress"]["node_id"] == "life_spring_arrival"

        ember = _submit_choice(
            client,
            session_id,
            spring["state"]["state_version"],
            "study_spring_ash",
        )
        assert ember["state"]["story_progress"]["node_id"] == "ember_route_ready"
        assert "ember_current" in ember["state"]["story_progress"]["public_clue_ids"]

        lieyi = _submit_choice(
            client,
            session_id,
            ember["state"]["state_version"],
            "enter_lieyi_plains",
        )
        assert lieyi["state"]["current_scene_id"] == "lieyi_plains"
        assert lieyi["state"]["story_progress"]["node_id"] == "lieyi_arrival"

        finding = _submit_choice(
            client,
            session_id,
            lieyi["state"]["state_version"],
            "observe_sacred_fire",
        )
        assert finding["state"]["story_progress"]["node_id"] == "demo_fire_complete"
        assert "sacred_fire_cycle" in finding["state"]["story_progress"]["public_clue_ids"]

        completed = _submit_choice(
            client,
            session_id,
            finding["state"]["state_version"],
            "return_with_fire_findings",
        )
        assert completed["state"]["current_scene_id"] == "minglin"
        assert completed["state"]["story_progress"]["node_id"] == "demo_complete"

    with TestClient(create_app(database_url)) as restarted:
        resumed = _start(restarted, session_id)
        choices = restarted.get(f"/api/game/{session_id}/choices").json()

        assert resumed["current_scene_id"] == "minglin"
        assert resumed["story_progress"] == completed["state"]["story_progress"]
        assert [choice["choice_id"] for choice in choices] == [
            "review_demo_findings"
        ]


def test_dust_branch_reaches_liuchen_with_different_clues(tmp_path) -> None:
    with TestClient(
        create_app(f"sqlite+aiosqlite:///{tmp_path / 'dust-demo.db'}")
    ) as client:
        session_id = "dust-demo"
        state = _start(client, session_id)
        grove = _submit_choice(
            client,
            session_id,
            state["state_version"],
            "travel_to_minglin_rune_grove",
        )
        route = _submit_choice(
            client,
            session_id,
            grove["state"]["state_version"],
            "trace_dust_runes",
        )
        entry_choice = _choice(client, session_id, "enter_liuchen_valley")
        assert "裂隙地圖" not in entry_choice["label"] + entry_choice["message"]
        assert "風沙" in entry_choice["label"] + entry_choice["message"]
        valley = _submit_choice(
            client,
            session_id,
            route["state"]["state_version"],
            "enter_liuchen_valley",
        )
        finding = _submit_choice(
            client,
            session_id,
            valley["state"]["state_version"],
            "listen_to_forgotten_names",
        )

        assert valley["state"]["current_scene_id"] == "liuchen_valley"
        assert "dust_route_trace" in valley["state"]["story_progress"]["public_clue_ids"]
        assert "fissure_map" not in valley["state"]["story_progress"]["public_clue_ids"]
        assert "地圖" not in " ".join(line["text"] for line in valley["story"]["dialogue"])
        assert finding["state"]["story_progress"]["node_id"] == "demo_dust_complete"
        assert "mummies_seek_remembrance" in finding["state"]["story_progress"]["public_clue_ids"]
        assert "sacred_fire_cycle" not in finding["state"]["story_progress"]["public_clue_ids"]

        valley["story"]["dialogue"][0]["text"] = (
            "符石路徑在腳下崩解，你借助地圖標出的地理優勢甩開封閉路線，進入流塵谷。"
        )
        action_id = uuid4()
        old_record = ActionRecord(
            session_id=session_id,
            action_id=str(action_id),
            request_digest="same-request",
            request_json={"story_choice_id": "enter_liuchen_valley"},
            status="completed",
            response_json=valley,
        )
        replayed = SqlAlchemyGameRepository._validated_cached_response(
            old_record, action_id, "same-request"
        )
        assert replayed is not None
        assert "地圖" not in replayed.story.dialogue[0].text
        assert "風沙方向" in replayed.story.dialogue[0].text


def test_stale_or_altered_story_choice_is_rejected_without_turn(tmp_path) -> None:
    with TestClient(
        create_app(f"sqlite+aiosqlite:///{tmp_path / 'invalid-choice.db'}")
    ) as client:
        session_id = "invalid-choice"
        state = _start(client, session_id)
        stale = client.post(
            "/api/game/turn",
            json={
                "session_id": session_id,
                "action_id": str(uuid4()),
                "message": "我直接進入烈燚原。",
                "input_type": "text",
                "target_npc_id": None,
                "action_mode": "movement",
                "destination_scene_id": "lieyi_plains",
                "story_choice_id": "enter_lieyi_plains",
                "expected_state_version": state["state_version"],
            },
        )
        valid_choice = _choice(client, session_id, "ask_for_task")
        altered = client.post(
            "/api/game/turn",
            json={
                "session_id": session_id,
                "action_id": str(uuid4()),
                "message": "我竄改了選項內容。",
                "input_type": "text",
                "target_npc_id": valid_choice["target_npc_id"],
                "action_mode": valid_choice["action_mode"],
                "destination_scene_id": valid_choice["destination_scene_id"],
                "story_choice_id": valid_choice["choice_id"],
                "expected_state_version": state["state_version"],
            },
        )
        unchanged = client.get(f"/api/game/{session_id}/state")

        assert stale.status_code == 409
        assert stale.json()["detail"]["code"] == "STORY_CHOICE_UNAVAILABLE"
        assert altered.status_code == 409
        assert altered.json()["detail"]["code"] == "STORY_CHOICE_MISMATCH"
        assert unchanged.json()["turn_count"] == 0
        assert unchanged.json()["state_version"] == 1


def test_first_stage_dialogue_does_not_reveal_later_truths(tmp_path) -> None:
    with TestClient(
        create_app(f"sqlite+aiosqlite:///{tmp_path / 'reveal-timing.db'}")
    ) as client:
        session_id = "reveal-timing"
        state = _start(client, session_id)
        for choice_id in (
            "ask_location",
            "ask_about_factions",
            "ask_about_fire_elder",
            "ask_about_mummies",
        ):
            turn = _submit_choice(
                client,
                session_id,
                state["state_version"],
                choice_id,
            )
            state = turn["state"]
            visible = " ".join(
                [
                    *(line["text"] for line in turn["story"]["dialogue"]),
                    *state["story_progress"]["public_clue_ids"],
                ]
            )
            for later_truth in (
                "第一次入侵",
                "維塔意識",
                "返回外界",
                "生死簿",
                "奪取維塔",
                "after_first_invasion",
                "factions_seek_player",
            ):
                assert later_truth not in visible

        assert state["story_progress"]["public_clue_ids"] == [
            "spring_stopped_expanding",
            "factions_notice_anomaly",
            "elders_near_spring",
            "mummies_value_names",
        ]


def test_legacy_clue_ids_are_not_exposed_to_player_or_image_provider() -> None:
    state = GameState(session_id="legacy-reveal", current_scene_id="minglin")
    state.story_progress.public_clue_ids = list(LEGACY_PUBLIC_CLUE_ALIASES)
    state.story_progress.chapter_title = "Demo 完成：長老的企圖"

    progress = project_player_view(state).story_progress
    prompt = SceneImageCoordinator._build_prompt(state)

    assert progress.public_clue_ids == list(LEGACY_PUBLIC_CLUE_ALIASES.values())
    assert progress.chapter_title == "Demo 完成：長老的行蹤"
    assert "長老的企圖" not in prompt
    for old_id in LEGACY_PUBLIC_CLUE_ALIASES:
        assert old_id not in progress.public_clue_ids
        assert old_id not in prompt


def test_old_demo_route_does_not_grant_the_later_fissure_map() -> None:
    state = GameState(session_id="old-demo-map", current_scene_id="minglin_rune_grove")
    state.story_progress.completed_choice_ids = ["trace_dust_runes"]
    state.story_progress.public_clue_ids = ["fissure_map"]
    state.flags["fissure_map"] = True

    visible = project_player_view(state)
    assert visible.story_progress.public_clue_ids == ["dust_route_trace"]
    assert "fissure_map" not in SceneImageCoordinator._build_prompt(state)

    normalized = normalize_legacy_demo_state(state)
    assert normalized.flags["fissure_map"] is False
    assert normalized.story_progress.public_clue_ids == ["dust_route_trace"]


def test_replaying_saved_first_stage_turn_uses_current_reveal_timing(tmp_path) -> None:
    with TestClient(
        create_app(f"sqlite+aiosqlite:///{tmp_path / 'legacy-replay.db'}")
    ) as client:
        session_id = "legacy-replay"
        state = _start(client, session_id)
        orientation = _submit_choice(
            client, session_id, state["state_version"], "ask_location"
        )
        old_response = _submit_choice(
            client,
            session_id,
            orientation["state"]["state_version"],
            "ask_about_factions",
        )

    old_response["story"]["dialogue"][0]["text"] = (
        "人族長老害怕失去輪迴，木乃伊則害怕被世界遺忘。"
        "他們都可能注意到唯一連著維塔意識的外來者。"
    )
    old_response["state"]["story_progress"]["public_clue_ids"] = [
        "spring_stopped_after_first_invasion",
        "factions_seek_player",
    ]
    old_response["story"]["established_events"][0]["effect"]["operations"][0][
        "revealed_clue_ids"
    ] = ["factions_seek_player"]
    action_id = uuid4()
    saved = ActionRecord(
        session_id=session_id,
        action_id=str(action_id),
        request_digest="same-request",
        request_json={"story_choice_id": "ask_about_factions"},
        status="completed",
        response_json=old_response,
    )

    replayed = SqlAlchemyGameRepository._validated_cached_response(
        saved, action_id, "same-request"
    )

    assert replayed is not None
    assert "維塔意識" not in replayed.story.dialogue[0].text
    assert replayed.state.story_progress.public_clue_ids == [
        "spring_stopped_expanding",
        "factions_notice_anomaly",
    ]
    assert replayed.story.established_events[0].effect["operations"][0][
        "revealed_clue_ids"
    ] == ["factions_notice_anomaly"]
