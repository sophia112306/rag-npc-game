# A／D 整合進度

整體里程碑：`██████░░░░ 60%`（M0、M1、M2a、M2b 完成；M2c～M4 待辦）

| 階段 | 狀態 | 可驗收成果 |
| --- | --- | --- |
| M0：設計與契約 | `██████████ 100%` | 四類資料邊界、回合流程、A／B／C／D 責任與整合缺口已盤點 |
| M1：基本串接 | `██████████ 100%` | 既有前端可建立 Session、送文字、顯示開發替身回覆並讀取正確回合狀態 |
| M2a：保存與結果處理 | `██████████ 100%` | SQLite、migration、完整回合交易、跨重啟去重與版本衝突已完成 |
| M2b：內容與知識隔離 | `██████████ 100%` | 世界／角色內容結構、NPC 記憶來源、授權後生成背景與 PlayerViewState 已完成 |
| M2c：核准事件介面 | `░░░░░░░░░░ 0%` | 待與 C 協調操作白名單、事件核准與狀態計算 |
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

## 已知限制

- M1 的 `minglin` 起始場景是為沿用現有可玩前端的暫時整合值，不視為最終世界觀定案。
- 真實 AI、RAG、自動記憶寫入、STT/TTS 尚未接入。
- `StoryProposal` 目前沒有成立事件；只回傳明確標示的替身對話。
- 目前只有維達利亞的前端公開原型資料；私有角色設定、正式來源、初始知識與秘密解鎖條件仍待團隊提供。

## 待 B／C 協調

- B：ModelGateway 請求／回應、逾時與錯誤格式，RAG metadata 與權限 filter 介面。
- C：固定事件 ID 與分支 ID 的對應、動態事件操作格式、強制換幕與生成式玩法的兼容方式。
- C：`Truth_C` relation payload、真相保底執行順序、單階段關係增量保存方式。
- 團隊：正式起始場景，以及完整世界觀、角色核心設定、秘密解鎖與知識來源資料。

## 下一階段 M2c

建立 `StoryProposal` 與固定操作白名單，讓 C 的規則驗證器核准或拒絕操作後，只有核准結果能更新狀態並進入最終敘事。既有固定事件、強制換幕與結局規則先維持不變，語意衝突列為待 C 協調。
