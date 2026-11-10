# A／D 整合進度

整體里程碑：`███████░░░ 70%`（M0、M1、M2a、M2b、M2c 完成；M3～M4 待辦）

| 階段 | 狀態 | 可驗收成果 |
| --- | --- | --- |
| M0：設計與契約 | `██████████ 100%` | 四類資料邊界、回合流程、A／B／C／D 責任與整合缺口已盤點 |
| M1：基本串接 | `██████████ 100%` | 既有前端可建立 Session、送文字、顯示開發替身回覆並讀取正確回合狀態 |
| M2a：保存與結果處理 | `██████████ 100%` | SQLite、migration、完整回合交易、跨重啟去重與版本衝突已完成 |
| M2b：內容與知識隔離 | `██████████ 100%` | 世界／角色內容結構、NPC 記憶來源、授權後生成背景與 PlayerViewState 已完成 |
| M2c：核准事件介面 | `██████████ 100%` | 初始操作白名單、事件原子核准、私有決策稽核與同交易保存已完成 |
| M3：真正生成 | `░░░░░░░░░░ 0%` | 待接 B 的 ModelGateway、RAG 與知識權限測試 |
| M4：世界持續發展 | `░░░░░░░░░░ 0%` | 待接 NPC 目標、承諾、回合時鐘與動態任務 |

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

## 已知限制

- M1 的 `minglin` 起始場景是為沿用現有可玩前端的暫時整合值，不視為最終世界觀定案。
- 真實 AI、RAG、自動記憶寫入、STT/TTS 尚未接入。
- 預設 `DevelopmentStoryPlanner` 不產生事件；要看到真正動態內容仍需接入 B 的 ModelGateway／RAG。
- 目前只有維達利亞的前端公開原型資料；私有角色設定、正式來源、初始知識與秘密解鎖條件仍待團隊提供。
- 初始白名單只有 `transfer_item`；關係、承諾、線索、固定事件與結局效果需依 C 的正式介面逐項加入，不能由模型任意指定。

## 待 B／C 協調

- B：ModelGateway 請求／回應、逾時與錯誤格式，RAG metadata 與權限 filter 介面。
- C：固定事件 ID 與分支 ID 的對應、動態事件操作格式、強制換幕與生成式玩法的兼容方式。
- C：`Truth_C` relation payload、真相保底執行順序、單階段關係增量保存方式。
- 團隊：正式起始場景，以及完整世界觀、角色核心設定、秘密解鎖與知識來源資料。

## 下一階段 M3

建立可替換的 ModelGateway、逾時／有限重試／結構驗證與失敗回復，再接 B 的模型與 RAG。未取得 B 的正式端點前只做介面與測試替身，不把它記為真實 AI 已完成。
