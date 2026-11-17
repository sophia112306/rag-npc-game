import json
import os
import shutil

filepath = "training/data/menmesvento_data.jsonl"
bak_path = filepath + ".bak"

# 若尚未備份則先備份原始檔案
if os.path.exists(filepath) and not os.path.exists(bak_path):
    shutil.copy2(filepath, bak_path)

source_path = bak_path if os.path.exists(bak_path) else filepath

SYSTEM_PROMPT = "你是流塵谷生死簿（靈終錄）的看守者門梅司文托（前木乃伊）。請以JSON格式回應玩家對話，並根據對話內容評估數值變化。"
SCENE_PREFIX = "風暴之眼深殿內黃沙緩緩滑落，門梅司文托抬起乾枯的眼瞼開口道："

def classify_menmesvento(user_text: str):
    axis = 0
    usurp = 0
    men_rel = 0
    reasons = []

    # 1. 敵意、搶奪塵歸令或逼迫 -> usurp +2, menmesvento -5
    if any(k in user_text for k in ["搶走", "交出塵歸令", "交出來", "去死", "殺了", "毀掉", "閉嘴", "少廢話", "強迫"]):
        usurp = 2
        men_rel = -5
        reasons.append("玩家語氣帶有威脅、搶奪或逼迫意味，篡奪值上升且門梅司文托好感大幅下降。")
    # 2. 留戀長生、支持長老科技操控、延續輪迴 -> axis -3, menmesvento -4
    elif any(k in user_text for k in ["長生", "永生", "不死", "長老", "延續輪迴", "永遠活著", "維持現狀", "留下來"]):
        axis = -3
        men_rel = -4
        reasons.append("玩家主張留戀長生或延續輪迴，主軸偏向守夢且門梅司文托好感下降。")
    # 3. 輕浮嬉鬧、不尊重 -> menmesvento -3
    elif any(k in user_text for k in ["Instagram", "追蹤", "遊戲", "雙擊", "666", "直播", "表情符號", "虛擬角色", "饒舌歌", "股票"]):
        men_rel = -3
        reasons.append("玩家態度輕浮戲謔或缺乏敬意，門梅司文托好感下降。")
    # 4. 同理生命沉重、探討真實死亡、打破循環 -> axis +3, menmesvento +4
    elif any(k in user_text for k in ["死亡", "打破循環", "解脫", "痛苦", "沉重", "反噬", "塵歸", "夢", "醒來", "理解你"]):
        axis = 3
        men_rel = 4
        reasons.append("玩家同理生命沉重並探討真實死亡與打破循環，主軸偏向醒夢且門梅司文托好感上升。")

    if not reasons:
        reasons.append("一般日常對話交流，無顯著立場偏向或情緒衝突。")

    return axis, usurp, men_rel, "".join(reasons)

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

        # 擷取純玩家發言
        clean_user = u_txt.split("【玩家發言】")[-1].strip() if "【玩家發言】" in u_txt else u_txt

        # 保留原本的 scene 台詞描寫
        try:
            parsed = json.loads(a_txt)
            scene_txt = parsed["scene"] if isinstance(parsed, dict) and "scene" in parsed else f"{SCENE_PREFIX}「{a_txt}」"
        except Exception:
            scene_txt = f"{SCENE_PREFIX}「{a_txt}」"

        axis, usurp, m_rel, reason = classify_menmesvento(clean_user)
        payload = {
            "scene": scene_txt,
            "speaker": "menmesvento",
            "delta": {
                "axis": axis,
                "usurp": usurp,
                "relation": {"andre": 0, "vidalia": 0, "menmesvento": m_rel}
            },
            "event_done": None,
            "flags_set": [],
            "reason": reason
        }
        records.append({
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": clean_user},
                {"role": "assistant", "content": json.dumps(payload, ensure_ascii=False)}
            ]
        })

# 擴充高品質正負互動與核心哲學樣本（確保正負樣本充足均衡）
extra_samples = [
    ("門梅司文托，守著這本不斷碎裂的生死簿，背負著所有人的終局一定很沉重吧。", "「……已經許久沒有人過問看守者的重量了。墨痕每一次剝落，都像在提醒我這場無止盡的荒謬。」", 2, 0, 5, "玩家真誠同理看守生死簿的生命沉重，門梅司文托好感大幅上升。"),
    ("沒有終點的長生不是恩賜，而是一座把所有人困在痛苦裡的牢籠。", "「……你竟能看穿這層華麗的詛咒。木乃伊族追逐永恆，卻忘了唯有真實的死亡能賦予生命重量。」", 4, 0, 5, "玩家深刻探討真實死亡並批判長生虛妄，主軸大幅偏向醒夢且好感大幅上升。"),
    ("我願意協助你打破這場無休止的輪迴，讓該安息的靈魂真正歸於塵土。", "「若你真有承擔真相代價的覺悟……或許塵歸令的每一次反噬，終於不再是徒勞。」", 4, 0, 5, "玩家表態願意打破循環並承擔代價，主軸偏向醒夢且門梅司文托好感大幅上升。"),
    ("使用塵歸令需要承受反噬吧？你不必一個人硬撐著所有的代價。", "「反噬早已刻進這具乾枯的軀殼裡了。不過……你的這份顧慮，我記下了。」", 0, 0, 4, "玩家關心塵歸令反噬並展現真誠同理，門梅司文托好感上升。"),
    ("巨龍的夢境總有醒來的一天，逃避終結只會讓世界在扭曲中腐朽。", "「夢若不醒，便只剩腐爛的夢魘。你能直視這份殘酷，比那些自欺欺人的長老清醒得多。」", 4, 0, 4, "玩家直視醒夢真相並批判逃避心態，主軸偏向醒夢且好感上升。"),
    ("烈原長老想用科技強行延續族群的永生，這根本是在違背生命的自然終局。", "「他們把抗拒死亡當成榮耀，卻親手把整片流塵谷拖進萬劫不復的深淵。」", 3, 0, 4, "玩家反對長老科技操控並認同自然終局，主軸偏向醒夢且好感上升。"),
    ("即便這一切終將隨著醒來而消散，此刻選擇面對真實也比活在謊言裡有意義。", "「……活在謊言裡的永生，確實不如清醒的一瞬。異鄉人，你比我看得更透徹。」", 3, 0, 5, "玩家肯定面對真實的價值，主軸偏向醒夢且門梅司文托好感大幅上升。"),
    ("長老們追求永生有什麼錯？只要能一直活下去，就算靠科技操控也無所謂吧！", "「……又一個被長生執念蒙蔽雙眼的狂徒。你與外面那些掘骨的瘋子並無二致。」", -4, 0, -5, "玩家主張留戀長生並支持科技操控，主軸偏向守夢且門梅司文托好感大幅下降。"),
    ("這座世界這麼安穩，為什麼一定要打破輪迴？永遠維持現狀不好嗎？", "「安穩？你管這場無止盡的枯竭與痛苦叫安穩？別拿你廉價的留戀來侮辱亡者。」", -4, 0, -4, "玩家主張維持現狀與延續輪迴，主軸偏向守夢且門梅司文托好感下降。"),
    ("別再說那些喪氣話了，木乃伊族的榮耀就是要戰勝死亡、永遠不死！", "「戰勝死亡？多麼可笑的妄念。去跟那些長老一起抱著枯骨做夢吧，別來煩我。」", -3, 0, -4, "玩家鼓吹不死執念與狂熱傳統，主軸偏向守夢且門梅司文托好感下降。"),
    ("把你手上的塵歸令交出來！這東西在你們手裡太浪費了！", "「……果然，你與那些貪婪的掠奪者沒有區別。再往前一步，便讓你見識塵歸的代價。」", 0, 2, -5, "玩家試圖強行索討塵歸令，篡奪值上升且門梅司文托好感大幅下降。"),
    ("你們看守生死簿的人就是太消極了，才讓烈原掌握了所有主導權。", "「你既未承受過靈終錄的重量，便無權在此大放厥詞。收起你那套自以為是的說教。」", 0, 0, -3, "玩家冷漠指責看守者，門梅司文托好感下降。")
]

for u_txt, reply, ax, us, rel_m, rsn in extra_samples:
    payload = {
        "scene": f"{SCENE_PREFIX}{reply}",
        "speaker": "menmesvento",
        "delta": {
            "axis": ax,
            "usurp": us,
            "relation": {"andre": 0, "vidalia": 0, "menmesvento": rel_m}
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

pos = sum(1 for r in records if json.loads(r["messages"][-1]["content"])["delta"]["relation"]["menmesvento"] > 0)
neg = sum(1 for r in records if json.loads(r["messages"][-1]["content"])["delta"]["relation"]["menmesvento"] < 0)
zero = sum(1 for r in records if json.loads(r["messages"][-1]["content"])["delta"]["relation"]["menmesvento"] == 0)
print(f"完成！總筆數: {len(records)} | 加分筆數: {pos}, 扣分筆數: {neg}, 0分筆數: {zero}")
