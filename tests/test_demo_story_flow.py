"""End-to-end fallback story choices, validation, and persistence."""

from uuid import uuid4

from fastapi.testclient import TestClient

from backend.main import create_app


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
        assert "fissure_map" in valley["state"]["story_progress"]["public_clue_ids"]
        assert finding["state"]["story_progress"]["node_id"] == "demo_dust_complete"
        assert "mummies_seek_remembrance" in finding["state"]["story_progress"]["public_clue_ids"]
        assert "sacred_fire_cycle" not in finding["state"]["story_progress"]["public_clue_ids"]


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


def test_legacy_quest_choices_remain_clickable_in_resumed_story_state(tmp_path) -> None:
    """Existing sessions may have a quest and location from before Demo nodes existed."""

    with TestClient(
        create_app(f"sqlite+aiosqlite:///{tmp_path / 'legacy-choice.db'}")
    ) as client:
        session_id = "legacy-choice"
        state = _start(client, session_id)
        quest = client.post(
            "/api/game/turn",
            json={
                "session_id": session_id,
                "action_id": str(uuid4()),
                "message": "有什麼需要我幫忙的任務？",
                "input_type": "text",
                "target_npc_id": "vidalia",
                "action_mode": "dialogue",
                "destination_scene_id": None,
                "story_choice_id": None,
                "expected_state_version": state["state_version"],
            },
        ).json()

        grove = _submit_choice(
            client,
            session_id,
            quest["state"]["state_version"],
            "travel_to_minglin_rune_grove",
        )
        returned = _submit_choice(
            client,
            session_id,
            grove["state"]["state_version"],
            "travel_to_minglin",
        )

        assert grove["state"]["current_scene_id"] == "minglin_rune_grove"
        assert grove["state"]["story_progress"]["node_id"] == "minglin_arrival"
        assert returned["state"]["current_scene_id"] == "minglin"
        assert (
            returned["story"]["established_events"][0]["event_type"]
            == "scene_change_requested"
        )
