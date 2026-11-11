# RAG NPC Game

第一人稱版本已恢復玩家自行移動：開啟 `http://localhost:3200/experiments/babylon`，WASD 移動、拖曳環視，走近人物／地標按 E。Tab 的「世界指令」可輸入「生成 6 個符石，變成夜晚並起霧」；場景配置經後端驗證保存，校內 Hunyuan 新 GLB 會逐一載入。操作、限制與交接見 [`docs/DEMO_HANDOFF.md`](docs/DEMO_HANDOFF.md)。

生成式 NPC 遊戲的 A／D 整合專案。現階段已串接既有 Next.js＋Phaser 前端、FastAPI 與 SQLite：可以建立持久化 Session、送出文字，並依設定使用後端規則動態或外部 ModelGateway 產生 NPC 台詞與事件提案；玩家 API、NPC 私有生成背景及事件核准流程已分開。

> 預設的「規則動態」不需要模型，能依玩家輸入、回合、背包、NPC 記憶、承諾與任務產生不同回覆。B 的真實模型／RAG 與外部 STT／TTS 服務仍尚未接入；前端會誠實區分「規則動態」與「AI 動態」。

瀏覽器版語音互動已提供：支援 Web Speech API 時可用麥克風把中文語音轉成可確認的文字，並用瀏覽器 TTS 播放 NPC 最近回覆。這不是外部 STT／TTS 服務；實際可用性取決於瀏覽器、localhost／HTTPS 與麥克風權限，文字輸入永遠保留。

## 相較前次 GitHub `main` 的變更

比較基準：2026-11-11 讀取的 `origin/main`，commit `cf31218`（Demo 動態故事 PR #7）。以下是本分支新增或修正的內容；舊版里程碑紀錄見 [`docs/PROGRESS.md`](docs/PROGRESS.md)。

| 範圍 | 本次變更 |
| --- | --- |
| 角色與對話 | 鳴霖加入安德烈，流塵谷加入門梅司文托；兩人有公開角色 API、肖像、Phaser 場景互動、角色專屬詢問選項和規則動態回覆。選項帶 `story_choice_id`，以同一回合契約送到後端。角色私有設定仍未填完。 |
| 開場劇情與舊存檔 | 第一階段台詞、線索 ID 和場景圖片 prompt 改為只公開當時可觀察的資訊；符石路徑先給風沙方向，不提早發放正式裂隙地圖。舊 Demo 存檔、舊回合重送及瀏覽器對話紀錄會轉成新版公開用語。 |
| 場景與旅途地圖 | 流塵谷新增 Tiled 可走區域與 NPC 位置。首頁加入俯視旅途地圖縮圖，可展開查看鳴霖、命脈之泉、符石林、流塵谷、烈燚原；青色光點會依目前場景移動，地圖本身不觸發旅行。 |
| 音樂與預覽 | 五個遊戲場景各有一首配樂；首頁與 Babylon 試玩頁會隨場景換曲。另有獨立的維塔預覽頁 `/preview/veta`，可切換觀察視角並播放專用配樂。曲目、來源及檔案記錄見 [`docs/AUDIO_ASSETS.md`](docs/AUDIO_ASSETS.md)。 |
| 3D 與世界指令 | WASD 第一人稱、近距離互動、五場景連續地形、受限世界指令、持久化 Hunyuan asset jobs 與 GLB 即時載入。 |
| 驗證 | 本次後端 `115 passed`；Next.js production build 通過；Chrome 實際完成兩條故事路線、五場景、文字指令與三件新 GLB 載入。 |

### 目前還缺什麼

| 優先 | 待完成事項 | 主要分工 |
| --- | --- | --- |
| 1 | 把「死亡即遊戲結束」落實為後端結束狀態與前端結束畫面，接入 C 的危險事件；正式 E1／E2／E3、真相揭露條件與結局流程仍待規則整合。現在只有第一階段的防劇透修正與可玩的 Demo 分支。 | C／D／A |
| 2 | 命脈之泉、符石林、烈燚原仍沿用鳴霖的 Phaser 可走區域；需各自建立 Tiled 地圖、出生點與在場角色，再逐場檢查互動位置。旅途地圖圖片是示意路線，尚未與後端解鎖條件同步，也不能點地點旅行。 | A／D |
| 3 | 接入 B 的正式 LLM／RAG 端點與知識權限資料，驗收角色語氣、未預寫情境、世界觀一致性及 NPC 私有資訊的揭露時機。目前可直接遊玩的預設模式仍是規則動態；安德烈與門梅司文托的私有設定也是空白。 | B／D |
| 4 | 圖片 job、輪詢和 fallback 已有，但尚未接正式 ImageGateway provider；若要正式部署，還需獨立 worker、逾時回復與有限重試。 | D／B |
| 5 | 在目標瀏覽器與手機實機驗收地圖、NPC 點擊、場景音樂與中文語音辨識；目前語音使用瀏覽器能力，尚未串接外部 STT／TTS。Babylon 場景也尚無各地獨立的完整 3D NPC 模型與碰撞地圖。 | A／D／B |

目前分支適合展示 POC。公開角色設定、場景細節及路線仍有 provisional 部分，正式世界觀與玩法應由團隊確認後再定版。

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

對話介面會顯示由後端依 Session 產生的主線選項，以及安德烈、門梅司文托的角色專屬詢問選項。點選換場選項會提交含 `destination_scene_id` 的一般 `PlayerAction`，沿用相同的去重、版本、規則驗證與資料庫交易，不是只在前端切換假畫面。

前端：

```bash
cd frontend
npm ci
npm run dev
```

瀏覽器網址：

- Phaser 2D 遊戲：http://localhost:3200
- Babylon.js 3D 原型：http://localhost:3200/experiments/babylon
- 維塔獨立預覽：http://localhost:3200/preview/veta
- FastAPI 文件：http://localhost:8300/docs
- 健康檢查：http://localhost:8300/health

前端預設呼叫 `http://localhost:8300`。需要改用其他後端時，將 `frontend/.env.example` 複製為 `.env.local` 後修改 `NEXT_PUBLIC_API_URL`。

## 目前 API

- `GET /api/characters/{npc_id}`：玩家可見的公開角色資料
- `GET /api/capabilities`：目前使用規則動態或外部模型，以及已開放的操作類型
- `POST /api/game/start`：建立或恢復持久化 Session
- `POST /api/game/turn`：提交 `action_id`、訊息與預期狀態版本
- `GET /api/game/{session_id}/state`：取得玩家可見狀態
- `GET /api/game/{session_id}/choices`：取得依目前公開狀態產生的可點選行動；可用 `npc_id=andre` 或 `npc_id=menmesvento` 取得角色詢問選項
- `GET /api/game/{session_id}/quests`：取得玩家可見且尚未結束的動態任務
- `POST /api/game/{session_id}/scene-image`：依已提交的公開狀態建立／回用圖片工作
- `GET /api/game/{session_id}/scene-image/{job_id}`：取得玩家安全的圖片工作狀態

同一個 `action_id`、同一內容重送會回傳原結果；同 ID 換成不同內容或提交過期的 `expected_state_version` 會得到 HTTP 409。Session、狀態、對話、核准事件與完整回應會以單一交易保存，後端重啟後仍可接續。

玩家 API 只回傳 `PlayerViewState`，不包含角色私有設定、NPC 關係數值、未解鎖知識或私人記憶。後端已建立 WorldCanon、角色設定、KnowledgeRecord 與 MemoryRecord 結構；NPC 生成背景會依 NPC、Session、解鎖狀態和可用回合過濾。這些結構已能送入 ModelGateway，但尚未用 B 的真實模型／RAG 服務驗收。

未受信任的 `StoryProposal` 會先通過固定操作白名單。`transfer_item` 會確認行動者、接收者及實際持有權；`change_scene` 會確認目的地已登記且與目前場景相連。不存在的物品、角色、場景或不可直達的路線會整件拒絕；核准／拒絕紀錄只存後端，玩家只會看見已成立且可公開的事件與最終敘事。

目前白名單也支援 `establish_commitment` 與 `offer_quest`。承諾、任務、玩家發言記憶與目擊事件會和回合同一交易保存，下一回合放入相關 NPC 的授權 context。生成任務只能先成為待接受提議，不能由模型自行標記為已接受或完成。

## 畫面與圖片素材

首頁、Babylon 試玩頁會依五個場景切換循環背景音樂，玩家可由右上角播放或關閉；維塔預覽頁另有配樂。音樂來源、授權與檔案雜湊記錄於 [`docs/AUDIO_ASSETS.md`](docs/AUDIO_ASSETS.md)。首頁左上角的旅途地圖使用 [`world-route-map-v1.png`](frontend/public/game/world-route-map-v1.png)，可展開查看地名，青色光點依目前場景更新；圖片上的道路是美術示意，不取代後端旅行規則。

第一版採用「建置期生成、遊戲期只引用版本化資產」：命脈之泉、符石林、流塵谷與烈燚原由 OpenAI 內建圖片生成工具製作，工具沒有回傳底層模型名稱，因此不在文件中猜測型號。檔案、尺寸、SHA-256、提示摘要與 provisional 狀態記錄於 [`frontend/public/game/scenes/manifest.json`](frontend/public/game/scenes/manifest.json)，完整提示在 [`docs/SCENE_ASSET_PROMPTS.md`](docs/SCENE_ASSET_PROMPTS.md)。每回合不會重新生圖，也不會讓文字模型覆寫圖片。

目前已加入 provider-neutral `ImageGateway`、可持久化 scene image jobs、fingerprint 去重、前端 polling 與失敗 fallback。部署端尚未注入正式圖片 provider，因此介面會標示「版本化場景」；圖片失敗不會回滾已成立的文字回合。正式生圖 adapter、API key、成本上限與獨立 worker 仍待團隊選定。

後端的單一 Scene Registry 位於 `backend/content/scenes.py`，提供玩家可見名稱與合法出口；`backend/content/world_scenes.py` 從保存的設定組合 3D 空間配置。Phaser 主頁沿用生成插畫；Babylon 使用連續地形、天空、天氣與 Hunyuan GLB，玩家可自行移動探索。`current_scene_id`、場景配置、成立事件、對話與版本在同一交易保存，重新整理或重啟後仍可承接。

符石林與烈燚原的具體內容仍標記為暫定。Demo Story Director 可依已核准線索解鎖流塵谷／烈燚原，但這是週四展示用 fallback，並非一般自由旅行出口，也尚未等同 C 的正式危險事件或完整世界路線。仍須由 C 確認正式事件 ID、入口、出口及 E1／E2／E3 對應後才可升格為正式設定。各地點的完整在場 NPC、獨立 GLB 與碰撞配置也仍待提供。若未來需要即時圖片生成，應另建有預算、快取、審核與失敗回復的 ImageGateway，不和文字回合交易綁死。

校內 Hunyuan3D gateway、持久化 3D asset job 與 Babylon loader 已接通。模型有參考圖投影貼圖與平滑法線；單工、有限重試、GLB 大小／面數與外部資源檢查均保留。遊戲後端用 `HUNYUAN3D_URL=http://127.0.0.1:8081` 經 SSH tunnel 呼叫，瀏覽器只連 FastAPI。現階段支援樹木、符石、祭壇與五個已登記地點的空間重建；正式角色模型與任意文字生成整個世界仍待後續。部署與量測見 [`docs/HUNYUAN3D_GPU_SETUP.md`](docs/HUNYUAN3D_GPU_SETUP.md)。

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
