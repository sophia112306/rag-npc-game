from pathlib import Path
from typing import Dict, List, Optional, Any
from backend.config import settings
from backend.schemas.game_state import GameState
from backend.services.llm_client import LocalLoRALLMClient


class ModelGateway:
    """統一管理敘事 AI 呼叫的閘道器"""

    def __init__(self):
        self.llm = LocalLoRALLMClient()
        self.system_prompt = self._load_system_prompt()

    def _load_system_prompt(self) -> str:
        prompt_file = Path(settings.INPUT_PARSER_PROMPT_PATH)
        if prompt_file.exists():
            return prompt_file.read_text(encoding="utf-8")
        for fallback_name in ["input_parser_2.txt", "input_parser.txt"]:
            fallback = Path(fallback_name)
            if fallback.exists():
                return fallback.read_text(encoding="utf-8")
        raise FileNotFoundError(f"找不到系統提示詞檔案：{prompt_file}")

    def run_narrative_turn(
        self,
        player_input: str,
        game_state: GameState,
        allowed_events: List[str],
        forced_event: Optional[str] = None,
        ai_guidance: Optional[Dict[str, Any]] = None,
        active_speaker: str = "menmesvento",
        chat_history: Optional[List[Dict[str, str]]] = None
    ) -> Dict[str, Any]:
        state_summary = (
            f"【當前狀態】axis: {game_state.axis}, usurp: {game_state.usurp}, "
            f"story_phase: {game_state.story_phase.value}, "
            f"allowed_events: {allowed_events}\n"
        )
        if forced_event:
            state_summary += f"【系統強制觸發事件】本回合務必觸發事件：{forced_event}（請將 event_done 設為 \"{forced_event}\"）\n"
        if ai_guidance and ai_guidance.get("remedy_hints"):
            state_summary += f"【劇情引導提示】{' '.join(ai_guidance['remedy_hints'])}\n"

        user_prompt = (
            f"{state_summary}"
            f"【在場角色】{active_speaker}\n"
            f"【玩家發言】{player_input}"
        )

        messages = [{"role": "system", "content": self.system_prompt}]
        if chat_history:
            messages.extend(chat_history[-6:])
        messages.append({"role": "user", "content": user_prompt})

        return self.llm.generate_json(messages)
