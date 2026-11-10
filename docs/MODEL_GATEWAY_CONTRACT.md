# ModelGateway HTTP 契約

本契約是 A／D 與 B 的供應商無關邊界。B 可以在後方使用雲端模型、校內 GPU、vLLM 或其他服務；遊戲後端只呼叫本契約，不直接依賴特定 SDK。

## 啟用方式

未設定 `MODEL_GATEWAY_URL` 時，後端使用明確標示的 `DevelopmentStoryPlanner`，不會呼叫外部服務。要啟用真實服務，設定：

```dotenv
MODEL_GATEWAY_URL=https://model-service.example/generate
MODEL_GATEWAY_API_KEY=
MODEL_GATEWAY_TIMEOUT_SECONDS=15
MODEL_GATEWAY_MAX_ATTEMPTS=2
```

API key 有值時以 `Authorization: Bearer <token>` 傳送。timeout 必須大於 0；attempts 限 1～3 次。

## Request

後端對 `MODEL_GATEWAY_URL` 發送 `POST application/json`。請求只包含生成需要的明確欄位，不包含內部 `axis`、`truth_level`、隱藏 flags、其他 NPC 的私人記憶或整份世界真相。

```json
{
  "session_id": "session-123",
  "turn_number": 1,
  "state_version": 1,
  "current_scene_id": "minglin",
  "player_id": "session-123-player",
  "player_inventory": [],
  "action_message": "你願意交換線索嗎？",
  "action_mode": "dialogue",
  "parsed_action": {
    "intent": "dialogue",
    "actor_id": "player",
    "target_ids": ["vidalia"],
    "action_type": "dialogue",
    "parameters": {},
    "confidence": 1.0
  },
  "target_context": {
    "npc_id": "vidalia",
    "setting_version": 1,
    "public_profile": {},
    "private_profile": {},
    "knowledge": [],
    "memories": [],
    "active_goals": [],
    "active_commitments": [],
    "active_quests": [],
    "missing_data": ["character_definition_incomplete"]
  },
  "allowed_operations": ["transfer_item", "establish_commitment", "offer_quest"],
  "generation_budget": {
    "max_model_calls": 2,
    "max_event_proposals": 1,
    "max_active_goals": 2,
    "max_active_commitments": 3,
    "max_active_quests": 2
  }
}
```

`target_context` 已由遊戲後端依 Session、NPC、解鎖狀態及回合過濾。B 不應另行加入未授權世界設定；`missing_data` 中的項目不可自行補成核心設定。

## Response

成功時回 HTTP 2xx 與單一 JSON object：

```json
{
  "intent_summary": "維達利亞審慎回應玩家的交換提議。",
  "npc_dialogue": [
    {
      "text": "我可以聽聽你的條件，但不會憑一句話交出議會保管的東西。",
      "emotion": "cautious"
    }
  ],
  "event_proposals": []
}
```

`npc_dialogue` 必須有 1～3 行。模型只產生文字與情緒；後端會把說話者固定為 request 中已授權的目標 NPC，模型不能冒充系統旁白或其他角色。NPC 台詞屬於角色的主觀發言，不會直接修改世界；客觀效果仍由後端以核准操作產生確定性系統敘事。

後端目前每回合最多接受一個 `event_proposals`；Gateway transport 最多依設定嘗試 1～3 次。可執行 operation 只限 request 的白名單。`transfer_item` 範例：

```json
{
  "intent_summary": "玩家把已持有的地圖碎片交給維達利亞。",
  "npc_dialogue": [{"text": "我會替你保管這塊碎片。", "emotion": "serious"}],
  "event_proposals": [
    {
      "event_type": "item_exchange",
      "description": "這是提案文字，不會直接升格為客觀事實。",
      "actor_id": "session-123-player",
      "target_id": "vidalia",
      "operations": [
        {
          "operation_type": "transfer_item",
          "item_id": "map_fragment",
          "from_entity_id": "session-123-player",
          "to_entity_id": "vidalia"
        }
      ],
      "witness_ids": ["session-123-player", "vidalia"],
      "visible_to_player": true
    }
  ]
}
```

模型不能指定 Session、狀態版本或實際成立結果。後端會驗證角色、持有權與操作白名單；拒絕的提案不改狀態，也不進入最終敘事。

`establish_commitment` 可建立之後回合能承接的正式承諾，但行動者必須等於承諾者，雙方必須是已登記實體，期限只能是 1～20 回合後：

```json
{
  "operation_type": "establish_commitment",
  "summary": "玩家答應帶回地圖碎片。",
  "promisor_id": "session-123-player",
  "promisee_id": "vidalia",
  "due_in_turns": 3
}
```

核准後，Commitment、來源 GameEvent、NPC 目擊記憶、對話與狀態在同一交易保存；下一回合會出現在相關 NPC 的 `active_commitments` 或 `memories`。模型不能直接寫入這些資料表。

`offer_quest` 只能建立 `offered` 任務，不能替玩家自動接受或宣告完成：

```json
{
  "operation_type": "offer_quest",
  "title": "尋回地圖碎片",
  "summary": "調查泉邊並帶回已確認存在的地圖碎片。",
  "giver_id": "vidalia",
  "recipient_id": "session-123-player",
  "due_in_turns": 5
}
```

任務必須由已登記角色提供給不同的已登記對象。核准後會保存為有來源的 Quest，玩家可從 `/api/game/{session_id}/quests` 取得，相關 NPC 下一回合則由 `active_quests` 承接。

## 錯誤與重試

- HTTP 408、429、5xx、連線失敗：視為暫時錯誤，可在上限內重試。
- HTTP 4xx（408、429 除外）：視為設定或請求錯誤，不重試。
- 2xx 但不是合法 JSON object，或不符合 `ModelStoryOutput`：在上限內重試。
- 最終失敗：遊戲 API 回 HTTP 503；不增加回合、不保存 ActionRecord 或部分世界狀態。

## B 需確認

1. 正式 `MODEL_GATEWAY_URL`。
2. 是否使用 Bearer token；token 只放環境變數，不提交 Git。
3. 服務能否直接回傳上述 JSON object；若是 OpenAI 相容的 choices/message 格式，請由 B 的 adapter 解包。
4. 部署模型名稱、structured output 支援狀況、預期延遲與最大 context。
5. RAG 是否由 B 的服務內部執行；若是，必須保留後端傳入的 NPC 授權邊界，不能做跨角色無條件檢索。
