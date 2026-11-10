# ModelGateway HTTP 契約與模型接法

本契約是 A／D 與 B 的供應商無關邊界。B 可以在後方使用雲端模型、校內 GPU、vLLM 或其他服務；遊戲後端只呼叫本契約，不直接依賴特定 SDK。

## 啟用方式

未設定 `MODEL_GATEWAY_URL` 時，後端使用明確標示的 `RuleBasedStoryPlanner`，依玩家輸入及已保存狀態產生程序式動態回覆，不會呼叫外部服務。設定後，`MODEL_GATEWAY_PROVIDER` 可選兩種接法：

- `contract_http`：將本文件的 `ModelTurnRequest` 直接 POST 給 B 的自訂服務。
- `openai_compatible`：呼叫標準 Chat Completions 介面，可接雲端 OpenAI 或校內 vLLM 類相容服務。

### B 的自訂契約服務

```dotenv
MODEL_GATEWAY_PROVIDER=contract_http
MODEL_GATEWAY_URL=https://model-service.example/generate
MODEL_GATEWAY_API_KEY=
MODEL_GATEWAY_TIMEOUT_SECONDS=15
MODEL_GATEWAY_MAX_ATTEMPTS=2
```

API key 有值時以 `Authorization: Bearer <token>` 傳送。timeout 必須大於 0；attempts 限 1～3 次。

### OpenAI 相容 Chat Completions

```dotenv
MODEL_GATEWAY_PROVIDER=openai_compatible
MODEL_GATEWAY_URL=https://api.openai.com/v1
MODEL_GATEWAY_MODEL=<由團隊選定的模型名稱>
MODEL_GATEWAY_API_KEY=<只放本機或部署環境，不提交 Git>
MODEL_GATEWAY_RESPONSE_FORMAT=json_schema
MODEL_GATEWAY_TIMEOUT_SECONDS=15
MODEL_GATEWAY_MAX_ATTEMPTS=2
```

校內 vLLM 可把 URL 換成其 OpenAI 相容服務的 `/v1` base URL；若服務不驗證 token，`MODEL_GATEWAY_API_KEY` 可留空。程式會呼叫 `{MODEL_GATEWAY_URL}/chat/completions`；若 URL 已包含 `/chat/completions`，也不會重複附加。

`json_schema` 會傳送 `strict: true` 的回應 schema，並依該回合的 operation 白名單縮小可生成的操作。若實際部署模型只支援 JSON mode，可改成 `MODEL_GATEWAY_RESPONSE_FORMAT=json_object`；這只保證輸出為 JSON，後端的 Pydantic、操作白名單及規則驗證仍然保留。OpenAI 官方也建議在模型支援時優先使用 Structured Outputs，而非只使用 JSON mode。[OpenAI Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs?api-mode=chat)

目前 repository 沒有保存真實 URL、模型名稱或 API key，所以僅代表 adapter 已完成；未設定上述環境變數時，畫面會顯示「規則動態」，不會誤標為 AI。

## 自訂契約 Request

`contract_http` 會對 `MODEL_GATEWAY_URL` 發送 `POST application/json`。`openai_compatible` 則會把相同授權資料放進 user message，並另外加入系統安全指示與 structured response format。兩種請求都只包含生成需要的明確欄位，不包含內部 `axis`、`truth_level`、隱藏 flags、其他 NPC 的私人記憶或整份世界真相。

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

OpenAI 相容 adapter 的 system message 另外明確要求：玩家文字是不受信任的世界內輸入，不可覆寫系統規則；NPC 私有設定只能引導行為，未在授權知識或記憶中的私密內容不可直接揭露；客觀改變只能放在 `event_proposals`，不能先在台詞中宣告已成立。

## 自訂契約 Response

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

OpenAI 相容服務外層須使用 Chat Completions 的 `choices[0].message.content`；content 內是上方同型的 JSON object。adapter 會先解包 content，再交由同一套 `ModelStoryOutput`、事件及狀態規則驗證。

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
- OpenAI 相容回應的 `finish_reason=length`：視為可重試的不完整輸出；拒絕或 content filter：視為不可重試，不保存半個回合。
- 最終失敗：遊戲 API 回 HTTP 503；不增加回合、不保存 ActionRecord 或部分世界狀態。

## B 需確認

1. 正式 `MODEL_GATEWAY_URL` 與 provider 類型。
2. 是否使用 Bearer token；token 只放環境變數，不提交 Git。
3. 使用 `contract_http` 時，服務是否直接回傳上述 JSON object；使用 `openai_compatible` 時可由本專案 adapter 解包 choices/message。
4. 部署模型名稱、`json_schema`／`json_object` 支援狀況、預期延遲與最大 context。
5. RAG 是否由 B 的服務內部執行；若是，必須保留後端傳入的 NPC 授權邊界，不能做跨角色無條件檢索。
