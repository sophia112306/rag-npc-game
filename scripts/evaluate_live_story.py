#!/usr/bin/env python3
"""Exercise live NPC generation inside every authored ending route."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
from typing import Any
from uuid import uuid4

import httpx
from fastapi.testclient import TestClient

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from backend.generation.http_gateway import HttpModelGateway  # noqa: E402
from backend.generation.planner import GatewayStoryPlanner  # noqa: E402
from backend.main import create_app  # noqa: E402


OPENING_CHOICES = (
    "meet_andre",
    "walk_to_council",
    "meet_vidalia",
    "ask_for_task",
)


ENDING_ROUTES: dict[str, tuple[str, ...]] = {
    "long_sleep": (
        "ask_location",
        "travel_to_minglin_life_spring",
        "study_spring_ash",
        "enter_lieyi_plains",
        "observe_sacred_fire",
        "return_with_fire_findings",
        "travel_to_minglin_rune_grove",
        "trace_dust_runes",
        "enter_liuchen_valley",
        "listen_to_forgotten_names",
        "return_with_dust_findings",
        "preview_border_ruins",
        "border_help_both",
        "return_after_border_choice",
        "enter_memory_library_with_map",
        "inspect_life_death_book",
        "inspect_invasion_archive",
        "contact_alan_observer",
        "seek_menmesvento_after_truths",
        "accept_dust_return_token",
        "return_to_minglin_for_veta",
        "enter_veta_source",
        "veta_q1_recurring_life",
        "veta_q2_release",
        "choose_long_sleep",
    ),
    "wake": (
        "travel_to_minglin_rune_grove",
        "read_ember_runes",
        "enter_lieyi_plains",
        "question_fire_elder_motive",
        "return_with_fire_findings",
        "travel_to_minglin_life_spring",
        "study_spring_echo",
        "enter_liuchen_valley",
        "study_burial_cycle",
        "return_with_dust_findings",
        "preview_border_ruins",
        "border_report",
        "return_after_border_choice",
        "enter_memory_library_with_elders",
        "inspect_invasion_archive",
        "inspect_life_death_book",
        "contact_alan_observer",
        "seek_menmesvento_after_truths",
        "decline_dust_return_token",
        "return_to_minglin_for_veta",
        "enter_veta_source",
        "veta_q1_each_life",
        "veta_q2_remember",
        "choose_wake",
    ),
    "new_dream": (
        "ask_location",
        "travel_to_minglin_life_spring",
        "study_spring_echo",
        "enter_liuchen_valley",
        "listen_to_forgotten_names",
        "return_with_dust_findings",
        "travel_to_minglin_rune_grove",
        "read_ember_runes",
        "enter_lieyi_plains",
        "observe_sacred_fire",
        "return_with_fire_findings",
        "preview_border_ruins",
        "border_ignore",
        "return_after_border_choice",
        "enter_memory_library_alone",
        "inspect_life_death_book",
        "inspect_invasion_archive",
        "contact_alan_observer",
        "seek_menmesvento_after_truths",
        "accept_dust_return_token",
        "return_to_minglin_for_veta",
        "enter_veta_source",
        "veta_q1_each_life",
        "veta_q2_release",
        "choose_new_dream",
    ),
    "dust_return": (
        "travel_to_minglin_rune_grove",
        "trace_dust_runes",
        "enter_liuchen_valley",
        "listen_to_forgotten_names",
        "return_with_dust_findings",
        "travel_to_minglin_life_spring",
        "study_spring_ash",
        "enter_lieyi_plains",
        "observe_sacred_fire",
        "return_with_fire_findings",
        "preview_border_ruins",
        "border_help_both",
        "return_after_border_choice",
        "enter_memory_library_with_map",
        "inspect_invasion_archive",
        "inspect_life_death_book",
        "contact_alan_observer",
        "seek_menmesvento_after_truths",
        "accept_dust_return_token",
        "return_to_minglin_for_veta",
        "enter_veta_source",
        "veta_q1_recurring_life",
        "veta_q2_release",
        "choose_dust_return",
    ),
    "usurp": (
        "travel_to_minglin_rune_grove",
        "trace_dust_runes",
        "enter_liuchen_valley",
        "listen_to_forgotten_names",
        "return_with_dust_findings",
        "travel_to_minglin_life_spring",
        "study_spring_ash",
        "enter_lieyi_plains",
        "observe_sacred_fire",
        "return_with_fire_findings",
        "preview_border_ruins",
        "border_ignore",
        "return_after_border_choice",
        "enter_memory_library_alone",
        "inspect_invasion_archive",
        "inspect_life_death_book",
        "contact_alan_observer",
        "seek_menmesvento_after_truths",
        "decline_dust_return_token",
        "return_to_minglin_for_veta",
        "enter_veta_source",
        "veta_q1_recurring_life",
        "veta_q2_control",
        "confirm_usurp_after_warning",
        "choose_usurp",
    ),
}

EXPECTED_ENDINGS = {
    "long_sleep": "長眠",
    "wake": "醒來",
    "new_dream": "新夢",
    "dust_return": "塵歸",
    "usurp": "篡夢",
}

LIVE_NPC_PROMPTS = {
    "vidalia": "當兩份證詞互相矛盾時，你會如何處理？",
    "andre": "平衡議會作決策時最重要的是什麼？",
    "dasso": "你如何理解長老的責任？",
    "menmesvento": "名字被遺忘時，你覺得失去的是什麼？",
    "seth": "你如何看待陌生旅人提出的合作？",
    "syra": "記錄一段見聞時，你最先分辨什麼？",
}

# Andre's first interaction is an authored opening event.  It is still
# exercised through the production turn API below, but deliberately does not
# call the free-dialogue model until a later relationship-gated side event.
AUTHORED_OPENING_NPCS = {"andre"}

NPC_TRIGGERS = {
    "enter_lieyi_plains": ("dasso",),
    "enter_liuchen_valley": ("menmesvento",),
    "preview_border_ruins": ("seth", "syra"),
}


def _headers(api_key: str | None) -> dict[str, str]:
    return (
        {"Authorization": f"Bearer {api_key}"}
        if api_key
        else {}
    )


def _metrics(
    gateway_url: str,
    api_key: str | None,
) -> dict[str, Any]:
    metrics_url = gateway_url.rsplit("/", 1)[0] + "/metrics"
    response = httpx.get(
        metrics_url,
        headers=_headers(api_key),
        timeout=10,
    )
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, dict):
        raise RuntimeError("Gateway metrics response must be an object")
    return payload


def _count_delta(
    before: dict[str, Any],
    after: dict[str, Any],
    field: str,
) -> dict[str, int]:
    before_counts = before.get(field, {})
    after_counts = after.get(field, {})
    if not isinstance(before_counts, dict) or not isinstance(after_counts, dict):
        raise RuntimeError(f"Gateway metrics field {field} must be an object")
    keys = set(before_counts) | set(after_counts)
    return {
        str(key): int(after_counts.get(key, 0))
        - int(before_counts.get(key, 0))
        for key in sorted(keys)
        if int(after_counts.get(key, 0))
        - int(before_counts.get(key, 0))
    }


def _start(client: TestClient, session_id: str) -> dict[str, Any]:
    response = client.post(
        "/api/game/start",
        json={"session_id": session_id},
    )
    if response.status_code != 201:
        raise RuntimeError(
            f"Could not start {session_id}: {response.status_code} {response.text}"
        )
    payload = response.json()
    if not isinstance(payload, dict):
        raise RuntimeError("Game start response must be an object")
    return payload


def _submit_choice(
    client: TestClient,
    session_id: str,
    state: dict[str, Any],
    choice_id: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    choices = client.get(f"/api/game/{session_id}/choices")
    choices.raise_for_status()
    choice = next(
        (
            row
            for row in choices.json()
            if row["choice_id"] == choice_id
        ),
        None,
    )
    if choice is None:
        raise RuntimeError(
            f"{session_id}: choice {choice_id} is unavailable at "
            f"{state['story_progress']['node_id']} / {state['current_scene_id']}"
        )
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
            "expected_state_version": state["state_version"],
        },
    )
    if response.status_code != 200:
        raise RuntimeError(
            f"{session_id}: choice {choice_id} failed: "
            f"{response.status_code} {response.text}"
        )
    payload = response.json()
    return payload["state"], payload


def _talk_to_npc(
    client: TestClient,
    session_id: str,
    state: dict[str, Any],
    npc_id: str,
    *,
    expected_story_node: str | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    protected_state = {
        "current_scene_id": state["current_scene_id"],
        "player": state["player"],
        "final_ending": state["final_ending"],
        "game_status": state["game_status"],
    }
    if expected_story_node is None:
        protected_state["story_progress"] = state["story_progress"]
    response = client.post(
        "/api/game/turn",
        json={
            "session_id": session_id,
            "action_id": str(uuid4()),
            "message": LIVE_NPC_PROMPTS[npc_id],
            "input_type": "text",
            "target_npc_id": npc_id,
            "action_mode": "dialogue",
            "expected_state_version": state["state_version"],
        },
    )
    if response.status_code != 200:
        raise RuntimeError(
            f"{session_id}: live dialogue with {npc_id} failed: "
            f"{response.status_code} {response.text}"
        )
    payload = response.json()
    updated = payload["state"]
    if (
        expected_story_node is not None
        and updated["story_progress"]["node_id"] != expected_story_node
    ):
        raise RuntimeError(
            f"{session_id}: {npc_id} dialogue should advance to "
            f"{expected_story_node}, got "
            f"{updated['story_progress']['node_id']}"
        )
    for field, expected in protected_state.items():
        if updated[field] != expected:
            raise RuntimeError(
                f"{session_id}: {npc_id} dialogue changed authoritative "
                f"state field {field}"
            )
    dialogue = payload["story"]["dialogue"]
    if not dialogue or dialogue[0]["speaker_id"] != npc_id:
        raise RuntimeError(
            f"{session_id}: live dialogue speaker was not {npc_id}: "
            + json.dumps(dialogue, ensure_ascii=False)
        )
    return updated, payload


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--gateway-url",
        default="http://127.0.0.1:8000/generate",
    )
    parser.add_argument("--api-key")
    args = parser.parse_args()

    before_metrics = _metrics(args.gateway_url, args.api_key)
    gateway = HttpModelGateway(
        args.gateway_url,
        api_key=args.api_key,
    )
    live_dialogues: list[dict[str, str]] = []
    ending_results: dict[str, str] = {}
    tested_npcs: set[str] = set()

    with TemporaryDirectory(prefix="rag-npc-live-story-") as temp_dir:
        database_url = (
            "sqlite+aiosqlite:///"
            + str(Path(temp_dir) / "live-story.db")
        )
        app = create_app(
            database_url,
            story_planner_factory=lambda context: GatewayStoryPlanner(
                gateway,
                context,
                timeout_seconds=30,
                max_attempts=1,
            ),
        )
        with TestClient(app) as client:
            for route_name, choice_ids in ENDING_ROUTES.items():
                session_id = f"live-story-{route_name}"
                state = _start(client, session_id)

                # Every ending starts after the player-visible authored
                # opening.  Keep this explicit so the evaluator cannot skip
                # the same gates enforced by the production turn API.
                opening_choices = OPENING_CHOICES
                if route_name == "long_sleep":
                    state, turn = _talk_to_npc(
                        client,
                        session_id,
                        state,
                        "andre",
                        expected_story_node="minglin_path_open",
                    )
                    tested_npcs.add("andre")
                    live_dialogues.append(
                        {
                            "npc_id": "andre",
                            "text": turn["story"]["dialogue"][0]["text"],
                        }
                    )
                    opening_choices = OPENING_CHOICES[1:]

                for choice_id in opening_choices:
                    state, _ = _submit_choice(
                        client,
                        session_id,
                        state,
                        choice_id,
                    )
                if route_name == "long_sleep":
                    state, turn = _talk_to_npc(
                        client,
                        session_id,
                        state,
                        "vidalia",
                    )
                    tested_npcs.add("vidalia")
                    live_dialogues.append(
                        {
                            "npc_id": "vidalia",
                            "text": turn["story"]["dialogue"][0]["text"],
                        }
                    )

                for choice_id in choice_ids:
                    state, turn = _submit_choice(
                        client,
                        session_id,
                        state,
                        choice_id,
                    )
                    if choice_id == "contact_alan_observer":
                        if turn["story"]["dialogue"][0]["speaker_id"] != "alan":
                            raise RuntimeError(
                                f"{session_id}: Alan story turn lost its speaker"
                            )
                    if (
                        choice_id.startswith("veta_q")
                        or choice_id == "confirm_usurp_after_warning"
                    ):
                        if turn["story"]["dialogue"][0]["speaker_id"] != "veta":
                            raise RuntimeError(
                                f"{session_id}: Veta story turn lost its speaker"
                            )

                    if route_name == "long_sleep":
                        for npc_id in NPC_TRIGGERS.get(choice_id, ()):
                            if npc_id in tested_npcs:
                                continue
                            state, live_turn = _talk_to_npc(
                                client,
                                session_id,
                                state,
                                npc_id,
                            )
                            tested_npcs.add(npc_id)
                            live_dialogues.append(
                                {
                                    "npc_id": npc_id,
                                    "text": live_turn["story"][
                                        "dialogue"
                                    ][0]["text"],
                                }
                            )

                expected_ending = EXPECTED_ENDINGS[route_name]
                if state["game_status"] != "completed":
                    raise RuntimeError(
                        f"{session_id}: route did not reach a terminal state"
                    )
                if state["final_ending"] != expected_ending:
                    raise RuntimeError(
                        f"{session_id}: expected {expected_ending}, got "
                        f"{state['final_ending']}"
                    )
                ending_results[route_name] = state["final_ending"]

    after_metrics = _metrics(args.gateway_url, args.api_key)
    source_delta = _count_delta(
        before_metrics,
        after_metrics,
        "source_counts",
    )
    route_delta = _count_delta(
        before_metrics,
        after_metrics,
        "route_counts",
    )
    npc_delta = _count_delta(
        before_metrics,
        after_metrics,
        "npc_counts",
    )
    if tested_npcs != set(LIVE_NPC_PROMPTS):
        raise RuntimeError(
            "Not every physical map NPC received a live model turn: "
            + ", ".join(sorted(set(LIVE_NPC_PROMPTS) - tested_npcs))
        )
    allowed_sources = {"model", "model_refined", "post_generation_guard"}
    expected_model_turns = len(LIVE_NPC_PROMPTS) - len(AUTHORED_OPENING_NPCS)
    if (
        not set(source_delta).issubset(allowed_sources)
        or sum(source_delta.values()) != expected_model_turns
    ):
        raise RuntimeError(
            "Expected every non-authored live turn to reach a model and use at most "
            f"post-generation safety, got {source_delta}"
        )
    if route_delta != {
        "dedicated_adapter": expected_model_turns
    }:
        raise RuntimeError(
            f"Expected only dedicated adapters, got {route_delta}"
        )

    print(
        json.dumps(
            {
                "status": "pass",
                "endings": ending_results,
                "live_npc_dialogues": live_dialogues,
                "gateway_source_delta": source_delta,
                "gateway_route_delta": route_delta,
                "gateway_npc_delta": npc_delta,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
