"""The player can discover the blank stone in Liuchen without skipping the story."""

from fastapi.testclient import TestClient

from backend.main import create_app
from test_demo_story_flow import _start, _submit_choice


def test_remembrance_slab_is_optional_unique_and_keeps_valley_route(tmp_path):
    session_id = "remembrance-slab"
    database_url = f"sqlite+aiosqlite:///{tmp_path / 'slab.db'}"
    with TestClient(create_app(database_url)) as client:
        state = _start(client, session_id)
        for choice_id in (
            "travel_to_minglin_rune_grove",
            "trace_dust_runes",
            "enter_liuchen_valley",
        ):
            state = _submit_choice(client, session_id, state["state_version"], choice_id)["state"]
        assert "remembrance_slab" not in state["player"]["inventory"]
        assert "find_remembrance_slab" not in {
            choice["choice_id"] for choice in client.get(f"/api/game/{session_id}/choices").json()
        }

        state = _submit_choice(
            client, session_id, state["state_version"], "listen_to_forgotten_names"
        )["state"]
        assert "find_remembrance_slab" in {
            choice["choice_id"] for choice in client.get(f"/api/game/{session_id}/choices").json()
        }

        state = _submit_choice(
            client, session_id, state["state_version"], "find_remembrance_slab"
        )["state"]
        assert state["player"]["inventory"] == ["remembrance_slab"]
        assert state["player"]["items"][0]["image_url"] == "/game/items/remembrance-slab-v1.jpg"
        assert "尚未記下任何經你查證的姓名" in state["player"]["items"][0]["description"]
        choices = {choice["choice_id"] for choice in client.get(f"/api/game/{session_id}/choices").json()}
        assert "find_remembrance_slab" not in choices
        assert "return_with_dust_findings" in choices
        assert client.get(f"/api/game/{session_id}/state").json()["player"]["inventory"] == ["remembrance_slab"]
