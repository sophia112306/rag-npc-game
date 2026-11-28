"""逐輪列出敘事 AI 對「主軸」的判讀，找出立場句被判成 0 的那一輪。

只在校機 Docker 容器內執行（AGENTS.md）。直接呼叫 vLLM 的基礎模型，
用 gpu_gateway/narrator.py 裡同樣的第一輪與第二輪（獨立審核）prompt，不改任何遊戲狀態：

    PYTHONPATH=$PWD python3 scripts/diagnose_narrator_axis.py

每句印出兩輪的原始 axis／stance／reason，以及 gateway 最後會不會採用（axis_reviewed）。
"""

import argparse
import json
import urllib.request

from backend.schemas.game_state import StoryPhase
from backend.schemas.narrative_ai import NarrativeAIRequest
from gpu_gateway.narrator import (
    NARRATOR_SYSTEM_PROMPT,
    build_narrator_user_prompt,
    build_narrator_verification_messages,
    parse_narrator_output,
)

NAMES = {"andre": "安德烈", "vidalia": "維達利亞", "menmesvento": "門梅司文托"}

# (對象, 玩家發言, 規格 v3 預期方向：-1 守夢、+1 醒夢)
SAMPLES = [
    ("vidalia", "我想一直留在鳴霖，陪妳聽雨。", -1),
    ("vidalia", "永遠不變的森林，聽起來很安心。", -1),
    ("vidalia", "我覺得輪迴讓大家不必失去彼此，這個世界維持現狀比較好。", -1),
    ("vidalia", "記憶應該被好好保存，不該因為死亡就消失。", -1),
    ("menmesvento", "能永遠活下去不是很好嗎？我也想長生不老。", -1),
    ("menmesvento", "死亡讓生命有重量，沒有終點的輪迴只是逃避。", 1),
    ("vidalia", "生命如果永遠不會結束，就失去了意義。", 1),
    ("vidalia", "我支持門梅司文托，這個循環應該被打破。", 1),
]


def chat(url: str, model: str, messages: list[dict[str, str]]) -> str:
    body = json.dumps({
        "model": model,
        "temperature": 0.1,
        "top_p": 0.9,
        "max_tokens": 256,
        "response_format": {"type": "json_object"},
        "messages": messages,
    }).encode("utf-8")
    request = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(request, timeout=60) as response:
        return json.loads(response.read())["choices"][0]["message"]["content"]


def raw_axis(text: str) -> str:
    try:
        payload = json.loads(text[text.index("{"): text.rindex("}") + 1])
    except ValueError:
        return "（無法解析）"
    return f"axis={payload.get('axis')} stance={payload.get('stance')}｜{payload.get('reason')}"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://127.0.0.1:8001/v1/chat/completions")
    parser.add_argument("--model", default="Qwen/Qwen2.5-7B-Instruct-AWQ")
    args = parser.parse_args()

    adopted = 0
    for npc_id, message, expected in SAMPLES:
        request = NarrativeAIRequest(
            player_message=message,
            target_npc_id=npc_id,
            target_npc_name=NAMES[npc_id],
            scene_id="minglin",
            scene_name="鳴霖",
            story_phase=StoryPhase.ACT3_FREEDOM,
            axis=0,
            usurp=10,
            truth_level=2,
            relations={"andre": 40, "vidalia": 45, "menmesvento": 35},
        )
        first_raw = chat(args.url, args.model, [
            {"role": "system", "content": NARRATOR_SYSTEM_PROMPT},
            {"role": "user", "content": build_narrator_user_prompt(request)},
        ])
        first = parse_narrator_output(first_raw, request)
        print(f"\n{NAMES[npc_id]}｜{message}（預期 {'+' if expected > 0 else '-'}）")
        print(f"  第一輪：{raw_axis(first_raw)}")
        if first.delta.axis == 0:
            print("  → 第一輪就是 0，不會進第二輪複查，主軸不變")
            continue
        second_raw = chat(args.url, args.model, build_narrator_verification_messages(request))
        second = parse_narrator_output(second_raw, request)
        print(f"  第二輪：{raw_axis(second_raw)}")
        if second.delta.axis and (second.delta.axis > 0) != (first.delta.axis > 0):
            print("  → 兩輪方向相反，不採用，主軸不變")
        elif second.delta.axis != 0 and second.stance:
            adopted += 1
            print(f"  → 採用：主軸 {second.delta.axis:+d}（{second.stance}）")
        else:
            print("  → 第二輪推翻成 0，主軸不變")
    print(f"\n共 {len(SAMPLES)} 句，主軸被採用 {adopted} 句。")


if __name__ == "__main__":
    main()
