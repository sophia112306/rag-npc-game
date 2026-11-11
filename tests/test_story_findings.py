"""Different investigations leave different readable, persistent consequences."""

from fastapi.testclient import TestClient

from backend.main import create_app
from test_demo_story_flow import _start, _submit_choice


def test_reports_reflect_each_branch_and_reach_npc_only_when_reported(tmp_path):
    database = f"sqlite+aiosqlite:///{tmp_path / 'reports.db'}"
    reports = {}
    saved = {}
    paths = {
        "fire": ("travel_to_minglin_life_spring", "study_spring_ash", "enter_lieyi_plains", "question_fire_elder_motive", "return_with_fire_findings"),
        "dust": ("travel_to_minglin_rune_grove", "trace_dust_runes", "enter_liuchen_valley", "listen_to_forgotten_names", "return_with_dust_findings"),
    }
    with TestClient(create_app(database)) as client:
        for session, choices in paths.items():
            state = _start(client, session)
            for choice in choices:
                state = _submit_choice(client, session, state["state_version"], choice)["state"]
            context = client.app.state.npc_context_repository
            before = client.portal.call(context.get_generation_context, session, "vidalia", state["turn_count"])
            assert not before.memories  # Private investigations did not teleport into her memory.
            report = _submit_choice(client, session, state["state_version"], "review_demo_findings")
            reports[session] = report["story"]["dialogue"][0]["text"]
            saved[session] = report["state"]["story_progress"]["findings"]
            after = client.portal.call(context.get_generation_context, session, "vidalia", report["turn_number"])
            assert any(saved[session][-1]["summary"] in memory.content for memory in after.memories)
            assert all(finding["kind"] == "investigation" for finding in saved[session])
        assert "灰燼" in reports["fire"] and "灰燼" not in reports["dust"]
        assert "名字" in reports["dust"] and "名字" not in reports["fire"]
        assert reports["fire"] != reports["dust"]
    with TestClient(create_app(database)) as restarted:
        for session in paths:
            assert _start(restarted, session)["story_progress"]["findings"] == saved[session]


def test_discovery_signal_requires_established_investigation_and_survives_restart(tmp_path):
    database = f"sqlite+aiosqlite:///{tmp_path / 'signal.db'}"
    with TestClient(create_app(database)) as client:
        state = _start(client, "signal")
        assert not state["story_progress"]["findings"] and state["world_scene"]["discovery"] is None
        state = _submit_choice(client, "signal", 1, "travel_to_minglin_life_spring")["state"]
        assert state["world_scene"]["discovery"] is None
        state = _submit_choice(client, "signal", state["state_version"], "study_spring_ash")["state"]
        assert state["world_scene"]["discovery"]["signal"] == "ember"
        assert state["world_scene"]["discovery"]["clue_id"] == "ember_current"
        assert len(state["story_progress"]["findings"]) == 1
    with TestClient(create_app(database)) as restarted:
        resumed = _start(restarted, "signal")
        assert resumed["world_scene"]["discovery"] == state["world_scene"]["discovery"]
        assert resumed["story_progress"]["findings"] == state["story_progress"]["findings"]
