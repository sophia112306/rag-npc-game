from typing import List, Optional
from backend.schemas.api_response import NarrativeAIResponse


class ActionValidator:
    """敘事 AI 輸出合法性驗證器 (草案 v3 規格)"""

    @staticmethod
    def validate_narrative_response(
        response: NarrativeAIResponse,
        allowed_events: List[str]
    ) -> NarrativeAIResponse:
        """
        檢查敘事 AI 挑選的 event_done 是否合法：
        1. 填了清單外的事件則強制忽略 (設為 None)。
        2. 敘事 AI 不得直接修改真相度與關鍵旗標 (由後端事件庫套用)。

        :param response: 敘事 AI 解析後的結構
        :param allowed_events: 目前允許觸發的固定事件 ID 清單
        :return: 修正後的 NarrativeAIResponse
        """
        # 1. 檢查 event_done 合法性
        if response.event_done:
            if response.event_done not in allowed_events:
                # 填了清單外的非法事件，強制忽略
                response.event_done = None

        return response