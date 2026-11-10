# RAG NPC Game

生成式 NPC 遊戲的 A／D 整合專案。現階段 M1 已串接既有 Next.js＋Phaser 前端與 FastAPI：可以建立暫存 Session、送出文字並顯示明確標示的開發替身回覆。

> 真實模型、RAG、持久化資料庫、NPC 私人記憶與語音服務尚未接入。開發替身不會修改背包、角色設定或遊戲規則數值。

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

## M1 API

- `GET /api/characters/{npc_id}`：玩家可見的公開角色資料
- `POST /api/game/start`：建立或恢復記憶體 Session
- `POST /api/game/turn`：提交 `action_id`、訊息與預期狀態版本
- `GET /api/game/{session_id}/state`：取得玩家可見狀態

同一個 `action_id` 在目前程序內重送不會重複增加回合；過期的 `expected_state_version` 會得到 HTTP 409。這些資料目前仍在記憶體中，重啟後會消失，M2 才會加入交易式資料庫保存。

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
