# RAG NPC Game｜夢龍世界探索原型

更新：2026-11-12（Asia/Taipei）。目前主遊戲改為 **Phaser 2D 探索＋固定寫實場景圖庫＋故事選項換場＋持久化回合**，入口為 <http://localhost:3200>。舊 3D 網址導回首頁；3D／Hunyuan 留作歷史原型，不再是遊玩依賴。正式敘事 LLM／RAG、第二幕與五結局尚未完成整合。

美術保留既有末世寫實／奇幻遺跡風格，只在遊戲端降低背景取樣解析度，沒有換成可愛手繪。五張場景各有 Tiled 可走區與互動點，M 地圖、J 手記和調查選項已接入 2D。下列歷史 3D 導覽正隨本次轉向整理，最新驗收以進度文件最上方為準。

這份 README 說明目前程式；原始設定見 [世界設計](docs/GENERATIVE_WORLD_DESIGN.md)，操作與交接見 [Demo 交接](docs/DEMO_HANDOFF.md)，歷史進度見 [PROGRESS](docs/PROGRESS.md)。舊進度百分比只代表當時驗收範圍，不代表整個遊戲完成。

完整平台的目標設計見 [系統架構總圖與判斷流程](docs/SYSTEM_ARCHITECTURE.md)，內含可下載的 SVG／PNG、回合判斷、資料庫分工、RAG 邊界與非同步生成，並標示已實作／部分完成／待接入。

## 1. 遊戲情境與目標

玩家暫從鳴霖的平衡議會進入遊戲，遇見維達利亞。命脈之泉長久沒有向外延伸，林地與符石出現異象。玩家走近人物交談、到現場調查，根據線索選擇前往烈燚原或流塵谷，再帶著實際結果回報。開場不直接告知玩家所有世界真相。

目標玩法是維持世界觀、角色核心人格與能力限制，讓反應、事件、任務及通往結局的過程隨玩家選擇發展：**生成器提出可能發生的事，程式判定哪些成立，資料庫保存結果，下一回合承接。** 目前主要調查節點仍預先定義，尚未達到完整自由生成故事的目標。

| 角色 | 設定方向與目前出場情況 |
| --- | --- |
| 維達利亞 | 鳴霖精靈領袖與議會調解人，守護泉眼、引導調查並接收回報。2D、3D 均可互動。 |
| 安德烈 | 鳴霖邊界調查官的公開原型設定；2D 有人物及異象／路線選項，3D 尚未加入獨立互動角色。 |
| 門梅司文托 | 流塵谷的名字／記憶記錄者，2D、3D 均有出場。深層動機與真相需按條件揭露。 |
| 維塔、火焰長老及其他勢力 | 已有世界設定或規則草案；維塔另有獨立預覽。尚未形成完整可玩的角色、任務與結局流程。 |

三位已登記 NPC 的初始 `private_profile` 目前都是空的，完整人格、語氣、能力及秘密權限卡尚未匯入。公開職稱與幾句回覆不能代替正式角色設定。

<details>
<summary>作者層世界設定與五種預定結局（含劇透，並非開場玩家已知資訊）</summary>

這是真實存在的封閉空間，由維塔的意識維持，不是醒來便消失的虛幻世界。設定包含精靈不死、人族輪迴、木乃伊復活，以及人與木乃伊透過埋葬／聖火轉化的關係。主角來自外部組織，身分與用途需逐步揭露。世界發生的事，不等於每位 NPC 都知道。

| 預定結局 | 設定結果 |
| --- | --- |
| 長眠 | 維塔繼續沉睡，既有規則與輪迴延續。 |
| 醒來 | 結界破裂，世界仍存在，居民只剩一條命。 |
| 篡夢 | 長老或外部組織奪走維塔力量。 |
| 新夢 | 主角協助維塔重新創造，世界持續擴展。 |
| 塵歸 | 主角抹除自己，入侵停止，世界恢復平靜。 |

五種結局已有設計與 C 的規則模組，尚未接成目前 API 的完整遊戲流程。使用者已確認「主角死亡即遊戲結束」；舊 C 模組仍有死後轉化邏輯，需協調修正後再整合。正式開場、完整知識卡與部分數值門檻仍待確認。

</details>

## 2. 現在怎麼玩

| 入口 | 用途 |
| --- | --- |
| <http://localhost:3200/experiments/babylon> | 主要驗收入口：Babylon.js 第一人稱 3D 探索、手記與世界指令。 |
| <http://localhost:3200> | 沿用朋友的 Phaser 2D 版本，有 NPC 對話、文字／瀏覽器語音輸入及背景切換。 |
| <http://localhost:3200/preview/veta> | 維塔獨立美術與配樂預覽，未接成主遊戲章節。 |
| <http://localhost:8300/docs> | FastAPI 實際 API 與 Schema。 |

| 3D 操作 | 功能 |
| --- | --- |
| WASD／方向鍵、Shift | 自由步行、奔跑；右下方向按鈕也可移動。 |
| 點地面／人物／地標 | 走向點選位置；人物與地標在靠近後互動。 |
| 拖曳／鎖定滑鼠 | 環視；Esc 釋放或關閉面板。 |
| E | 距離人物／地標 3.6 公尺內開啟對話或調查。 |
| M／旅途地圖 | 查看五個地點、預覽、目前位置、解鎖狀態與合法路線；遠處追蹤先走近出發點，再確認旅行。 |
| J／調查紀錄 | 查看有來源的交談記錄與現場調查；回議會可先走近維達利亞再回報。 |
| Tab／世界指令 | 調整當前場景日夜、天氣、地形及物件數量。這是原型場景編輯功能，尚未設定為主角的世界觀能力。 |
| 新旅程 | 建立新 Session；原存檔仍保留於資料庫。 |

一般聊天不保證推進調查；需完成當前調查，選後端發出的合法旅行選項。輸入與當前「對話型」故事選項相同的文字，也可走相同驗證流程；現場調查與旅行請點對應選項，以送出正確行動模式。

場景位置、配置、回合、事件、記憶與調查進度由 SQLite 保存，重整或後端重啟可承接。**連續步行座標／朝向尚未保存**，重載會回到目前場景入口。兩個前端共用瀏覽器 Session 識別與後端契約，但功能尚未完全一致：語音在 2D 頁，J 手記與世界指令在 3D 頁。

## 3. 已完成的場景與故事線

### 場景現況

| 地點／ID | 目前 3D 呈現 | 故事用途與限制 |
| --- | --- | --- |
| 平衡議會 `minglin` | 原版森林配色、圓形祭壇、刻紋、石板路、石柱、水池；手繪樹葉配立體樹幹。 | 維達利亞接見、出發調查與回報。 |
| 命脈之泉 `minglin_life_spring` | 泉池、反射水面、薄霧、林地與環境 GLB。 | 灰燼／裂響兩種方向；主要泉池固定保留。地點已登記，完整細節仍待確認。 |
| 符石林 `minglin_rune_grove` | 黃昏林地、中央符石、周圍符石與樹木。 | 灼熱符痕／風沙方向；中央符石固定保留。具體內容標記為暫定。 |
| 流塵谷 `liuchen_valley` | 沙土、裂谷、沙塵、門梅司文托與環境物件。 | 記名／埋葬調查；不是參考圖中所有建築與生物的完整立體重建。 |
| 烈燚原 `lieyi_plains` | 岩地、玄武岩材質、動畫聖火、熔流及祭壇。 | 聖火／長老行蹤調查；聖火底座固定保留。具體內容標記為暫定。 |

五地都有版本化背景與配樂。2D 切換完整插畫，3D 使用可行走地形、天空及物件。3D NPC 仍是肖像 billboard，尚無完整人物背面、骨架與行走動畫。Phaser 只有鳴霖、流塵谷兩份 Tiled 地圖，其餘三地仍沿用鳴霖的可走區域。

### 可玩的調查分支

```mermaid
flowchart TD
    A[平衡議會：遇見維達利亞] --> B[命脈之泉]
    A --> C[符石林]
    B -->|追查水面的灰燼| D[解鎖烈燚原]
    C -->|解讀灼熱符痕| D
    B -->|聆聽泉底裂響| E[解鎖流塵谷]
    C -->|辨認風沙路徑| E
    D --> F[觀察聖火輪迴 或 調查長老的行蹤]
    E --> G[記下被遺忘者的名字 或 追查埋葬與復生]
    F --> H[返回議會：手記與實際回報]
    G --> H
    H --> I[本條 Demo 完成：可探索另一條路線]
```

不同選擇會保存不同線索、開放不同路線、顯示不同調查標記。回報時維達利亞只整理實際建立的公開紀錄；私下調查不直接變成她的記憶，需透過回報事件得知。「下一章待續」是目前內容邊界，未連到正式第二幕或五結局。

### 哪些部分現在真的會生成

| 部分 | 實際方式 |
| --- | --- |
| 主要調查故事 | `demo_story.py` 預先定義分支、條件與回覆，依狀態選擇；不是 LLM 即興創作。 |
| 一般 NPC 互動 | 預設 `RuleBasedStoryPlanner` 按關鍵字、回合、記憶、承諾與任務組合回覆／提案；可處理觀察任務、承諾、實際持有物品的交付等。 |
| 外部敘事模型 | 自訂 HTTP／OpenAI 相容 adapter 已有；B 的 URL、模型及正式 RAG 未就緒，執行模式為 `rule_based`。即使設定模型，既有 Demo 選項仍走導演流程，不會自動變成全程自由創作。 |
| 3D 配置 | 後端由保存的 seed、日夜、天氣、地形與數量組合配置，合法修改後才保存。 |
| 3D 新幾何 | 校內 GPU 的 Hunyuan3D-2mini turbo 由三種固定參考圖產出樹木／符石／祭壇 GLB，逐件載入；不是任意文字生成完整世界。 |
| 2D 場景插畫 | 使用四張已生成的地點插畫與既有森林圖。ImageGateway 與工作保存已有，但未接正式即時圖片 provider，不會每回合重新生圖。 |

世界指令如 `生成 6 個符石，變成夜晚並起霧`。上限為 48 棵樹、12 個符石、3 座祭壇；支援白天／黃昏／夜晚、晴朗／薄霧／雨／沙塵、丘陵／沙丘／岩地。超量或不支援的內容不消耗回合；單純日夜／天氣不重生幾何。核心地標保留版本化模型，新 GLB 尺寸或載入失敗時保留既有模型，套用成功才計為已載入。

Hunyuan 目前生成形狀並使用參考圖投影貼圖，尚未載入 Hunyuan Paint，側面、背面與美術品質仍有限。來源、prompts 與版本見 [場景插畫](docs/SCENE_ASSET_PROMPTS.md)、[3D 資產](docs/3D_ASSET_PROMPTS.md)、[場景 manifest](frontend/public/game/scenes/manifest.json)、[模型 manifest](frontend/public/game/models/manifest.json)。

## 4. 整體程式架構

### 資料夾地圖

```text
rag-npc-game/
├── backend/                         FastAPI 與權威遊戲邏輯
│   ├── main.py                      啟動、遷移、服務組裝、CORS
│   ├── api/                         HTTP：遊戲、角色、能力、健康、3D 工作／下載
│   ├── orchestration/               回合協調、選項、Demo 導演、世界指令解析
│   ├── content/                     角色／地點、配置、線索、揭露規則、授權背景查詢
│   ├── schemas/                     Pydantic：行動、提案、操作、狀態、記憶、玩家投影
│   ├── generation/                  規則 planner、模型 adapter、2D／3D 工作處理
│   ├── modules/                     現行 ProposalResolver 與待整合的 C 引擎
│   ├── rules/                       C 的固定事件、數值、階段與結局規則草案
│   ├── database/                    SQLAlchemy 表、Session、repository、交易、遷移入口
│   └── prompts/                     解析／結局模板，未接成現行完整主流程
├── frontend/                        Next.js、React、Phaser、Babylon.js
│   ├── app/
│   │   ├── page.tsx                 /：2D UI、對話、瀏覽器語音與回合送出
│   │   ├── layout.tsx               共用頁面殼與全域樣式入口
│   │   ├── globals.css              共用與 2D 介面樣式
│   │   ├── experiments/page.tsx     /experiments 轉到 Babylon 頁
│   │   ├── experiments/babylon/     3D 頁面入口
│   │   └── preview/veta/            維塔預覽、layout 與專用樣式
│   ├── components/
│   │   ├── MinglinGame.tsx          Phaser 人物、移動、Tiled、碰撞與互動
│   │   ├── WorldMap.tsx             2D／3D 共用旅途地圖，顯示後端合法路線
│   │   └── experiments/             3D UI、控制、渲染、森林主景、水材質、尺寸檢查
│   ├── lib/                         共用 API 型別／請求、Session key、配樂與播放 hook
│   └── public/
│       ├── audio/                   場景音樂與維塔配樂
│       ├── images/                  NPC 肖像等靜態圖
│       └── game/                    森林素材、人物去背、旅途地圖、兩份 .tmj
│           ├── scenes/              四張地點插畫與 manifest
│           ├── models/              預設 GLB、manifest、references/ 生成參考圖
│           └── materials/           沙土、玄武岩等材質
├── infra/hunyuan3d/                  GPU Dockerfile、Compose、生成 API、容器依賴
├── migrations/                      Alembic env.py、模板與 versions/ 七次遷移
├── scripts/                         離線更新預設 GLB 與 manifest 的腳本
├── tests/                           後端契約、交易、規則、adapter、失敗回復測試
│   └── frontend/                    第一人稱操作與模型尺寸的 Node 測試
├── docs/                            世界設計、契約、交接、素材來源、部署與進度
│   └── qa/                          分階段瀏覽器截圖與驗收步驟
├── data/                            本機 game.db、generated_assets/；不提交執行資料
├── requirements.txt                 後端依賴；requirements-dev.txt 為測試依賴
├── alembic.ini                      資料庫遷移設定
└── .python-version                  Python 版本；前端依賴在 frontend/package*.json
```

`.venv/`、`frontend/node_modules/`、`frontend/.next/` 與快取是本機環境／建置產物。金鑰放被忽略的本機 `.env`，不放程式或文件；後端目前不自動載入根目錄 `.env`，啟動時需將變數帶入程序。前端設定檔為 `frontend/.env.local`。

### 一個回合從哪裡經過

```mermaid
flowchart TD
    UI[2D 或 3D 介面] --> API[api/game.py：start / turn / state / choices]
    API --> O[GameOrchestrator：去重、版本、選擇路徑]
    O --> D[Demo 選項：demo_story_director]
    O --> P[一般互動：規則或外部 StoryPlanner]
    O --> W[世界指令：world_commands]
    D --> S[StoryProposal：尚未成立的提案]
    P --> S
    W --> S
    S --> R[ProposalResolver：驗證與計算]
    R --> DB[commit_turn：同交易保存狀態、事件、對話、記憶、去重結果]
    DB --> V[PlayerViewState：玩家可見投影]
    V --> UI
```

三條提案路徑共用規則與交易邊界。`/start` 建立／恢復 Session；每個新行動有 `action_id`，不確定成功時保留原 ID 重送。相同 ID／內容重播原結果；同 ID 換內容或過期 `expected_state_version` 回傳 409，不重複增加回合或物品。

模型呼叫在提交交易前完成；客觀結果來自核准操作與系統敘事。NPC 發言不能直接增加背包或改寫設定，接真實模型後仍需測試台詞是否聲稱了未核准結果。

**3D 生成是另一條非同步管線：** Tab 指令 → 回合驗證並保存配置 → `/scene-assets` 建立／回用工作 → `SceneAssetCoordinator` → SSH tunnel → GPU Docker `/generate` → GLB 驗證與保存 → 前端輪詢 → Babylon 尺寸檢查後替換裝飾。

工作狀態存在資料庫，GLB 在 `data/generated_assets/`，最多嘗試兩次，重啟可恢復。瀏覽器只向遊戲 FastAPI 取模型，不直接連 GPU。GPU 只在遠端 loopback 發布埠；新幾何生成需要校內 VPN 與 SSH tunnel，未連 GPU 仍可用預設模型探索。

### 要改哪種邏輯，就看哪個檔案

下列位置均相對於專案根目錄。

| 要改的事情 | 邏輯位置與責任 |
| --- | --- |
| Demo 分支、條件、台詞與線索 | `backend/content/demo_story.py` 定義內容；`backend/orchestration/demo_story_director.py` 轉提案，不在前端按鈕裡改狀態。 |
| 選項、NPC 詢問與下一步 | `backend/orchestration/player_choices.py`；`backend/schemas/player_view.py` 將公開路線投影給地圖。 |
| 地名、ID、合法出口、地圖座標 | `backend/content/scenes.py` 是單一 Scene Registry。 |
| 物件分布、出生／互動點、核心地標 | `backend/content/world_scenes.py`；可調欄位／上限在 `backend/schemas/world_scene.py`。 |
| 世界指令句型 | `backend/orchestration/world_commands.py` 只提出受限配置操作。 |
| 3D UI、送回合、工作輪詢 | `frontend/components/experiments/TrialExperience.tsx`；按鍵／點擊步行在同目錄 `first-person.ts`。 |
| 地形、光照、模型載入、碰撞 | `frontend/components/experiments/babylon-driver.ts`；`world.ts` 共用高度與 driver 契約，`asset-layout.ts` 檢查模型尺寸。 |
| 原版森林祭壇、路、水池、樹葉 | `frontend/components/experiments/forest-sanctuary.ts`；`sanctuary-layout.ts` 共用水池範圍，`water-material.ts` 共用水材質；樣式在 `TrialExperience.module.css`。 |
| 手記、回報、防劇透 | `backend/content/story_findings.py` 推導紀錄，`reveal_policy.py` 控制公開用語；前端 `InvestigationJournal.tsx` 呈現。 |
| 角色與知識權限 | `backend/content/characters.py`、`backend/schemas/content.py`、`backend/content/context_repository.py`；依 NPC、Session、解鎖及回合過濾。 |
| B 的模型、背景組合、逾時重試 | `backend/generation/config.py` 組裝，`gateway.py` 定義契約，`planner.py` 整理授權背景；`http_gateway.py`／`openai_compatible_gateway.py` 呼叫服務。 |
| 合法事件、所有權、承諾、任務、換場 | `backend/modules/proposal_resolver.py`；操作格式在 `backend/schemas/story.py`。 |
| 回合協調與執行分流 | `backend/orchestration/game_orchestrator.py`，目前解析仍是簡化版本，尚未完整接 C 的 InputEngine。 |
| Session、交易、事件、對話、目擊記憶、去重 | `backend/database/repository.py`；資料表在 `models.py`，連線在 `session.py`。 |
| C 的數值、危險事件、換幕與結局 | `backend/rules/`，以及 `backend/modules/input_engine.py`、`action_validator.py`、`state_manager.py`、`ending_engine.py`。已有模組，**現行 GameOrchestrator 未呼叫這套完整流程**。 |
| 3D 工作與 GPU 服務 | `backend/generation/scene_assets.py` 處理 job／GLB；`infra/hunyuan3d/server.py` 執行 Hunyuan；`scripts/generate_scene_models.py` 更新離線資產。 |
| 2D 圖片工作 | `backend/generation/image_gateway.py` 定義介面，`scene_image_jobs.py` 處理保存、工作與 fallback；尚無正式 provider 注入。 |
| 2D 人物、移動、語音／對話 | `frontend/components/MinglinGame.tsx`、`frontend/app/page.tsx`；`.tmj` 的 Actors／Walkable 圖層定義角色點與可走區域。 |
| 共用 API／Session、配樂 | `frontend/lib/game-api.ts`；`scene-music.ts`、`use-scene-music.ts`。 |

### 資料實際保存在哪裡

| 類別 | 程式／資料表 |
| --- | --- |
| 不可由普通生成改寫的設定 | `world_canon`、`character_definitions`。已有格式與表，不代表完整原始設定已匯入；初始公開角色在 `content/characters.py`。 |
| 可變世界狀態 | `game_sessions.state_json` 保存 `GameState`：背包、所在場景、故事進度、場景配置；版本供併發檢查。 |
| 事件、對話、請求紀錄 | `game_events`、`dialogue_records`；`action_records` 保存摘要、結果與私有提案核准／拒絕稽核。 |
| NPC 知識與記憶 | `knowledge_records`、`memory_records` 含角色、來源與時間；目擊或回報後建立對應記憶。 |
| 目標、承諾、任務 | `npc_goals`、`commitments`、`quests` 有來源、期限與狀態；已有資料與背景查詢，尚非完整自主世界模擬。 |
| 圖片／模型工作 | `scene_image_jobs`、`scene_asset_jobs`；GLB 檔另存本機執行目錄。 |

玩家 API 的 `PlayerViewState` 不含 NPC 私人記憶、關係數值、隱藏旗標或作者真相。前端不能直接讀寫資料表或任意 patch `GameState`。世界設計 Markdown 也尚未自動轉成授權 RAG 資料。

## 5. 尚缺工作與交接責任

| 優先 | 尚缺工作 | 負責方／需要提供的資料 |
| --- | --- | --- |
| 1 | 真正敘事生成與 RAG：匯入來源、按權限檢索，驗證人格及跨回合一致性；讓生成事件接續故事，而非只換聊天台詞。 | B／D：URL、模型名稱、請求回應範例、RAG 格式及授權條件；見 [B 交接](docs/B_AI_RAG_HANDOFF.md)、[模型契約](docs/MODEL_GATEWAY_CONTRACT.md)。 |
| 2 | 正式第二／三幕、真相 A／B／C、危險事件、死亡即結束與五結局；協調數值門檻及 Demo 銜接。 | C／D／A：事件／效果契約、觸發與揭露條件，先修正舊死後轉化邏輯。 |
| 3 | 完整人物與世界資料：人格、語氣、能力、初始知識、秘密、揭露時機、各地角色與配置。 | 作者／B／C：補角色卡與來源；確認符石林、烈燚原暫定內容。 |
| 4 | 正式 NPC GLB／動畫、獨立建築與碰撞、安德烈 3D 出場、另外三張 Phaser 地圖及 2D／3D 功能對齊。 | A／D／美術：模型、材質、場景配置及互動點；目前三類 Hunyuan 物件不足以代表完整場景美術。 |
| 5 | 即時 2D 插畫 provider、預算與生成策略，目前只有介面、工作保存、輪詢與 fallback。 | D／B：選定服務或校內部署及可驗收的介面。 |
| 6 | NPC 自主行動循環、任務完整生命週期、連續座標存檔；多人部署的外部 worker／工作租約。 | D／B／C：定義觸發與測試；現行 3D worker 以單一 FastAPI 程序為前提。 |
| 7 | 3D 語音 UI、外部 STT／TTS、目標瀏覽器／投影／手機實機驗收。 | A／D／B；目前 2D 使用瀏覽器語音能力，文字輸入持續保留。 |

目前沒有把整份作者秘密塞進每位 NPC 的 prompt，也不會因為寫好設定 Markdown 就自動完成章節。下一個生成驗收單位應是：一個能跨數回合承接、通過規則及知識邊界、可回放的新事件。

## 6. 本機啟動與設定

需要 Python 3.12、Node.js 20.9+。以下依賴裝在本機專案環境；GPU 主機依賴一律放 Docker，不直接在主機執行 apt／pip／npm 安裝。

後端（專案根目錄）：

```bash
python3.12 -m venv .venv
./.venv/bin/pip install -r requirements.txt
./.venv/bin/uvicorn backend.main:app --reload --port 8300
```

前端（另一個終端）：

```bash
cd frontend
npm ci
npm run dev
```

production 展示：`npm run build` 後執行 `npm run start`，仍在 3200；不要同時啟動 dev 與 start 占同一埠。前端預設連 8300；要改位置，將 `frontend/.env.example` 複製為 `.env.local`，設定 `NEXT_PUBLIC_API_URL`。

後端啟動會執行 Alembic 遷移，預設 SQLite 為 `data/game.db`；可用 `DATABASE_URL` 改位置。手動遷移：`./.venv/bin/alembic upgrade head`。不要提交本機資料庫。

### 啟用已部署的校內 Hunyuan

連校內 VPN，使用本機已設定的 SSH alias 開 tunnel：

```bash
ssh -N -L 127.0.0.1:8081:127.0.0.1:8081 nccu-gpu
curl http://127.0.0.1:8081/health
```

health 為 `ready` 後，後端改用：

```bash
HUNYUAN3D_URL=http://127.0.0.1:8081 ./.venv/bin/uvicorn backend.main:app --port 8300
```

SSH alias 與存取權需各自設定，倉庫不保存帳密或私鑰。部署見 [GPU 設定](docs/HUNYUAN3D_GPU_SETUP.md)。GPU 未就緒可省略 `HUNYUAN3D_URL`，用預設 GLB 探索。

### 接 B 的敘事模型

目前尚無正式端點，以下只表示設定介面，值由 B 提供，不代表已接通：

```bash
export MODEL_GATEWAY_PROVIDER=openai_compatible
export MODEL_GATEWAY_URL='<B 的 OpenAI 相容服務基底 URL>'
export MODEL_GATEWAY_MODEL='<B 提供的模型名稱>'
# 若需要金鑰，以本機安全方式設定 MODEL_GATEWAY_API_KEY，勿提交。
./.venv/bin/uvicorn backend.main:app --reload --port 8300
```

也支援 `contract_http` 自訂契約；URL 未設定採規則 planner，錯誤端點不會當成生成成功。預設呼叫逾時 15 秒、最多兩次嘗試；見 [MODEL_GATEWAY_CONTRACT](docs/MODEL_GATEWAY_CONTRACT.md)。

## 7. API 與驗收

| API | 用途 |
| --- | --- |
| `GET /health`、`GET /api/capabilities` | 健康與生成模式；RAG／外部語音 pending 不代表 2D 瀏覽器語音不存在。 |
| `GET /api/characters/{npc_id}` | 已登記角色公開資料。 |
| `POST /api/game/start` | 建立／恢復 Session。 |
| `POST /api/game/turn` | 提交 action_id、預期版本與行動模式。 |
| `GET /api/game/{session_id}/state` | 公開狀態、場景、手記、地圖及下一步。 |
| `GET /api/game/{session_id}/choices` | 情境選項；npc_id 可為 vidalia／andre／menmesvento。 |
| `GET /api/game/{session_id}/quests` | 玩家可見的未結束任務。 |
| `POST /api/game/{session_id}/scene-image`、`GET .../scene-image/{job_id}` | 2D 圖片工作；未設定 provider 使用版本化場景。 |
| `POST /api/game/{session_id}/scene-assets`、`GET .../scene-assets/{job_id}` | 3D 工作建立、輪詢；POST 要帶 expected_state_version。 |
| `GET /api/game/{session_id}/scene-assets/{job_id}/model` | 取得該 Session 成功工作的 GLB。 |

最近一次功能驗收（2026-11-12）：**123 個後端測試、11 個前端測試、Next.js production build 通過**。Chrome 實走兩條分支與不同回報、重整承接、地標保護、新 Hunyuan GLB、下載失敗保留場景及恢復。這不替代尚未接入的正式 LLM、結局或完整美術驗收。

```bash
# 專案根目錄：後端與前端邏輯測試
./.venv/bin/pip install -r requirements-dev.txt
PYTHONPATH=. ./.venv/bin/pytest -q
node --experimental-strip-types --test tests/frontend/*.test.ts

# 前端 production build
cd frontend
npm run build
```

Node 控制測試需使用支援 `--experimental-strip-types` 的版本；Next.js 最低 Node 版本不等於支援此測試旗標。

| 文件／證據 | 內容 |
| --- | --- |
| [最新故事與生成場景 QA](docs/qa/story-consequences/README.md) | 火焰／風沙手記、回報、固定泉眼、新 GLB 與失敗回復。 |
| [地圖 QA](docs/qa/world-map/README.md)、[森林 QA](docs/qa/forest-sanctuary/README.md) | 路線、承接、原版主景與操作。 |
| [音樂資產](docs/AUDIO_ASSETS.md) | 曲目、來源、授權、雜湊。 |
| [B AI／RAG 交接](docs/B_AI_RAG_HANDOFF.md) | 模型、資料、檢索與驗收交付。 |
| [A／D Demo 交接](docs/DEMO_HANDOFF.md) | 展示、環境、限制、下一位接手事項。 |

A 負責前端、遊戲畫面與語音；B 負責模型與 RAG；C 負責行為解析、規則與結局；D 負責 API、Session、資料庫、Orchestrator、記憶及整合。共用 Schema 由 D 整合；涉及設定或 C 的規則先協調，不在前端另寫一套權威邏輯。
