import json
import os

filepath = "training/data/vidalia_data.jsonl"
bak_path = filepath + ".bak"
source_path = bak_path if os.path.exists(bak_path) else filepath

SYSTEM_PROMPT = "你是鳴霖的精靈領袖維達利亞，奉行斯多葛學派哲學。請以JSON格式回應玩家對話，並根據對話內容評估數值變化。"
SCENE_PREFIX = "鳴霖森林的微光灑落在古老石階上，維達利亞神情平靜地注視著你："

def classify_vidalia(user_text: str):
    axis = 0
    usurp = 0
    vidalia_rel = 0
    reasons = []

    # 1. 敵意與暴力威脅 -> usurp +2, vidalia -5
    if any(k in user_text for k in ["搶走", "炸毀", "殺死", "宣戰", "虛擬角色", "趕快"]):
        usurp = 2
        vidalia_rel = -5
        reasons.append("玩家語氣帶有威脅、暴力或命令意味，篡奪值上升且維達利亞好感大幅下降。")
    # 2. 輕挑、戲謔、不尊重 -> vidalia -3
    elif any(k in user_text for k in ["Instagram", "遊戲", "雙擊", "666", "表情符號", "可愛", "談戀愛", "男朋友", "饒舌歌", "股票", "筆下的角色"]):
        vidalia_rel = -3
        reasons.append("玩家態度輕浮戲謔或缺乏敬意，維達利亞好感下降。")
    # 3. 真誠請益、認同理性與守護 -> vidalia +3 ~ +4
    elif any(k in user_text for k in ["謝謝", "指導", "智者", "純潔泉晶", "守護", "陪伴", "理解", "理性", "平靜", "自然", "信任"]):
        vidalia_rel = 4
        reasons.append("玩家展現真誠請益、尊重或認同斯多葛理性秩序，維達利亞好感上升。")

    # 4. 主軸判定
    if any(k in user_text for k in ["夢", "醒來", "消失", "打破", "死亡"]):
        axis = 3
        reasons.append("玩家觸及世界虛實與打破循環，主軸偏向醒夢。")
    elif any(k in user_text for k in ["留下", "永遠", "守護好", "維繫"]):
        axis = -3
        reasons.append("玩家流露守護與留戀現狀傾向，主軸偏向守夢。")

    if not reasons:
        reasons.append("一般日常對話交流，無顯著立場偏向或情緒衝突。")

    return axis, usurp, vidalia_rel, "".join(reasons)

records = []
with open(source_path, "r", encoding="utf-8") as f:
    for line in f:
        line = line.strip()
        if not line:
            continue
        item = json.loads(line)
        msgs = item.get("messages", [])
        u_txt = next((m["content"] for m in msgs if m["role"] == "user"), "")
        a_txt = next((m["content"] for m in msgs if m["role"] == "assistant"), "")
        u_txt = u_txt.split("【玩家發言】")[-1].strip() if "【玩家發言】" in u_txt else u_txt

        try:
            parsed = json.loads(a_txt)
            scene_txt = parsed["scene"] if isinstance(parsed, dict) and "scene" in parsed else f"{SCENE_PREFIX}「{a_txt}」"
        except Exception:
            scene_txt = f"{SCENE_PREFIX}「{a_txt}」"

        axis, usurp, v_rel, reason = classify_vidalia(u_txt)
        payload = {
            "scene": scene_txt,
            "speaker": "vidalia",
            "delta": {
                "axis": axis,
                "usurp": usurp,
                "relation": {"andre": 0, "vidalia": v_rel, "menmesvento": 0}
            },
            "event_done": None,
            "flags_set": [],
            "reason": reason
        }
        records.append({
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": u_txt},
                {"role": "assistant", "content": json.dumps(payload, ensure_ascii=False)}
            ]
        })

# 擴充高品質正面互動與哲學探討樣本（補足加分與主軸平衡）
extra_samples = [
    ("維達利亞，我願意陪妳一起守護鳴霖森林與命脈之泉的秩序。", "「你的承諾展現了難得的克制與責任。只要心志不為外物所動，這片林地的法度便不會輕易崩解。」", -3, 0, 5, "玩家主動承諾陪伴並守護秩序，維達利亞好感大幅上升，主軸偏向守夢。"),
    ("我能理解妳看似冷靜背後的重擔，領袖的孤獨並不容易承受吧。", "「……你比多數訪客更懂得觀察表象之下的平靜。履行職責本無需他人憐憫，但你的理解確實令人感到安穩。」", 0, 0, 5, "玩家真誠同理維達利亞的內心重擔，維達利亞好感大幅上升。"),
    ("請教我如何在混亂的局勢中保持斯多葛式的冷靜與清醒？", "「區分你能掌控的內心抉擇，與你無法掌控的外在風暴。當你不再企圖強求結果，平靜便會自然降臨。」", 0, 0, 4, "玩家謙遜請教斯多葛哲學與心智修養，維達利亞好感上升。"),
    ("我不會用暴力干涉精靈族的傳統，我尊重這片森林自己的節奏。", "「尊重自然律動的訪客並不多見。願你的行動始終與你的言辭一致。」", -2, 0, 4, "玩家尊重自然法度與精靈族立場，維達利亞好感上升，主軸微偏守夢。"),
    ("這座森林的每一道光影都如此真實，我希望能幫你們留住這份安寧。", "「安寧源自內心的秩序，而非外在的永恆。不過，你守護此地的善意，我已清楚感知。」", -4, 0, 4, "玩家表達留戀並希望維持森林安寧，維達利亞好感上升，主軸偏向守夢。"),
    ("就算這世界終有盡頭，此刻與妳並肩守護泉眼的記憶也是真實的。", "「……即便萬物終將流轉消逝，當下所踐行的品德與抉擇仍具意義。你的話語發人深省。」", -2, 0, 5, "玩家說出觸動維達利亞內心的真誠話語，維達利亞好感大幅上升。"),
    ("我帶來了裂隙周邊的觀測紀錄，希望能幫妳更理智地評估泉眼危機。", "「客觀的紀錄有助於排除無謂的猜測。你的謹慎與條理，對鳴霖而言是寶貴的助力。」", 0, 0, 4, "玩家提供理性線索協助評估危機，維達利亞好感上升。"),
    ("面對烈原的挑釁，我支持妳以冷靜克制代替盲目開戰的決定。", "「唯有不被憤怒牽引，才能看清真正的出路。很高興你沒有被狂熱的戰意蒙蔽。」", 0, 0, 4, "玩家認同維達利亞克制衝突的理性決策，維達利亞好感上升。"),
    ("維達利亞，告訴我一些古籍上沒有記載、只屬於妳自己的過去吧。", "「……精靈少向異鄉人談及私事。但既然你已展現足夠的誠意與穩重，我便為你訴說一段舊日的星軌。」", 0, 0, 5, "玩家真誠深入對話引導其說出未記載之事，維達利亞好感大幅上升。"),
    ("如果為了維繫這場永恆的安寧，必須犧牲無數靈魂的解脫，這樣真的對嗎？", "「……你的提問觸及了秩序與慈悲的邊界。維持現狀究竟是守護，還是另一種執念，我也必須重新審視。」", 4, 0, 3, "玩家理性探討輪迴代價並引發維達利亞反思，主軸偏向醒夢且好感上升。"),
    ("純潔泉晶不只是工具，它承載了妳與族人長久以來的信念吧。", "「你看見了器物背後的克制與守護。請妥善對待它，莫讓它淪為私慾的籌碼。」", -2, 0, 4, "玩家理解純潔泉晶背後的精神意義，維達利亞好感上升。"),
    ("今天風聲很靜，我不問任務也不談危機，只想安靜陪妳待一會兒。", "「……無言的陪伴有時比千言萬語更貼近自然的本真。這份片刻的寧靜，我收下了。」", -2, 0, 5, "玩家給予純粹真誠的陪伴，維達利亞好感大幅上升。")
]

for u_txt, reply, ax, us, rel_v, rsn in extra_samples:
    payload = {
        "scene": f"{SCENE_PREFIX}{reply}",
        "speaker": "vidalia",
        "delta": {
            "axis": ax,
            "usurp": us,
            "relation": {"andre": 0, "vidalia": rel_v, "menmesvento": 0}
        },
        "event_done": None,
        "flags_set": [],
        "reason": rsn
    }
    records.append({
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": u_txt},
            {"role": "assistant", "content": json.dumps(payload, ensure_ascii=False)}
        ]
    })

with open(filepath, "w", encoding="utf-8") as f:
    for r in records:
        f.write(json.dumps(r, ensure_ascii=False) + "\n")

pos = sum(1 for r in records if json.loads(r["messages"][-1]["content"])["delta"]["relation"]["vidalia"] > 0)
neg = sum(1 for r in records if json.loads(r["messages"][-1]["content"])["delta"]["relation"]["vidalia"] < 0)
zero = sum(1 for r in records if json.loads(r["messages"][-1]["content"])["delta"]["relation"]["vidalia"] == 0)
print(f"完成！總筆數: {len(records)} | 加分筆數: {pos}, 扣分筆數: {neg}, 0分筆數: {zero}")
