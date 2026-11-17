#!/usr/bin/env python3
"""Call the GPU contract gateway directly and validate ModelStoryOutput."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

import httpx

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from backend.content.characters import CHARACTER_PROFILES  # noqa: E402
from backend.generation.gateway import ModelStoryOutput, ModelTurnRequest  # noqa: E402
from backend.schemas.content import NPCGenerationContext  # noqa: E402
from backend.schemas.parsed_action import ParsedAction  # noqa: E402


def main(default_npc: str = "vidalia") -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://127.0.0.1:8000/generate")
    parser.add_argument("--npc", default=default_npc)
    parser.add_argument("--api-key")
    parser.add_argument("--message", default="請說明你會如何判斷一個傳聞是否可信？")
    args = parser.parse_args()

    profile = CHARACTER_PROFILES.get(args.npc)
    if profile is None:
        print(f"未知 NPC：{args.npc}", file=sys.stderr)
        return 2
    request = ModelTurnRequest(
        session_id="gateway-smoke-test",
        turn_number=1,
        state_version=1,
        current_scene_id="gateway-smoke-scene",
        player_id="gateway-smoke-player",
        player_inventory=[],
        action_message=args.message,
        action_mode="dialogue",
        parsed_action=ParsedAction(intent="dialogue"),
        target_context=NPCGenerationContext(
            npc_id=args.npc,
            setting_version=1,
            public_profile=profile.model_dump(mode="json"),
            private_profile={},
            knowledge=[],
            memories=[],
            missing_data=["尚未授權的世界秘密"],
        ),
        allowed_operations=[],
    )
    headers = {"Authorization": f"Bearer {args.api_key}"} if args.api_key else {}
    try:
        response = httpx.post(
            args.url,
            headers=headers,
            json=request.model_dump(mode="json"),
            timeout=90,
        )
        response.raise_for_status()
        output = ModelStoryOutput.model_validate(response.json())
    except (httpx.HTTPError, ValueError) as exc:
        print(f"Gateway smoke test failed: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(output.model_dump(mode="json"), ensure_ascii=False, indent=2))
    print(f"OK: {args.npc} returned valid ModelStoryOutput")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
