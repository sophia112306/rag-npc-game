# A／D 整合進度

整體里程碑：`████░░░░░░ 40%`（M0、M1 完成；M2～M4 待辦）

| 階段 | 狀態 | 可驗收成果 |
| --- | --- | --- |
| M0：設計與契約 | `██████████ 100%` | 四類資料邊界、回合流程、A／B／C／D 責任與整合缺口已盤點 |
| M1：基本串接 | `██████████ 100%` | 既有前端可建立 Session、送文字、顯示開發替身回覆並讀取正確回合狀態 |
| M2：保存與結果處理 | `░░░░░░░░░░ 0%` | 待加入 SQLite、交易、跨重啟去重與事件／狀態保存 |
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

## 已知限制

- Session、去重紀錄與狀態仍只存在 FastAPI 程序記憶體，重啟會消失。
- M1 的 `minglin` 起始場景是為沿用現有可玩前端的暫時整合值，不視為最終世界觀定案。
- 真實 AI、RAG、NPC 私人記憶、資料庫、STT/TTS 尚未接入。
- `StoryProposal` 目前沒有成立事件；只回傳明確標示的替身對話。

## 待 B／C 協調

- B：ModelGateway 請求／回應、逾時與錯誤格式，RAG metadata 與權限 filter 介面。
- C：固定事件 ID 與分支 ID 的對應、動態事件操作格式、強制換幕與生成式玩法的兼容方式。
- C：`Truth_C` relation payload、真相保底執行順序、單階段關係增量保存方式。
- 團隊：正式起始場景，以及完整世界觀、角色核心設定、秘密解鎖與知識來源資料。

## 下一階段 M2

建立 SQLite repository 與 migration，讓 Session、完整回合、核准事件及 action 去重紀錄在同一交易保存；驗收重啟接續、重送不重複、版本衝突與交易失敗回復。
