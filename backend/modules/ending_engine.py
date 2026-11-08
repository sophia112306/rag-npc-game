from typing import Dict, List, Optional, Tuple
from backend.schemas.game_state import GameState
from backend.rules.ending_rules import EndingRules


class EndingEngine:
    """雙階段結局處理引擎 (草案 v3 規格)"""

    # -----------------------------------------------------------------
    # 第一階段：取得當前可選結局清單 (1~3 個)
    # -----------------------------------------------------------------
    @staticmethod
    def get_available_endings(game_state: GameState) -> List[str]:
        """
        第一階段：傳回當前可供玩家選擇的 1~3 個結局清單。

        :param game_state: 當前遊戲狀態
        :return: 可選結局名稱串列，例如 ['長眠', '塵歸']
        """
        return EndingRules.evaluate_available_endings(game_state)

    # -----------------------------------------------------------------
    # 第二階段：歸入最終結局與生成尾聲 Prompt
    # -----------------------------------------------------------------
    @staticmethod
    def resolve_final_ending(
        game_state: GameState,
        player_answer_q3: str,
        answer_q1: str = "",
        answer_q2: str = ""
    ) -> Tuple[str, str]:
        """
        第二階段：接收玩家回答維塔第三個問題的文字，判定歸入哪一個最終結局，
        並根據尾聲旗標生成用於 LLM 產出結局小說的 Prompt。

        :param game_state: 當前遊戲狀態
        :param player_answer_q3: 玩家對第 3 題 (抉擇) 的回答文字
        :param answer_q1: 玩家對第 1 題 (生命的價值) 的回答
        :param answer_q2: 玩家對第 2 題 (記憶與遺忘) 的回答
        :return: (最終判定結局名稱, 尾聲 Prompt)
        """
        available_endings = EndingEngine.get_available_endings(game_state)
        final_ending = "長眠"  # 預設保底結局

        # 1. 關鍵字比對與結局歸入
        text = player_answer_q3.lower()
        if "塵歸" in text or "抹除" in text or "消逝" in text:
            if "塵歸" in available_endings:
                final_ending = "塵歸"
        elif "新夢" in text or "重新創造" in text or "創造" in text:
            if "新夢" in available_endings:
                final_ending = "新夢"
        elif "醒來" in text or "打破" in text or "接受死亡" in text:
            if "醒來" in available_endings:
                final_ending = "醒來"
        elif "篡夢" in text or "奪取" in text:
            if "篡夢" in available_endings:
                final_ending = "篡夢"
        elif "長眠" in text or "沉睡" in text or "維持" in text:
            if "長眠" in available_endings:
                final_ending = "長眠"
        else:
            # 若回答不明確或選了不可選的結局，優先取可選清單的第一個
            if available_endings:
                final_ending = available_endings[0]

        # 2. 收集尾聲旗標 (World Epilogue Flags)
        epilogue_context = EndingEngine._build_epilogue_context(
            game_state, final_ending, answer_q1, answer_q2
        )

        # 3. 組合尾聲生成 Prompt
        prompt = EndingEngine._generate_epilogue_prompt(epilogue_context)

        return final_ending, prompt

    # -----------------------------------------------------------------
    # 內部輔助方法：建構尾聲 context 與 Prompt
    # -----------------------------------------------------------------
    @staticmethod
    def _build_epilogue_context(
        game_state: GameState,
        final_ending: str,
        answer_q1: str,
        answer_q2: str
    ) -> Dict[str, any]:
        """彙整用於生成尾聲的遊戲歷史 context"""
        vidalia_rel = game_state.npc_states.get("vidalia").relation if "vidalia" in game_state.npc_states else 0
        menmesvento_rel = game_state.npc_states.get("menmesvento").relation if "menmesvento" in game_state.npc_states else 0
        andre_rel = game_state.npc_states.get("andre").relation if "andre" in game_state.npc_states else 0

        # 長老會/外部組織篡夢主導權判定
        usurp_controller = "長老會" if game_state.flags.get("elder_cooperation", False) else "外部技術評議會"

        return {
            "final_ending": final_ending,
            "axis": game_state.axis,
            "usurp_value": game_state.usurp,
            "truth_level": game_state.truth_level,
            "is_transformed": game_state.flags.get("is_transformed", False),
            "transformed_race": game_state.flags.get("transformed_race", "無"),
            "usurp_controller": usurp_controller,
            "answer_q1": answer_q1 if answer_q1 else "未詳細說明",
            "answer_q2": answer_q2 if answer_q2 else "未詳細說明",
            "npc_relations": {
                "維達利亞": vidalia_rel,
                "門梅司文托": menmesvento_rel,
                "安德烈": andre_rel
            },
            "story_flags": game_state.flags
        }

    @staticmethod
    def _generate_epilogue_prompt(context: Dict[str, any]) -> str:
        """根據 context 產出傳給故事 LLM 的 Prompt 模板"""
        prompt = f"""你是《夢龍》遊戲的故事敘述者。玩家已完成終局維塔的三問，並達成了最終結局【{context['final_ending']}】。

【遊戲背景與尾聲參數】:
1. 最終結局: {context['final_ending']}
2. 主軸傾向值: {context['axis']} (負值偏向守夢/沉睡，正值偏向醒夢/接受死亡)
3. 世界傷痕(篡奪值): {context['usurp_value']}% (數值越高代表世界邊緣異象與毀損越嚴重)
4. 篡奪主導者(若為篡夢): {context['usurp_controller']}
5. 玩家身分狀態: {"已轉化為 " + str(context['transformed_race']) + " 族" if context['is_transformed'] else "外來者(無名者)"}

【玩家在維塔三問中的回答】:
- 第一題 (關於生命的單一與存在價值): "{context['answer_q1']}"
- 第二題 (關於記憶的痛苦與遺忘的慈悲): "{context['answer_q2']}"

【NPC 關係與命運去向】:
- 維達利亞 (關係值: {context['npc_relations']['維達利亞']}): {"深情挽留並依附主角" if context['npc_relations']['維達利亞'] >= 60 else "冷淡肅穆地觀望世界變化"}
- 門梅司文托 (關係值: {context['npc_relations']['門梅司文托']}): {"親手將塵歸令交付主角，釋懷合眼" if context['npc_relations']['門梅司文托'] >= 60 else "默然看著因果流轉"}
- 安德烈 (關係值: {context['npc_relations']['安德烈']}): {"在屏障裂隙前向主角致敬" if context['npc_relations']['安德烈'] >= 40 else "遠遠戒備"}

請根據上述的所有歷史參數與玩家的回答，撰寫一段 3 到 5 段、具備強烈文學史詩感與情感渲染力的結局尾聲小說，完整交代夢境世界、三族命運以及主角的最終歸宿。
"""
        return prompt

if __name__ == "__main__":
    print("=== 正在測試 EndingEngine 雙階段結局處理邏輯 ===")

    # 1. 建立測試用的 GameState (模擬階段四)
    gs = GameState(session_id="ending_test", axis=0, truth_level=3)
    gs.flags["has_dust_token"] = True

    # 2. 第一階段：取得可選結局
    available = EndingEngine.get_available_endings(gs)
    print(f"【第一階段可選結局】: {available}")  # 應顯示 ['長眠', '醒來', '塵歸']

    # 3. 第二階段：傳入玩家回答，判定歸入結局並產生尾聲 Prompt
    q1 = "生命因為只有一次，所以每一個選擇才彌足珍貴。"
    q2 = "銘記雖然痛苦，但也是我們活過的唯一證明。"
    q3 = "我選擇使用塵歸令，讓我自己抹除，結束這場入侵。"

    final_ending, epilogue_prompt = EndingEngine.resolve_final_ending(
        gs, player_answer_q3=q3, answer_q1=q1, answer_q2=q2
    )

    print(f"【第二階段最終判定結局】: {final_ending}")
    print("\n【生成的尾聲 Prompt 預覽】:\n" + epilogue_prompt[:300] + "...\n")
    print("=== EndingEngine 所有雙階段邏輯驗證完畢！ ===")