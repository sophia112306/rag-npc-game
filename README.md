# RAG NPC Game

生成式 NPC 遊戲的 A／D 整合專案。現階段 M2a 已串接既有 Next.js＋Phaser 前端、FastAPI 與 SQLite：可以建立持久化 Session、送出文字並顯示明確標示的開發替身回覆。

> 真實模型、RAG、NPC 私人記憶與語音服務尚未接入。開發替身不會修改背包、角色設定或遊戲規則數值。

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
- `POST /api/game/start`：建立或恢復持久化 Session
- `POST /api/game/turn`：提交 `action_id`、訊息與預期狀態版本
- `GET /api/game/{session_id}/state`：取得玩家可見狀態

同一個 `action_id`、同一內容重送會回傳原結果；同 ID 換成不同內容或提交過期的 `expected_state_version` 會得到 HTTP 409。Session、狀態、對話、核准事件與完整回應會以單一交易保存，後端重啟後仍可接續。

## 驗證

後端契約測試：

```bash
python3.12 -m pip install -r requirements-dev.txt
python3.12 -m pytest -q
```

前端 production build：

```bash
cd frontend
npm ci
npm run build
```

整合進度與待協調項目請見 [`docs/PROGRESS.md`](docs/PROGRESS.md)。
