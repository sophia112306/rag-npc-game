"""用真實模型走一段遊戲：敘事 AI 判讀對話、套用數值，NPC 依信任度與角色狀態回話。

只在校機 Docker 容器內執行（AGENTS.md）。在程序內載入本分支的後端（暫存 SQLite），
連到指定的 GPU gateway，不會動到任何正在使用的服務或存檔：

    python3 scripts/play_narrative_session.py --gateway http://127.0.0.1:8010

每回合印出玩家發言、NPC 回覆，以及判讀後實際生效的關係值、主軸、篡奪值，
和該回合送給 NPC 的信任度與角色狀態（敘事 AI 先套用數值，NPC 才回話），
用來確認語氣是否隨好感改變。
"""

import argparse
import json
import os
import tempfile
import urllib.error
import urllib.request
from pathlib import Path
from uuid import uuid4

OPENING = ("meet_andre", "walk_to_council", "meet_vidalia", "ask_for_task")

# 預設與維達利亞的對話：先拉近關係，再測重複發言與冒犯
DEFAULT_LINES = (
    "妳在鳴霖住了多久了？",
    "可以說說妳五百年前四處旅行時看到的東西嗎？",
    "我很喜歡這片森林的寧靜，好像時間都停下來了。",
    "外面的世界每樣東西都會壞掉，所以這裡讓我很安心。",
    "如果可以的話，我想留在鳴霖多陪妳一段時間。",
    "如果可以的話，我想留在鳴霖多陪妳一段時間。",
    "妳一個人看著這片森林這麼久，會覺得孤單嗎？",
    "謝謝妳願意跟我說這些，我會好好記住的。",
    "妳以前有沒有遇過像我這樣的外來者？",
    "精靈不懂死亡，所以才能這麼悠哉吧。",
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--gateway", default="http://127.0.0.1:8010", help="GPU gateway 的根網址")
    parser.add_argument("--npc", default="vidalia", help="對話的 NPC（需在鳴霖：vidalia 或 andre）")
    parser.add_argument("--line", action="append", help="自訂玩家發言，可重複；不給則用預設對話")
    parser.add_argument("--api-key", default=None)
    args = parser.parse_args()

    base = args.gateway.rstrip("/")
    try:
        with urllib.request.urlopen(f"{base}/health", timeout=10) as response:
            ready = json.loads(response.read().decode("utf-8")).get("status") == "ready"
    except (urllib.error.URLError, OSError, ValueError):
        ready = False
    if not ready:
        print(
            f"連不到 {base}/health：gateway 還沒啟動或還沒準備好。請先在容器內執行：\n"
            "  NPC_GATEWAY_HOST=127.0.0.1 NPC_GATEWAY_PORT=8010 nohup bash scripts/start_npc_gateway.sh "
            "> /tmp/narrative-gateway.log 2>&1 &\n"
            "等約 8 秒後再執行這支腳本。"
        )
        return 1
    os.environ["MODEL_GATEWAY_PROVIDER"] = "contract_http"
    os.environ["MODEL_GATEWAY_URL"] = f"{base}/generate"
    os.environ["NARRATIVE_GATEWAY_URL"] = f"{base}/narrate"
    os.environ.setdefault("MODEL_GATEWAY_TIMEOUT_SECONDS", "60")
    os.environ.setdefault("NARRATIVE_GATEWAY_TIMEOUT_SECONDS", "60")
    if args.api_key:
        os.environ["MODEL_GATEWAY_API_KEY"] = args.api_key

    from fastapi.testclient import TestClient

    from backend.main import create_app
    from backend.rules.state_rules import npc_behavior_mode, npc_trust_tier

    database = Path(tempfile.mkdtemp(prefix="narrative-session-")) / "session.db"
    app = create_app(f"sqlite+aiosqlite:///{database}")
    session_id = "narrative-probe"

    with TestClient(app) as client:
        def state():
            return client.portal.call(app.state.game_orchestrator.get_state, session_id)

        def submit(**payload):
            current = state()
            response = client.post("/api/game/turn", json={
                "session_id": session_id,
                "action_id": str(uuid4()),
                "input_type": "text",
                "expected_state_version": current.state_version,
                **payload,
            })
            if response.status_code != 200:
                raise RuntimeError(f"回合失敗 {response.status_code}：{response.text}")
            return response.json()

        client.post("/api/game/start", json={"session_id": session_id}).raise_for_status()
        for choice_id in OPENING:
            choice = next(c for c in client.get(f"/api/game/{session_id}/choices").json() if c["choice_id"] == choice_id)
            submit(
                message=choice["message"], target_npc_id=choice["target_npc_id"],
                action_mode=choice["action_mode"], destination_scene_id=choice["destination_scene_id"],
                story_choice_id=choice_id,
            )
        print(f"生成模式：{app.state.generation_mode}；敘事 AI：{'已啟用' if app.state.game_orchestrator.narrative_judge else '未啟用'}\n")

        npc_id = args.npc
        for number, line in enumerate(args.line or DEFAULT_LINES, start=1):
            before = state()
            try:
                turn = submit(message=line, target_npc_id=npc_id, action_mode="dialogue")
            except RuntimeError as exc:
                # 回合失敗時不會儲存任何變更（包含敘事 AI 的數值），繼續下一句
                print(f"── 第 {number} 回合 ──\n玩家：{line}\n  {exc}\n")
                continue
            after = state()
            npc = after.npc_states[npc_id]
            replies = [d["text"] for d in turn["story"]["dialogue"]] or ["（沒有回覆）"]
            print(f"── 第 {number} 回合 ──")
            print(f"玩家：{line}")
            for reply in replies:
                print(f"{npc.name}：{reply}")
            print(
                f"  關係值 {before.npc_states[npc_id].relation} → {npc.relation}"
                f"｜主軸 {before.axis} → {after.axis}（計入立場：{(after.recent_axis_stances or [None])[-1] or '無'}）"
                f"｜篡奪 {before.usurp} → {after.usurp}"
                f"｜本階段對話累積 +{after.phase_relation_dialogue_gain.get(npc_id, 0)}"
            )
            print(
                f"  本回合 NPC 收到：信任度 {npc_trust_tier(npc_id, npc.relation)}"
                f"｜角色狀態 {npc_behavior_mode(npc_id, npc.relation, after.axis, after.story_phase) or '（無）'}\n"
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
