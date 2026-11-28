"""The page is found in Minglin and its text follows visible story state."""

from fastapi.testclient import TestClient

from backend.content.items import vidalia_page_text
from backend.main import create_app
from backend.schemas.game_state import GameState, StoryPhase
from backend.schemas.player_view import project_player_view
from test_demo_story_flow import _start, _submit_choice


def test_page_is_found_once_after_vidalia_briefing_and_persists(tmp_path):
    session_id = "vidalia-page"
    database_url = f"sqlite+aiosqlite:///{tmp_path / 'page.db'}"
    with TestClient(create_app(database_url)) as client:
        state = _start(client, session_id)
        assert state["player"]["inventory"] == []
        choices = client.get(f"/api/game/{session_id}/choices").json()
        assert "find_vidalia_notes" in {choice["choice_id"] for choice in choices}

        result = _submit_choice(client, session_id, state["state_version"], "find_vidalia_notes")
        state = result["state"]
        assert state["story_progress"]["node_id"] == "minglin_briefed"
        assert state["player"]["inventory"] == ["vidalia_observation_page"]
        page = state["player"]["items"][0]
        assert page["image_url"] == "/game/items/vidalia-observation-page-v1.jpg"
        assert "字跡工整而疏離" in page["description"]
        assert "find_vidalia_notes" not in {
            choice["choice_id"] for choice in client.get(f"/api/game/{session_id}/choices").json()
        }
        assert client.get(f"/api/game/{session_id}/state").json()["player"]["items"] == [page]


def test_page_tone_changes_without_changing_items_or_ending():
    state = GameState(session_id="page-tones")
    state.player.inventory.append("vidalia_observation_page")
    page = lambda: project_player_view(state).player.items[0].description

    assert "字跡工整而疏離" in page()
    state.npc_states["vidalia"].relation = 60
    state.axis = -20
    assert "捨不得" in page()
    state.axis = 20
    assert "塗改" in page()
    state.npc_states["vidalia"].relation = 59
    assert "字跡工整而疏離" in page()
    state.npc_states["vidalia"].relation = 60
    state.story_phase = StoryPhase.ACT4_ENDING
    state.final_ending = "醒來"
    assert "尚未說完的告別" in page()
    assert state.player.inventory == ["vidalia_observation_page"]
    assert state.final_ending == "醒來"
    assert vidalia_page_text(state) == page()
