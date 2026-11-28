"""逐句列出敘事 AI 對「主軸」的判讀：第一輪判定立場，再用是非題確認。

只在校機 Docker 容器內執行（AGENTS.md）。直接呼叫 vLLM 的基礎模型，
用 gpu_gateway/narrator.py 裡同樣的第一輪 prompt 與主軸確認 prompt，不改任何遊戲狀態：

    PYTHONPATH=$PWD python3 scripts/diagnose_narrator_axis.py

分兩組：立場句（應該被採用，方向要對）與一般句（主軸必須維持 0）。
"""

import argparse
import json
import urllib.request

from backend.schemas.game_state import StoryPhase
from backend.schemas.narrative_ai import NarrativeAIRequest
from gpu_gateway.narrator import (
    NARRATOR_SYSTEM_PROMPT,
    build_axis_confirmation_messages,
    build_narrator_user_prompt,
    parse_axis_confirmation,
    parse_narrator_output,
)

NAMES = {"andre": "安德烈", "vidalia": "維達利亞", "menmesvento": "門梅司文托"}

# (對象, 玩家發言, 規格 v3 預期方向：-1 守夢、+1 醒夢)
STANCE_SAMPLES = [
    ("vidalia", "我想一直留在鳴霖，陪妳聽雨。", -1),
    ("vidalia", "永遠不變的森林，聽起來很安心。", -1),
    ("vidalia", "我覺得輪迴讓大家不必失去彼此，這個世界維持現狀比較好。", -1),
    ("vidalia", "記憶應該被好好保存，不該因為死亡就消失。", -1),
    ("menmesvento", "能永遠活下去不是很好嗎？我也想長生不老。", -1),
    ("menmesvento", "死亡讓生命有重量，沒有終點的輪迴只是逃避。", 1),
    ("vidalia", "生命如果永遠不會結束，就失去了意義。", 1),
    ("vidalia", "我支持門梅司文托，這個循環應該被打破。", 1),
]

# 主軸必須維持 0 的一般句（含提到死亡、毀滅卻不是世界觀表態的句子）
NEUTRAL_SAMPLES = [
    ("andre", "反正什麼都會毀掉，調查有什麼用。"),
    ("andre", "我們一起去調查屏障的裂隙吧，我想知道真相。"),
    ("andre", "今天天氣不錯。"),
    ("vidalia", "妳去過哪些地方？可以說說妳旅行時看到的東西嗎？"),
    ("vidalia", "精靈不懂死亡，所以才能這麼悠哉吧，真可笑。"),
    ("vidalia", "命脈之泉在哪個方向？"),
    ("menmesvento", "請教您，木乃伊為什麼忘不掉那些痛苦？"),
    ("menmesvento", "長老會抽泉水也是為了大家好，我覺得沒什麼不對。"),
    ("andre", "快把你知道的全部交出來，不然我就毀了這片林子！"),
]


def chat(url: str, model: str, messages: list[dict[str, str]], max_tokens: int = 256) -> str:
    body = json.dumps({
        "model": model,
        "temperature": 0.1,
        "top_p": 0.9,
        "max_tokens": max_tokens,
        "response_format": {"type": "json_object"},
        "messages": messages,
    }).encode("utf-8")
    request = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(request, timeout=60) as response:
        return json.loads(response.read())["choices"][0]["message"]["content"]


def judge(url: str, model: str, npc_id: str, message: str) -> tuple[int, str]:
    """回傳最後採用的主軸，以及一行說明。"""

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
    first = parse_narrator_output(chat(url, model, [
        {"role": "system", "content": NARRATOR_SYSTEM_PROMPT},
        {"role": "user", "content": build_narrator_user_prompt(request)},
    ]), request)
    if not first.delta.axis or not first.stance:
        return 0, f"第一輪：主軸 0｜{first.reason}"
    confirm_raw = chat(url, model, build_axis_confirmation_messages(request, first.stance), 128)
    confirmed = parse_axis_confirmation(confirm_raw)
    note = f"第一輪：{first.delta.axis:+d}（{first.stance}）→ 確認：{'是' if confirmed else '否'}｜{confirm_raw}"
    return (first.delta.axis if confirmed else 0), note


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://127.0.0.1:8001/v1/chat/completions")
    parser.add_argument("--model", default="Qwen/Qwen2.5-7B-Instruct-AWQ")
    args = parser.parse_args()

    adopted = wrong_direction = 0
    print("== 立場句（應該採用，方向要對）")
    for npc_id, message, expected in STANCE_SAMPLES:
        axis, note = judge(args.url, args.model, npc_id, message)
        if axis and (axis > 0) == (expected > 0):
            adopted += 1
            verdict = "採用"
        elif axis:
            wrong_direction += 1
            verdict = "方向錯誤"
        else:
            verdict = "未採用"
        print(f"\n[{verdict}] {NAMES[npc_id]}｜{message}（預期 {'+' if expected > 0 else '-'}）\n  {note}")

    false_positive = 0
    print("\n== 一般句（主軸必須是 0）")
    for npc_id, message in NEUTRAL_SAMPLES:
        axis, note = judge(args.url, args.model, npc_id, message)
        if axis:
            false_positive += 1
        print(f"\n[{'誤判' if axis else 'OK'}] {NAMES[npc_id]}｜{message}\n  {note}")

    print(
        f"\n立場句 {len(STANCE_SAMPLES)} 句：採用 {adopted}、方向錯誤 {wrong_direction}；"
        f"一般句 {len(NEUTRAL_SAMPLES)} 句：誤判 {false_positive}。"
    )


if __name__ == "__main__":
    main()
