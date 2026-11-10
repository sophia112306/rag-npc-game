# RAG NPC Game

生成式 NPC 遊戲的 A／D 整合專案。現階段已串接既有 Next.js＋Phaser 前端、FastAPI 與 SQLite：可以建立持久化 Session、送出文字，並依設定使用後端規則動態或外部 ModelGateway 產生 NPC 台詞與事件提案；玩家 API、NPC 私有生成背景及事件核准流程已分開。

> 預設的「規則動態」不需要模型，能依玩家輸入、回合、背包、NPC 記憶、承諾與任務產生不同回覆。B 的真實模型／RAG 與外部 STT／TTS 服務仍尚未接入；前端會誠實區分「規則動態」與「AI 動態」。

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

外部模型是選用且預設關閉。後端同時支援 B 的自訂 HTTP 契約與 OpenAI 相容 Chat Completions（可接雲端 OpenAI 或校內 vLLM）。例如在啟動後端前設定：

```bash
export MODEL_GATEWAY_PROVIDER=openai_compatible
export MODEL_GATEWAY_URL=https://api.openai.com/v1
export MODEL_GATEWAY_MODEL='<由團隊選定的模型名稱>'
export MODEL_GATEWAY_API_KEY='<本機金鑰>'
./.venv/bin/uvicorn backend.main:app --reload --port 8300
```

程式不會替團隊選定模型，也不會自動讀取或提交本機 `.env`。未設定 URL 時使用可直接遊玩的「規則動態」；完整格式、JSON schema fallback 與 B 需確認的項目見 [`docs/MODEL_GATEWAY_CONTRACT.md`](docs/MODEL_GATEWAY_CONTRACT.md)。

規則動態目前能處理招呼、場景觀察、任務詢問、明確承諾、物品交付、先前對話回想與場景移動。任務、承諾、物品移轉及換場仍需通過後端白名單驗證，並與完整回合同一交易保存。它是可驗收的程序式故事系統，不宣稱具備 LLM 的自由創作能力。

對話介面最多顯示四個由後端依 Session 產生的可點選行動，包含情境對話及目前場景可到達的地點。點選換場選項會提交含 `destination_scene_id` 的一般 `PlayerAction`，沿用相同的去重、版本、規則驗證與資料庫交易，不是只在前端切換假畫面。

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
- `GET /api/capabilities`：目前使用規則動態或外部模型，以及已開放的操作類型
- `POST /api/game/start`：建立或恢復持久化 Session
- `POST /api/game/turn`：提交 `action_id`、訊息與預期狀態版本
- `GET /api/game/{session_id}/state`：取得玩家可見狀態
- `GET /api/game/{session_id}/choices`：取得依目前公開狀態產生的可點選行動
- `GET /api/game/{session_id}/quests`：取得玩家可見且尚未結束的動態任務
- `POST /api/game/{session_id}/scene-image`：依已提交的公開狀態建立／回用圖片工作
- `GET /api/game/{session_id}/scene-image/{job_id}`：取得玩家安全的圖片工作狀態

同一個 `action_id`、同一內容重送會回傳原結果；同 ID 換成不同內容或提交過期的 `expected_state_version` 會得到 HTTP 409。Session、狀態、對話、核准事件與完整回應會以單一交易保存，後端重啟後仍可接續。

玩家 API 只回傳 `PlayerViewState`，不包含角色私有設定、NPC 關係數值、未解鎖知識或私人記憶。後端已建立 WorldCanon、角色設定、KnowledgeRecord 與 MemoryRecord 結構；NPC 生成背景會依 NPC、Session、解鎖狀態和可用回合過濾。這些結構已能送入 ModelGateway，但尚未用 B 的真實模型／RAG 服務驗收。

未受信任的 `StoryProposal` 會先通過固定操作白名單。`transfer_item` 會確認行動者、接收者及實際持有權；`change_scene` 會確認目的地已登記且與目前場景相連。不存在的物品、角色、場景或不可直達的路線會整件拒絕；核准／拒絕紀錄只存後端，玩家只會看見已成立且可公開的事件與最終敘事。

目前白名單也支援 `establish_commitment` 與 `offer_quest`。承諾、任務、玩家發言記憶與目擊事件會和回合同一交易保存，下一回合放入相關 NPC 的授權 context。生成任務只能先成為待接受提議，不能由模型自行標記為已接受或完成。

## 畫面與圖片素材

版本化 fallback 資產中的命脈之泉、符石林、流塵谷與烈燚原由 OpenAI 內建圖片生成工具製作，工具沒有回傳底層模型名稱，因此不在文件中猜測型號。檔案、尺寸、SHA-256、提示摘要與 provisional 狀態記錄於 [`frontend/public/game/scenes/manifest.json`](frontend/public/game/scenes/manifest.json)，完整提示在 [`docs/SCENE_ASSET_PROMPTS.md`](docs/SCENE_ASSET_PROMPTS.md)。

目前已加入 provider-neutral `ImageGateway`、可持久化 scene image jobs、fingerprint 去重、前端 polling 與失敗 fallback。部署端尚未注入正式圖片 provider，因此介面會標示「版本化場景」；圖片失敗不會回滾已成立的文字回合。正式生圖 adapter、API key、成本上限與獨立 worker 仍待團隊選定。

後端的單一 Scene Registry 位於 `backend/content/scenes.py`，同時提供 2D 背景、3D 遠景、玩家可見名稱、合法出口與 visual profile。Phaser 主頁會切換完整背景；Babylon.js 3D 會依同一 Session 切換遠景、地面、霧光、色盤與前景物件群。`current_scene_id`、成立事件、對話與版本會在同一交易保存，重新整理或重啟後仍可承接。

符石林與烈燚原的具體內容仍標記為暫定。Demo Story Director 可依已核准線索解鎖流塵谷／烈燚原，但這是週四展示用 fallback，仍須由 C 確認正式事件 ID、入口、出口及 E1／E2／E3 對應後才可升格為正式設定。各地點的完整在場 NPC、獨立 GLB 與碰撞配置也仍待提供。

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
