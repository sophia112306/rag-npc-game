#!/usr/bin/env python3
"""Use the game backend from a terminal before connecting the frontend."""

from __future__ import annotations

import argparse
import sys
from uuid import uuid4

import httpx


NPC_TRAVEL_ROUTES = {
    "menmesvento": (
        "travel_to_minglin_rune_grove",
        "trace_dust_runes",
        "enter_liuchen_valley",
    ),
}


def _error_message(response: httpx.Response) -> str:
    try:
        payload = response.json()
        detail = payload.get("detail", payload)
    except (ValueError, AttributeError):
        return response.text or f"HTTP {response.status_code}"
    if isinstance(detail, dict):
        code = detail.get("code")
        message = detail.get("message")
        if code and message:
            return f"{code}: {message}"
        if code:
            return str(code)
    return str(detail)


def _print_state(state: dict[str, object]) -> None:
    scene = state.get("current_scene")
    scene_name = scene.get("display_name") if isinstance(scene, dict) else None
    print(
        f"[狀態] scene={scene_name or state.get('current_scene_id')} "
        f"turn={state.get('turn_count')} version={state.get('state_version')}"
    )


def _submit_turn(
    client: httpx.Client,
    *,
    session_id: str,
    state: dict[str, object],
    npc_id: str,
    message: str,
) -> dict[str, object]:
    response = client.post(
        "/api/game/turn",
        json={
            "session_id": session_id,
            "action_id": str(uuid4()),
            "input_type": "text",
            "message": message,
            "target_npc_id": npc_id,
            "action_mode": "dialogue",
            "expected_state_version": state["state_version"],
        },
    )
    if response.status_code != 200:
        raise RuntimeError(_error_message(response))
    payload = response.json()
    for line in payload["story"]["dialogue"]:
        emotion = f" ({line['emotion']})" if line.get("emotion") else ""
        print(f"{line['speaker_name']}{emotion}：{line['text']}")
    next_state = payload["state"]
    _print_state(next_state)
    return next_state


def _travel_to_npc(
    client: httpx.Client,
    *,
    session_id: str,
    state: dict[str, object],
    npc_id: str,
) -> dict[str, object]:
    """Follow canonical story choices needed to reach a remote trained NPC."""

    route = NPC_TRAVEL_ROUTES.get(npc_id, ())
    for choice_id in route:
        response = client.get(f"/api/game/{session_id}/choices")
        if response.status_code != 200:
            raise RuntimeError(_error_message(response))
        choice = next(
            (
                item
                for item in response.json()
                if item.get("choice_id") == choice_id
            ),
            None,
        )
        if choice is None:
            raise RuntimeError(f"找不到前往 {npc_id} 的劇情選項 {choice_id}")
        turn = client.post(
            "/api/game/turn",
            json={
                "session_id": session_id,
                "action_id": str(uuid4()),
                "input_type": "text",
                "message": choice["message"],
                "target_npc_id": choice.get("target_npc_id"),
                "action_mode": choice["action_mode"],
                "destination_scene_id": choice.get("destination_scene_id"),
                "story_choice_id": choice["story_choice_id"],
                "expected_state_version": state["state_version"],
            },
        )
        if turn.status_code != 200:
            raise RuntimeError(_error_message(turn))
        state = turn.json()["state"]
    if route:
        print(f"[移動] 已依劇情路線前往 {npc_id}")
        _print_state(state)
    return state


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--api-url", default="http://127.0.0.1:8300")
    parser.add_argument("--npc", default="vidalia")
    parser.add_argument("--session-id", default=f"terminal-{uuid4().hex[:10]}")
    parser.add_argument("--once", help="send one message and exit")
    parser.add_argument(
        "--allow-rule-based",
        action="store_true",
        help="allow the deterministic fallback instead of requiring a live model",
    )
    args = parser.parse_args()

    try:
        with httpx.Client(base_url=args.api_url.rstrip("/"), timeout=90) as client:
            capabilities = client.get("/api/capabilities")
            if capabilities.status_code != 200:
                print(
                    f"無法讀取後端模式：{_error_message(capabilities)}",
                    file=sys.stderr,
                )
                return 1
            generation_mode = capabilities.json().get("generation_mode")
            if generation_mode != "external_model" and not args.allow_rule_based:
                print(
                    "後端目前是 rule_based，不是真實 NPC 模型。請用 "
                    "MODEL_GATEWAY_URL 啟動後端；若刻意要測 fallback，"
                    "請加 --allow-rule-based。",
                    file=sys.stderr,
                )
                return 2
            response = client.post(
                "/api/game/start", json={"session_id": args.session_id}
            )
            if response.status_code != 201:
                print(f"無法開始遊戲：{_error_message(response)}", file=sys.stderr)
                return 1
            state = response.json()
            _print_state(state)
            npc_id = args.npc
            try:
                state = _travel_to_npc(
                    client,
                    session_id=args.session_id,
                    state=state,
                    npc_id=npc_id,
                )
            except RuntimeError as exc:
                print(f"無法前往角色所在場景：{exc}", file=sys.stderr)
                return 1

            if args.once:
                _submit_turn(
                    client,
                    session_id=args.session_id,
                    state=state,
                    npc_id=npc_id,
                    message=args.once,
                )
                return 0

            print("輸入訊息；/npc <id> 切換角色，/state 看狀態，/quit 離開。")
            while True:
                raw = input(f"你 → {npc_id}：").strip()
                if not raw:
                    continue
                if raw in {"/quit", "/exit"}:
                    return 0
                if raw == "/state":
                    _print_state(state)
                    continue
                if raw.startswith("/npc "):
                    npc_id = raw.removeprefix("/npc ").strip()
                    print(f"目標角色改為 {npc_id}")
                    continue
                try:
                    state = _submit_turn(
                        client,
                        session_id=args.session_id,
                        state=state,
                        npc_id=npc_id,
                        message=raw,
                    )
                except RuntimeError as exc:
                    print(f"請求失敗：{exc}", file=sys.stderr)
    except (httpx.HTTPError, OSError) as exc:
        print(f"連不到遊戲後端 {args.api_url}: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
