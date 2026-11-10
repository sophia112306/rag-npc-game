# A／D 整合進度

整體里程碑：`█████████░ 90%`（M0～M2c、M4 完成；M3 程式整合完成、真實服務待驗收）

| 階段 | 狀態 | 可驗收成果 |
| --- | --- | --- |
| M0：設計與契約 | `██████████ 100%` | 四類資料邊界、回合流程、A／B／C／D 責任與整合缺口已盤點 |
| M1：基本串接 | `██████████ 100%` | 既有前端可建立 Session、送文字、顯示開發替身回覆並讀取正確回合狀態 |
| M2a：保存與結果處理 | `██████████ 100%` | SQLite、migration、完整回合交易、跨重啟去重與版本衝突已完成 |
| M2b：內容與知識隔離 | `██████████ 100%` | 世界／角色內容結構、NPC 記憶來源、授權後生成背景與 PlayerViewState 已完成 |
| M2c：核准事件介面 | `██████████ 100%` | 初始操作白名單、事件原子核准、私有決策稽核與同交易保存已完成 |
| M3：真正生成 | `█████████░ 90%` | Gateway、動態台詞、安全回復已完成；待 B 的真實端點、RAG 與角色品質驗收 |
| M4：世界持續發展 | `██████████ 100%` | 有來源的 NPC 目標、承諾、回合時鐘、記憶承接與動態任務已完成 |
| A1：瀏覽器語音互動 | `█████████░ 90%` | STT transcript 與瀏覽器 TTS 已完成；待實機麥克風中文辨識驗收 |

## M1 已完成

- 合併 `frontend/babylon-game`，保留 Phaser 2D 主畫面與 Babylon.js 3D 原型。
- 統一前端與 FastAPI 的文字行動契約。
- 加入玩家可見角色 API 與 localhost CORS。
- 加入 `state_version` 衝突檢查及程序內 `action_id` 去重。
- 開發替身只產生對話，不直接修改背包、核心設定或規則數值。
- 鎖定 Python 3.12，補上開發測試依賴與啟動文件。

## M1 驗收

- `python -m pytest -q`：5 passed。
- `npm run build`：Next.js、TypeScript 與 `/`、`/experiments`、`/experiments/babylon` build 通過。
- 雙服務實際啟動：前端 `/` 回應 200；後端 health、CORS、start、turn、state 均通過 live HTTP 驗收。
- 同一 `action_id` live 重送後仍為第 1 回合、`state_version=2`，確認程序內去重成立。
- 本次環境的瀏覽器控制主機不可用，未執行自動化視覺點擊；已用 production build、實際前端頁面回應與 live API 全流程替代驗證。

## M2a 已完成

- 新增 SQLAlchemy async repository、SQLite、Alembic 初始 migration 與 app 啟動自動升級。
- 原子保存 Session 狀態、ActionRecord、對話、核准事件及完整回應。
- 以 canonical JSON＋SHA-256 比對有效請求內容；同 ID 同內容重播原結果，不同內容回 409。
- 以 `state_version` compare-and-swap 防止過期動作覆蓋新狀態。
- 保存過程任一步驟失敗時，狀態、事件、對話與 ActionRecord 一起 rollback。
- 前端在連線結果不確定時保留原 `action_id` 重送；明確版本衝突時重新取得最新狀態。

## M2a 驗收

- `python -m pytest -q`：14 passed。
- migration upgrade／downgrade、app 啟動 migration、跨 engine 與跨 app 重啟接續均通過。
- 同 ID 不同內容、舊版本、完整交易 rollback 均有自動化測試。
- `npm run build`：Next.js、TypeScript 與全部既有 routes 通過 production build。

## M2b 已完成

- 新增只含玩家可見欄位的 `PlayerViewState`；角色內部關係、真相軸、結局旗標及 NPC 私有資料不再由遊戲 API 回傳。
- 新增 WorldCanon、CharacterDefinition、KnowledgeRecord、MemoryRecord 資料表、Pydantic 契約及 Alembic migration。
- 角色設定帶有來源與完整度；現有維達利亞資料只標示為 `incomplete` 的前端原型來源，不自行補寫缺失世界觀。
- NPC 生成背景依 Session、目標 NPC、解鎖狀態、可用回合及有效記憶過濾。
- app 啟動只補入缺少的原型角色定義，不覆寫團隊之後維護的正式設定。

## M2b 驗收

- `PYTHONPATH=. ./.venv/bin/pytest -q`：17 passed。
- 鎖定秘密、其他 NPC 的知識、未來回合資訊及失效記憶均不會進入目標 NPC 的生成背景。
- 未註冊 NPC 不可建立生成背景；不完整角色資料會回報缺少欄位供後續流程停止或降級。
- `npm run build`：Next.js、TypeScript 與 `/`、`/experiments`、`/experiments/babylon` 全部通過 production build。

## M2c 已完成

- 將未受信任的 `StoryProposal` 與玩家可見 `ResolvedStory` 分離；最終台詞只加入已核准且可公開的事件。
- 建立固定操作白名單及 `ProposalResolver`；第一個可執行操作為 `transfer_item`，不允許任意 JSON patch、任意旗標或核心設定改寫。
- 每件事件以全有或全無方式計算；其中一項操作失敗，不會留下部分狀態。
- 成立事件由後端依核准效果產生客觀描述，不直接把模型自由文字升格成世界事實。
- 核准狀態、原因及實際效果保存於 ActionRecord 的私有 `resolution_json`；玩家 API 不回傳這份稽核資料。
- 核准狀態、成立事件、最終對話及 ActionRecord 延續 M2a 的單一交易與版本衝突保護。

## M2c 驗收

- `PYTHONPATH=. ./.venv/bin/pytest -q`：24 passed。
- 合法的既有物品可在已登記角色間移轉，並建立可追溯 GameEvent。
- 不存在物品、虛構角色及冒用他人物品均被拒絕；狀態與 GameEvent 不變。
- 多操作事件中任一操作失敗時整件回復；未核准內容不出現在最終台詞。
- Alembic `20261110_0003` app 啟動升級通過；`npm run build` production build 通過。

## M3 已完成的整合基礎

- 建立供應商無關的 `ModelGateway`、`ModelTurnRequest` 與 `ModelStoryOutput`，不綁定特定雲端模型或 vLLM SDK。
- Model request 只包含目前場景、玩家必要狀態與經 M2b 過濾的目標 NPC context；不傳送完整 `axis`、`truth_level`、隱藏 flags 或其他 NPC 私人記憶。
- 加入結構驗證、逾時、最多 1～3 次有限嘗試、暫時／永久 HTTP 錯誤分類及失敗 503 回復。
- 外部模型失敗時不增加回合、不建立 ActionRecord，也不留下部分狀態。
- 加入 opt-in HTTP adapter 與環境變數；未設定 `MODEL_GATEWAY_URL` 時不呼叫外部服務。
- 模型可生成目標 NPC 的主觀台詞與事件提案；後端固定說話者身分，客觀效果仍只用核准事件的確定性系統敘事。
- 新增 `/api/capabilities`，前端會明確顯示「開發替身」或「AI 動態」。
- B 的完整 HTTP 契約記錄於 `docs/MODEL_GATEWAY_CONTRACT.md`。

## M3 目前驗收

- `PYTHONPATH=. ./.venv/bin/pytest -q`：41 passed。
- 格式錯誤可有限修正，timeout 達上限後停止，永久設定錯誤不重試。
- fake Gateway 的動態台詞已通過完整 API 流程，玩家端不再顯示開發替身。
- 外部模型失敗的 503、Retry-After、狀態不推進均有自動化測試。
- HTTP 408／429／5xx 與 4xx 分類、Bearer header、授權 context payload 均有測試。
- `npm run build`：Next.js、TypeScript 與全部既有 routes 通過 production build。
- 尚未使用 B 的真實服務做延遲、角色一致性、RAG 召回與多回合品質驗收，因此 M3 不記為 100%。

## M4 已完成

- 新增有來源的 NPCGoal、Commitment 與 Quest 持久化結構及 Alembic migration。
- 回合時鐘只選取目標 NPC 最多 2 個到期目標、3 個未完成承諾及 2 個 open quests，避免無限制擴張 prompt。
- 新增 `establish_commitment` 白名單操作；參與者、行動者、對象及期限驗證通過後，才與來源 GameEvent 同交易保存。
- 新增 `offer_quest` 白名單操作；只能建立 `offered` 任務，模型不能替玩家自動接受、完成或失敗。
- 玩家發言保存為目標 NPC 的 interaction memory；成立事件保存為目擊 NPC 的 observed-event memory，均附 action／event 來源。
- 下一回合的 ModelGateway context 會取得相關記憶、未完成承諾、到期目標及動態任務。
- 每回合最多一個事件提案；Gateway 嘗試上限為 1～3 次，預設 2 次。
- 新增玩家安全的 quests API，前端任務列會顯示最新任務提議或目前任務。

## M4 驗收

- `PYTHONPATH=. ./.venv/bin/pytest -q`：49 passed。
- 端到端兩回合測試證明第一回合的承諾、玩家原話、目擊記憶與任務會進入第二回合的目標 NPC context。
- 同一 action 重送不會重複建立 Commitment、Quest 或 Memory；交易失敗時記憶也一起 rollback。
- 任務由已登記 giver 提供給不同的已登記 recipient；玩家 API 只回傳 visibility=player 的 open quests。
- Alembic `20261110_0005` upgrade／downgrade 與 app 啟動升級通過。
- `npm run build`：Next.js、TypeScript 與全部既有 routes 通過 production build。

## A1 瀏覽器語音互動

- 玩家按下麥克風後才啟動 Web Speech recognition，不會在載入頁面時要求權限。
- 辨識結果先放入輸入框供確認；送出 API 時使用既有 `speech_transcript`，不會把未確認內容自動提交。
- 不確定回應重試會保留相同 action ID、文字、state version 與 input type。
- 玩家可手動播放／停止 NPC 最近回覆的瀏覽器 TTS；系統成立事件不會冒充 NPC 語音。
- 不支援語音 API 或拒絕權限時，顯示／停用對應控制，文字遊戲仍可運作。
- `npm run build`：Next.js production build 與 TypeScript 通過。
- 尚未在使用者實機完成麥克風權限、中文辨識與聲音輸出測試，因此目前記為 90%。

## 已知限制

- M1 的 `minglin` 起始場景是為沿用現有可玩前端的暫時整合值，不視為最終世界觀定案。
- 真實 AI、RAG、自動記憶寫入、STT/TTS 尚未接入。
- 真實 ModelGateway 端點尚未提供；目前程式可接入，但預設仍為開發替身。
- 預設 `DevelopmentStoryPlanner` 不產生事件；要看到真正動態內容仍需接入 B 的 ModelGateway／RAG。
- 目前只有維達利亞的前端公開原型資料；私有角色設定、正式來源、初始知識與秘密解鎖條件仍待團隊提供。
- 目前白名單為 `transfer_item`、`establish_commitment`、`offer_quest`；關係、線索、任務接受／完成、固定事件與結局效果仍需依 C 的正式介面加入。

## 待 B／C 協調

- B：ModelGateway 請求／回應、逾時與錯誤格式，RAG metadata 與權限 filter 介面。
- C：固定事件 ID 與分支 ID 的對應、動態事件操作格式、強制換幕與生成式玩法的兼容方式。
- C：`Truth_C` relation payload、真相保底執行順序、單階段關係增量保存方式。
- 團隊：正式起始場景，以及完整世界觀、角色核心設定、秘密解鎖與知識來源資料。

## 下一步

1. B 提供正式 URL、認證方式、模型／RAG 能力後完成 M3 live 驗收與角色品質案例。
2. C 確認任務接受／完成、關係、固定事件與結局操作後再擴充白名單；不自行改寫現有規則語意。
