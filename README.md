# RAG NPC Game

生成式 NPC 遊戲的 A／D 整合專案。現階段 M3 整合基礎已串接既有 Next.js＋Phaser 前端、FastAPI 與 SQLite：可以建立持久化 Session、送出文字，並依設定顯示開發替身或外部 Gateway 的動態 NPC 台詞；玩家 API、NPC 私有生成背景及事件核准流程已分開。

> B 的真實模型／RAG 與外部 STT／TTS 服務尚未接入。開發替身不會修改背包、角色設定或遊戲規則數值。

瀏覽器版語音互動已提供：支援 Web Speech API 時可用麥克風把中文語音轉成可確認的文字，並用瀏覽器 TTS 播放 NPC 最近回覆。這不是外部 STT／TTS 服務；實際可用性取決於瀏覽器、localhost／HTTPS 與麥克風權限，文字輸入永遠保留。

## 環境

- Python 3.12
- Node.js 20.9 以上
- npm（依 `frontend/package-lock.json` 安裝）

## 啟動

後端：

```bash
python3.12 -m venv .venv
./.venv/bin/pip install -r requirements.txt
./.venv/bin/uvicorn backend.main:app --reload --port 8300
```

後端啟動時會自動執行 Alembic migration，預設資料庫為 `data/game.db`。部署或手動升級也可執行：

```bash
./.venv/bin/alembic upgrade head
```

可用 `DATABASE_URL` 改變資料庫位置，例如 `sqlite+aiosqlite:////absolute/path/game.db`。

外部模型是選用且預設關閉。可複製根目錄 [`.env.example`](.env.example) 設定 `MODEL_GATEWAY_URL`；HTTP 格式與 B 需確認的項目見 [`docs/MODEL_GATEWAY_CONTRACT.md`](docs/MODEL_GATEWAY_CONTRACT.md)。只設定 shell／部署環境變數才會生效，程式不會自動讀取或提交本機 `.env`。

前端：

```bash
cd frontend
npm ci
npm run dev
```

瀏覽器網址：

- Phaser 2D 遊戲：http://localhost:3200
- Babylon.js 3D 原型：http://localhost:3200/experiments/babylon
- FastAPI 文件：http://localhost:8300/docs
- 健康檢查：http://localhost:8300/health

前端預設呼叫 `http://localhost:8300`。需要改用其他後端時，將 `frontend/.env.example` 複製為 `.env.local` 後修改 `NEXT_PUBLIC_API_URL`。

## 目前 API

- `GET /api/characters/{npc_id}`：玩家可見的公開角色資料
- `GET /api/capabilities`：目前使用開發替身或外部模型，以及已開放的操作類型
- `POST /api/game/start`：建立或恢復持久化 Session
- `POST /api/game/turn`：提交 `action_id`、訊息與預期狀態版本
- `GET /api/game/{session_id}/state`：取得玩家可見狀態
- `GET /api/game/{session_id}/quests`：取得玩家可見且尚未結束的動態任務

同一個 `action_id`、同一內容重送會回傳原結果；同 ID 換成不同內容或提交過期的 `expected_state_version` 會得到 HTTP 409。Session、狀態、對話、核准事件與完整回應會以單一交易保存，後端重啟後仍可接續。

玩家 API 只回傳 `PlayerViewState`，不包含角色私有設定、NPC 關係數值、未解鎖知識或私人記憶。後端已建立 WorldCanon、角色設定、KnowledgeRecord 與 MemoryRecord 結構；NPC 生成背景會依 NPC、Session、解鎖狀態和可用回合過濾。這些結構尚未接到 B 的模型／RAG 服務。

未受信任的 `StoryProposal` 會先通過固定操作白名單。目前第一個可執行操作是 `transfer_item`：後端確認行動者、接收者及實際持有權後才更新狀態。不存在的物品、角色或冒用他人物品會整件拒絕；核准／拒絕紀錄只存後端，玩家只會看見已成立且可公開的事件與最終敘事。

目前白名單也支援 `establish_commitment` 與 `offer_quest`。承諾、任務、玩家發言記憶與目擊事件會和回合同一交易保存，下一回合放入相關 NPC 的授權 context。生成任務只能先成為待接受提議，不能由模型自行標記為已接受或完成。

## 驗證

後端契約測試：

```bash
./.venv/bin/pip install -r requirements-dev.txt
PYTHONPATH=. ./.venv/bin/pytest -q
```

前端 production build：

```bash
cd frontend
npm ci
npm run build
```

整合進度與待協調項目請見 [`docs/PROGRESS.md`](docs/PROGRESS.md)。
