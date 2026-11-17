with open("scripts/convert_datasets_v3.py", "r", encoding="utf-8") as f:
    code = f.read()

old_block = '''    # 激怒或逼迫判定 (usurp +1~+2)
    if any(k in user_text for k in ["去死", "廢物", "滾", "毀掉", "殺了", "交出來", "少廢話", "閉嘴"]):
        usurp = 2
        if speaker in rel:
            rel[speaker] = -5
        reasons.append("玩家語氣帶有敵意與逼迫，篡奪值上升且角色好感下降。")'''

new_block = '''    # 激怒或逼迫判定 (usurp +1~+2)
    if any(k in user_text for k in ["去死", "廢物", "滾", "毀掉", "殺了", "交出來", "少廢話", "閉嘴", "搶走", "炸毀"]):
        usurp = 2
        if speaker in rel:
            rel[speaker] = -5
        reasons.append("玩家語氣帶有敵意與威脅，篡奪值上升且角色好感下降。")'''

old_vidalia = '''    # 各角色專屬好感加減規則
    if speaker == "vidalia":
        if any(k in user_text for k in ["陪伴", "理解", "一起", "守護", "真相", "辛苦", "相信妳", "傾聽"]):
            rel["vidalia"] = 4
            reasons.append("玩家展現真誠陪伴與理解，維達利亞好感上升。")
        elif any(k in user_text for k in ["冷血", "無情", "可笑", "愚蠢", "威脅", "無聊", "Instagram", "手機"]):
            rel["vidalia"] = -3
            reasons.append("玩家表現輕挑、嘲弄或冷漠，維達利亞好感下降。")'''

new_vidalia = '''    # 各角色專屬好感加減規則
    if speaker == "vidalia":
        if any(k in user_text for k in ["陪伴", "理解", "一起", "守護", "真相", "辛苦", "相信妳", "傾聽", "謝謝", "指導", "智者", "理性", "平靜", "自然法度"]):
            rel["vidalia"] = 4
            reasons.append("玩家展現真誠請益、理解或認同理性秩序，維達利亞好感上升。")
        elif any(k in user_text for k in ["冷血", "無情", "可笑", "愚蠢", "威脅", "無聊", "Instagram", "遊戲", "老鐵", "666", "表情符號", "虛擬角色", "趕快"]):
            rel["vidalia"] = -3
            reasons.append("玩家表現輕挑、嬉鬧或嘲弄，維達利亞好感下降。")'''

code = code.replace(old_block, new_block).replace(old_vidalia, new_vidalia)
with open("scripts/convert_datasets_v3.py", "w", encoding="utf-8") as f:
    f.write(code)
print("規則已更新完成！")
