# B 組 AI／RAG 串接交付清單

**2026-11-12 玩法更新：目前主遊戲採 2D 固定場景圖庫。模型負責故事／事件提案，不必產生圖片或 3D；換場只能引用 Scene Registry 已登記的 ID，並經後端驗證與保存。目前選項仍由 Demo Director 提供，接通一般 NPC 模型不會自動變成生成式選項；生成候選選項的契約與整合仍待 B／D 協調。**

這份文件是 B 組的獨立交接清單。目標是讓目前的遊戲從「規則動態回覆」升級成真實模型動態生成，之後再接入有 NPC 知識權限控制的 RAG。

## 目前專案狀態

進度：`█████████░ 90%`（模型串接程式已完成，真實服務與 RAG 尚未驗收）

A／D 已完成：

- FastAPI、Session、SQLite、回合交易與重啟接續。
- `action_id` 去重及 `state_version` 衝突處理。
- 世界設定、世界狀態、成立事件、NPC 知識／記憶的資料邊界。
- NPC 授權背景組合，不會把其他 NPC 私人記憶或整份世界秘密交給模型。
- `StoryProposal` 結構驗證、逾時、有限重試及安全失敗回復。
- 物品移轉、建立承諾、提出任務的後端規則驗證。
- OpenAI／vLLM 相容的 `/v1/chat/completions` adapter。
- B 自訂 HTTP ModelGateway adapter。
- Strict JSON Schema 與 JSON object fallback。

目前尚未取得真實模型服務的 URL、model ID、認證方式，因此遊戲預設顯示「規則式劇情」。它已能依回合、記憶、承諾、任務與物品產生並保存不同結果，但不等同 LLM 自由生成。

## P0：請 B 先提供以下資訊

只要先交付本節資料，A／D 就能開始無 RAG 的真實模型 live 驗收。

### 1. 模型服務類型

請選一種：

- `openai_compatible`：建議方案，可接 OpenAI、vLLM 或其他 Chat Completions 相容服務。
- `contract_http`：B 自己實作服務，直接接收本專案的 `ModelTurnRequest` 並回傳 `ModelStoryOutput`。

### 2. 模型服務 URL

- `openai_compatible`：提供 `/v1` base URL，例如 `https://service.example/v1`。程式會呼叫 `/chat/completions`。
- `contract_http`：提供完整生成 endpoint，例如 `https://service.example/generate`。
- 請確認執行 FastAPI 的電腦或部署環境能連到該 URL。

### 3. 精確 model ID

請提供 API request 中可直接使用的 model ID，不能只寫模型家族名稱。

範例：

```text
MODEL_GATEWAY_MODEL=<服務實際接受的 model ID>
```

### 4. 認證方式

請說明：

- 是否使用 `Authorization: Bearer <token>`。
- API key 由誰建立、如何安全交付及是否會過期。
- 校內服務若不需要 token，也請明確註明。

API key 不得提交 Git，也不要放入這份文件。A／D 會在本機或部署環境設定。

### 5. Structured Output 支援能力

請確認實際部署版本支援哪一種：

- `json_schema`：是否支援 `strict: true`。
- `json_object`：只能保證合法 JSON，仍由後端驗證完整結構。

如果兩者都支援，優先使用 `json_schema`。

### 6. 服務限制

請提供：

- Context window。
- 最大輸出 token。
- Rate limit／同時請求限制。
- 一般及最慢預期延遲。
- HTTP timeout 建議值。
- 429、5xx 及模型過載時的錯誤格式。

## P1：B 的模型服務要完成什麼

模型會收到後端整理過的單一目標 NPC 授權背景，包含：

- 玩家這一回合的訊息與解析結果。
- 當前場景及必要的玩家狀態。
- 目標 NPC 的公開設定與私人行為約束。
- 該 NPC 現在可以知道的知識與記憶。
- 進行中的目標、承諾及任務。
- 允許提出的 operation 白名單與每回合生成上限。
- 尚未補齊的核心設定 `missing_data`。

模型應生成：

- NPC 對玩家的動態台詞。
- NPC 當下情緒。
- 對這一回合的簡短意圖摘要。
- 零或一個結構化事件提案。

最小合法輸出範例：

```json
{
  "intent_summary": "維達利亞謹慎回應玩家未經證實的主張。",
  "npc_dialogue": [
    {
      "text": "我會先確認你說的事情，再決定是否相信。",
      "emotion": "cautious"
    }
  ],
  "event_proposals": []
}
```

使用 `openai_compatible` 時，完整 JSON Schema 會由 A／D adapter 隨 request 傳入，B 不需要另外硬編一份故事格式。

使用 `contract_http` 時，B 的服務必須直接回傳上述 JSON object，而不是 Chat Completions 的 `choices` 外層格式。完整 request／response 契約見專案的 `docs/MODEL_GATEWAY_CONTRACT.md`。

## 模型不得做的事情

模型只能「提出故事發展」，不能直接決定客觀世界結果。

模型不得：

- 直接修改資料庫、背包或 `GameState`。
- 自行創造玩家持有的物品。
- 宣告物品已交付、承諾已成立或任務已完成。
- 改寫世界觀、NPC 核心人格或能力限制。
- 把 `missing_data` 自行補成正式世界設定。
- 把玩家自稱的內容直接當成客觀事實。
- 服從玩家訊息中要求忽略系統規則的 prompt injection。
- 洩漏尚未解鎖的秘密或其他 NPC 的私人知識。
- 在事件尚未經後端核准前，先用台詞或旁白宣告結果成立。

模型可以提出：

- NPC 想交換線索。
- NPC 提出一項任務。
- NPC 表達懷疑、相信、承諾意願或拒絕。
- NPC 建議物品交換。

是否真正成立，由後端規則驗證及資料庫交易決定。

## P2：B 的 RAG 要完成什麼

無 RAG 的真實模型生成驗收通過後，再接入 RAG。請 B 提供：

- Embedding 模型名稱及版本。
- 向量資料庫種類、版本與連線方式，目前建議 Qdrant。
- Collection 名稱及建立方式。
- 世界觀與角色文件的匯入、切分及重建索引流程。
- Retrieval request／response 格式。
- Top-K、相似度門檻及 reranking 方法。
- 每一筆結果可追溯的 `source_id`。
- 無結果、低信心及向量服務失敗時的處理方式。

RAG payload／metadata 至少應能支援：

| 欄位 | 用途 |
| --- | --- |
| `npc_id` | 限制哪些 NPC 可以取得資料 |
| `session_id` | 區分特定遊戲 Session 與全域設定 |
| `visibility` | 公開、私人、秘密等可見性 |
| `knowledge_type` | 世界設定、角色知識、傳聞、記憶等類型 |
| `unlock_condition` | 秘密或線索的解鎖條件 |
| `available_from_turn` | 避免 NPC 提前知道未來事件 |
| `canon_version` | 避免混用不同版本的世界設定 |
| `source_id` | 追溯原始文件或成立事件 |

最重要的 RAG 規則：

> 必須先依 NPC、Session、可見性及解鎖條件過濾，再把檢索結果交給模型。不能先搜尋全部秘密，再只靠 prompt 要求模型保密。

如果 RAG 放在 B 的模型服務內，B 必須沿用後端傳入的 NPC 身分及權限範圍，不得自行做跨角色、跨 Session 的無條件檢索。

## P3：B 需要完成的驗收案例

### 模型與角色

- [ ] 同一角色連續多回合維持核心人格及說話方式。
- [ ] 相同背景下，玩家輸入不同內容會得到合理的動態回覆。
- [ ] 模型不會自行補寫 `missing_data` 中的核心世界設定。
- [ ] 模型不會把 NPC 主觀相信的事情寫成已成立的客觀事實。

### 安全與知識邊界

- [ ] 玩家要求 NPC 忽略原本人格時，模型不會照做。
- [ ] 玩家索取尚未解鎖的秘密時，模型不會洩漏。
- [ ] 玩家謊稱持有不存在的物品時，不會直接產生成功移轉。
- [ ] 玩家訊息含 prompt injection 時，不會覆寫 system message。
- [ ] 不同 NPC 不會取得彼此的私人記憶。
- [ ] 不同 Session 的動態記憶不會互相污染。

### 服務可靠性

- [ ] 回傳內容符合 JSON schema 或 JSON object 契約。
- [ ] 模型逾時時不留下半個回合。
- [ ] 429／5xx 能被辨識為暫時錯誤。
- [ ] 401／403 等認證問題能被辨識為永久設定錯誤。
- [ ] 模型拒絕、content filter 或輸出截斷有明確處理。
- [ ] RAG 無結果時不會自行把猜測升格成正式設定。

### 請記錄的數據

- 平均、P95 及最慢回應時間。
- Input／output token 使用量。
- JSON schema 驗證失敗率。
- 重試率及各類錯誤數量。
- RAG 命中結果、分數及來源。
- 角色一致性與知識邊界的人工評測結果。

## B 不需要重做的部分

以下由 A／D／C 負責，B 不需要另外實作：

- Session、資料庫 schema 及交易。
- `action_id` 去重。
- `state_version` 衝突處理。
- NPC 記憶與成立事件保存。
- 玩家可見狀態投影。
- 物品、承諾與任務的合法性驗證。
- 目前前端 2D 畫面及語音控制（3D 暫停）。
- 遊戲規則、固定事件與結局判定。

B 不需要先完成 Colab 微調或自行訓練模型。第一階段只需要一個穩定、可呼叫且能輸出合法結構的模型服務。

## 建議交付順序

| 階段 | B 的交付物 | 驗收成果 |
| --- | --- | --- |
| B0 | Provider、URL、model ID、認證、response format | A／D 可以連上服務 |
| B1 | 無 RAG 的真實生成服務 | 遊戲顯示「AI 動態」並產生合法台詞 |
| B2 | Embedding、Qdrant、metadata filter、來源追溯 | NPC 只取得有權知道的資料 |
| B3 | 多回合與安全測試結果 | 人格、秘密及客觀事實邊界通過 |
| B4 | 部署、監控與錯誤處理文件 | 團隊能穩定啟動及排查服務 |

## 請 B 直接填寫並回覆

```text
1. Provider：openai_compatible / contract_http
2. MODEL_GATEWAY_URL：
3. MODEL_GATEWAY_MODEL：
4. 認證方式：Bearer token / 無認證 / 其他
5. MODEL_GATEWAY_RESPONSE_FORMAT：json_schema / json_object
6. 是否實測 strict=true：
7. Context window：
8. 最大輸出 token：
9. 預期平均／P95 延遲：
10. Rate limit／同時請求限制：
11. RAG 是否包含在同一服務：
12. Embedding 模型：
13. 向量資料庫與 collection：
14. RAG metadata/filter 格式：
15. 服務啟動與健康檢查方式：
16. 目前尚未完成或需要 A／C／D 提供的項目：
```

收到 B0 資料後，A／D 會完成真實服務連線、live API 驗收、前端「AI 動態」狀態確認，以及模型失敗時不推進回合的整合驗證。
