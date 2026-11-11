# A／D 整合進度

## 2026-11-11 明日 Demo 發行整合

- 從 GitHub 最新 `main` 建立 `release/demo-2026-11-12`，合併 NPC 路線／音樂／世界地圖、揭露安全修正、動態故事穩定修正與 Hunyuan3D gateway。
- 解決 README、進度文件、Babylon 音樂／穩定視圖與故事測試衝突；保留新功能，同時避免恢復已移除的固定符石任務與錯誤幾何。
- 瀏覽器實際驗收首頁四個起始選項、規則動態回合、Babylon 接近維達利亞、符石林換場、流塵谷分支及重新整理承接。
- 視覺驗收發現符石林仍疊加不合透視的錐形樹／方柱後，已停用所有非議會場景的共用 primitive props；正式 GLB 可在完成資產 job、材質與 transform 驗收後逐場加入。
- 驗證：後端 106 個測試通過；Next.js 16.4.4 production build 通過；本機 production Chrome 無阻斷性 JavaScript 錯誤。

## 2026-11-11 開場揭露順序修正

- 依劇情草案 v3，第一階段只呈現可觀察的泉水與異象線索；真相 A 最早在第二階段，真相 B／C 在第三階段依條件揭露。
- 第一階段的符石調查只解鎖流塵谷路徑線索；正式「裂隙地圖」留給 E2-3。舊 Demo 存檔中由符石調查提早取得的地圖旗標，讀取時會移除。
- 符石林進入流塵谷的選項、行動和旁白改為「風沙路標／方向」；舊回合重送及瀏覽器舊對話紀錄也同步改寫。
- 修正 Demo 中過早說出第一次入侵、主角與維塔的連結、長老奪權目的及主角可返回外界的台詞與公開線索 ID。
- 舊 Session 的公開線索與章節名稱在玩家 API、圖片 prompt 中轉為不劇透版本；已保存回合重送與首頁瀏覽器舊對話紀錄也套用相同修正。
- 使用者已決定「死亡即遊戲結束」；C 的危險事件及 A／D 的結束狀態尚未接入，不能把死亡後轉化草案當成現行玩法。
- 驗證：後端 102 個測試通過（揭露流程測試也可單獨執行），前端 TypeScript 檢查通過。正式真相 A／B／C 事件、NPC 知識授權與外部模型一致性驗證仍待 B／C 整合。

整體里程碑：`█████████▌ 95%`（M0～M2c、M4、A2～A3 完成；M3 真實服務、A1 實機語音與 A4 3D 資產管線待驗收）

週四動態故事 Demo：`██████████ 100%`（D0～D3 完成；D4 使用版本化 fallback；D5 實際點選、換場與重整承接通過，可供明日展示）

| 階段 | 狀態 | 可驗收成果 |
| --- | --- | --- |
| M0：設計與契約 | `██████████ 100%` | 四類資料邊界、回合流程、A／B／C／D 責任與整合缺口已盤點 |
| M1：基本串接 | `██████████ 100%` | 既有前端可建立 Session、送文字、顯示開發替身回覆並讀取正確回合狀態 |
| M2a：保存與結果處理 | `██████████ 100%` | SQLite、migration、完整回合交易、跨重啟去重與版本衝突已完成 |
| M2b：內容與知識隔離 | `██████████ 100%` | 世界／角色內容結構、NPC 記憶來源、授權後生成背景與 PlayerViewState 已完成 |
| M2c：核准事件介面 | `██████████ 100%` | 初始操作白名單、事件原子核准、私有決策稽核與同交易保存已完成 |
| M3：真正生成 | `█████████░ 90%` | Gateway、動態台詞、安全回復已完成；待 B 的真實端點、RAG 與角色品質驗收 |
| M3a：規則動態故事 | `██████████ 100%` | 無模型也能依輸入、回合、記憶、承諾、任務與背包產生並保存不同結果 |
| M4：世界持續發展 | `██████████ 100%` | 有來源的 NPC 目標、承諾、回合時鐘、記憶承接與動態任務已完成 |
| A1：瀏覽器語音互動 | `█████████░ 90%` | STT transcript 與瀏覽器 TTS 已完成；待實機麥克風中文辨識驗收 |
| A2：圖片／場景生成 | `██████████ 100%` | 四張版本化生成場景、單一 Registry、合法換場、2D／3D 顯示、保存與重啟承接均已完成 |
| A3：情境選項介面 | `██████████ 100%` | 後端依 Session 產生最多四個對話／移動選項，前端點選後提交正式回合並隨狀態更新 |
| A4：Hunyuan3D 資產管線 | `████████░░ 80%` | 私有 shape-only GPU API 與真實 GLB 驗收完成；待後端持久化 asset job、Babylon loader 與材質／畫面驗收 |

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
- 新增 OpenAI 相容 Chat Completions adapter，可用環境變數選擇模型，支援 strict JSON schema 與 JSON object fallback；原本 B 的自訂契約 adapter 繼續保留。
- 模型 system prompt 明確隔離玩家指令、未授權秘密、缺失核心設定與尚未核准的客觀結果。
- 模型可生成目標 NPC 的主觀台詞與事件提案；後端固定說話者身分，客觀效果仍只用核准事件的確定性系統敘事。
- 新增 `/api/capabilities`，前端會明確顯示「規則動態」或「AI 動態」。
- B 的完整 HTTP 契約記錄於 `docs/MODEL_GATEWAY_CONTRACT.md`。

## M3 目前驗收

- `PYTHONPATH=. ./.venv/bin/pytest -q`：97 passed（目前全套；含 M4、語音、OpenAI 相容 adapter、規則動態、場景切換、權威故事選項、舊 Session 相容與兩條 Demo 分支回歸測試）。
- 格式錯誤可有限修正，timeout 達上限後停止，永久設定錯誤不重試。
- fake Gateway 的動態台詞已通過完整 API 流程，玩家端不再顯示開發替身。
- 外部模型失敗的 503、Retry-After、狀態不推進均有自動化測試。
- HTTP 408／429／5xx 與 4xx 分類、Bearer header、授權 context payload 均有測試。
- OpenAI 相容 `/v1/chat/completions` request、模型名稱、Bearer token、回應解包、strict schema、JSON fallback、拒絕、截斷及 content filter 均有自動化測試。
- `npm run build`：Next.js、TypeScript 與全部既有 routes 通過 production build。
- 尚未使用 B 的真實服務做延遲、角色一致性、RAG 召回與多回合品質驗收，因此 M3 不記為 100%。

## M3a 規則動態故事

- 未設定外部模型時，預設使用 `RuleBasedStoryPlanner`，不再顯示固定的開發替身句子。
- 招呼會依初次／再次互動及已保存記憶改變。
- 詢問任務時可提出一項只引用目前公開場景的觀察任務；同一 open quest 不會重複建立。
- 玩家明確承諾時可建立有來源的 Commitment；提及交付物品時會先核對實際背包。
- 詢問先前對話時只承接該 NPC 的玩家互動記憶，不把 observed-event 私人內容直接洩漏。
- 規則只產生 `StoryProposal`；任務、承諾與物品仍通過既有 resolver，與回合、事件及記憶同交易保存。
- 前端 badge 顯示「規則動態」；只有設定並使用外部 ModelGateway 時才顯示「AI 動態」。
- 新增玩家選項 API；初始提供所在地、委託及兩個合法目的地，任務建立後改為任務追問、承諾回報及合法目的地。
- 選項只包裝一般 `PlayerAction`，仍使用 `action_id`、`state_version`、resolver 與完整回合交易；自由文字輸入不受限制。
- 新增有狀態的 Demo Story Director；玩家可由命脈之泉線索解鎖烈燚原，或由符石林辨認風沙路徑後解鎖流塵谷，兩條分支會保存不同公開線索與下一組選項。正式裂隙地圖仍留待 E2-3。
- `story_choice_id` 只接受當前節點可用的權威選項；竄改文字、目的地或模式會回傳 409，避免只靠前端隱藏選項。
- 舊 Session 可能已有任務與位置、但尚無 Demo 節點；其舊版對話／旅行選項會先與後端當下發出的完整 action 比對，再走既有規則流程，不會被誤判成過期 Demo 選項。
- 新增 `advance_story` 白名單操作；推進節點、揭露公開線索、解鎖特殊場景、換場、事件及對話沿用單一交易，後續操作失敗時不留下半個故事節點。

## M3a 驗收

- `PYTHONPATH=. ./.venv/bin/pytest -q`：97 passed。
- 單元測試涵蓋回合化招呼、記憶承接、秘密隔離、任務去重、承諾及物品持有權提案。
- API 端到端測試證明規則任務會保存，下一回合承接且不重複新增。
- Choices API 測試涵蓋初始選項、任務後選項更新及不存在 Session 的 404；前端 TypeScript production build 通過。
- Live HTTP 驗收：`/api/capabilities` 回報 `rule_based`，前端 `/` 與 `/experiments/babylon` 均回 200；第一回合建立任務、第二回合承接，任務總數維持 1。
- 瀏覽器控制主機目前不可用，未完成自動化畫面點擊；production build 與實際服務 HTTP 已通過。

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

## A2 圖片／場景生成與切換

- 使用 OpenAI 內建圖片生成工具製作命脈之泉與符石林兩張 1672×941 場景圖；工具未揭露底層模型名稱，因此只記錄實際工具，不猜測型號。
- 依使用者提供的流塵谷參考設計新增 1672×941 場景圖；保留峽谷、龜裂道路、風沙柱、墓葬遺跡、枯木與遠景木乃伊，並避開大型前景角色以利遊戲疊加。
- 依使用者提供的烈燚原參考設計新增 1672×941 場景圖；保留中央火柱祭壇、熔流、玄武岩峽壁與橙色樹林，移除參考圖人物並保留前景可行走路徑。
- 生成提示摘要、版本、尺寸、SHA-256、風格參考及 provisional 狀態保存在 `frontend/public/game/scenes/manifest.json`；舊資產未被覆蓋。
- 圖片採建置期生成與版本化提交；遊戲每回合只引用已存在資產，不重複呼叫圖片模型。
- 新增 provider-neutral `ImageGateway` 與 `scene_image_jobs` migration；圖片工作只在已提交狀態之後建立，不在遊戲回合交易中等待模型。
- 圖片 prompt fingerprint 只使用公開場景、公開章節、公開線索與固定 style version；不讀取 NPC 私人記憶或隱藏設定，相同內容會回用既有 job。
- 2D／3D 前端以非重疊 polling 追蹤工作；舊場景的晚到結果不能覆蓋目前場景，成功時套用生成 URL，未設定／失敗時保留版本化 fallback。
- 新增單一 Scene Registry，同時供後端合法路線驗證、PlayerViewState、Phaser 2D 完整背景及 Babylon 3D 遠景使用，沒有前後端各維護一份場景表。
- 新增 `change_scene` 白名單操作；只有玩家、已登記目的地與 Scene Registry 允許的出口可以成立，不可直達或不存在場景會原子拒絕。
- `destination_scene_id` 納入 action digest；場景狀態、成立事件、對話與版本以同一交易保存，後端重啟後仍可承接。
- 流塵谷地名由 C 的 E3-1 規則確認，但不列入普通場景出口；待 C 的危險事件操作整合後，才依「持有裂隙地圖」條件進入。
- 烈燚原名稱與視覺來自使用者參考，但現有 C 規則沒有對應事件或路線；目前以 provisional 場景登記，且不列入任何普通場景出口。
- 玩家選項建構已從 Orchestrator 抽離；共用前端 API 型別與請求函式，避免在 2D／3D 頁重複定義契約。
- 3D 頁收到成功回合後會立即套用場景，不再讓後續 choices 更新失敗阻擋已成立的移動結果。
- Scene Registry 現在同時提供霧光、色盤、可見物件群，以及議會角色／符石／地面可見性；Babylon 依 API 套用，不在前端另維護一份場景表。
- 完整場景插畫已包含天空、地面與透視，因此 Babylon 不再疊加另一套水平地板、柱子、泉、符石或議會道路；目前只保留維達利亞 cutout 與故事互動，避免兩套地平線與光源互相衝突。
- 固定「尋找命脈符石」前端假任務已移除；議會流程改成接近維達利亞後直接顯示後端依 Session 與故事節點提供的選項。
- Babylon 遠景由四張互相交叉的平面改為單一 screen-space layer，消除側面平面穿入鏡頭所形成的巨大三角遮蔽。
- 非議會場景直接顯示當前章節、後端提供的規則選項及已成立公開線索，不必返回不存在於當地的維達利亞互動點。
- 共用 Session 發生 `STATE_VERSION_CONFLICT` 時，3D 頁會自動重新取得最新狀態與選項，再提示玩家重試原行動。
- Babylon 遠景載入會區分已啟用與載入中的 URL；失敗時保留舊遠景、顯示明確訊息，解除故障後可重試同一張圖。

## A2 驗收

- `PYTHONPATH=. ./.venv/bin/pytest -q`：97 passed；涵蓋資產／Registry 完整性、合法換場、特殊路線、舊 Session 返回路線、Scene Profile、圖片 job 去重、成功、timeout fallback、Session 隔離、migration 與跨 app 重啟承接。
- `npm run build`：Next.js 16.4.4、TypeScript、`/` 與 `/experiments/babylon` production build 通過。
- Live Demo：火焰與風沙兩條分支均到達特殊場景；Headless Chrome 以 1600×913 WebGL 載入烈燚原／流塵谷，hard refresh 保持位置，無 JavaScript exception。
- 3D live 驗收發現動態遠景 Y 軸方向不一致，已修正並重新截圖確認遠景正向。
- 後續實機畫面發現流塵谷仍載入議會原型及交叉遠景牆；修正後以獨立 Headless Chrome／SwiftShader 對流塵谷與烈燚原重新截圖，兩者皆無遮蔽、無議會角色或假地形，且顯示不同章節與選項。
- Live HTTP：起始場景回傳平衡議會與四個選項；提交「前往命脈之泉」後建立 `change_scene` 成立事件、版本 1→2，重新 GET 仍為命脈之泉。
- Chrome headless＋CDP 實際座標點擊「前往命脈之泉」：turn POST 與 choices GET 均為 200，場景標題及遠景更新、對話面板退出；hard refresh 後仍保留相同 Session 與位置。
- 瀏覽器故障注入驗收：版本衝突 409 後可自動同步並重試成功；choices GET 被封鎖時已成立回合與場景仍會更新；遠景 PNG 被封鎖時顯示錯誤並保留舊景，解除後重新載入成功。

## A4 Hunyuan3D 資產管線

- 新增固定 Hunyuan3D upstream commit 的 CUDA 12.8 Docker image，使用支援 Blackwell 的 PyTorch cu128 wheel。
- 第一版只載入 Hunyuan3D-2mini shape model，不載入 Paint／texture model，也不啟用需額外編譯 CUDA extension 的 FlashVDM。
- 私有 FastAPI gateway 提供 `/live`、`/health` 與 `/generate`；模型在背景初始化，健康狀態可區分 loading、ready 與 error。
- 生成限制為單工，輸入限制為 12 MiB、24 MP 與三種圖片格式；輸出為 GLB，模型未就緒回 503、已有工作回 429。
- Compose 使用 rootless Docker 可用的 NVIDIA CDI，且只發布到遠端 `127.0.0.1:8081`；前端不直接呼叫校機。
- 本機 Python compile、Compose YAML 解析與安全配置測試通過；`PYTHONPATH=. ./.venv/bin/pytest -q` 為 100 passed。
- 校機 RTX 5060 Ti 已完成 image build、持久化 7.2 GB model cache、container recreate 與真實 `/generate` 驗收。
- 正式 API 以既有維達利亞 cutout 在 6.75 秒產出 687,488-byte GLB；後處理結果為 17,222 vertices／40,000 faces、watertight，0 restart、未 OOM。
- 原始 256 mesh 在 18.62 秒產生，峰值 4,571 MiB，但 875,034 faces 且非 watertight；因此 API 強制加入官方浮動面／退化面清理及 face reduction，不把 raw mesh 直接送進 Babylon。
- 本機 SSH tunnel `127.0.0.1:8081` 已取得 `ready`；服務仍只綁遠端 loopback，前端不直接連校機。

## 已知限制

- M1 的 `minglin` 起始場景是為沿用現有可玩前端的暫時整合值，不視為最終世界觀定案。
- 真實 AI、RAG 與外部 STT/TTS 尚未接入；NPC 互動／目擊記憶已由後端依核准結果自動寫入。
- 真實 ModelGateway 端點、模型名稱與認證尚未提供；目前可直接接 B 的自訂契約或 OpenAI 相容服務，預設則使用規則動態。
- 規則動態可承接狀態但不是 LLM 自由創作；角色語氣、未預寫情境與大範圍故事發展仍需真實 ModelGateway／RAG。
- 圖片 job／polling／fallback 已可運作，但部署端尚未注入正式 ImageGateway，因此目前介面會誠實標示「版本化場景」，不是每回合即時呼叫圖片模型。
- 圖片工作目前由 FastAPI background task 執行；Demo 單程序可用，正式多程序部署仍應改為 transactional outbox＋獨立 worker、stale-job recovery 與有限重試。
- Babylon 頁目前是使用完整場景圖、角色 cutout 與狀態式故事 UI 的 2.5D 視覺原型；尚未建立正式 GLB、地形、導航網格或碰撞地圖，介面不再宣稱已完成第一人稱 3D 建模。
- 正式 3D 應使用 Tripo／Meshy 等 image-to-3D 服務產生模組化 GLB，再經 Blender 清理、減面、PBR 與碰撞設定；專案目前沒有 GLB、Blender 或 3D provider API key。
- 零預算方案改以校內 GPU 部署 Hunyuan3D：現有圖片生成工具繼續製作透視一致的完整背景；Hunyuan3D 只負責獨立遺跡、祭壇、樹木等 mesh，不把單張風景圖直接當作已完成遊戲關卡。
- A4 已固定 Hunyuan3D-2mini shape-only、CUDA 12.8、單工生成、面數上限與遠端 loopback 綁定；GPU gateway 已實際驗收，但尚未建立遊戲後端 3D asset job、正式材質或 Babylon GLB 載入，不能標示為已串進遊戲。
- Scene Registry 已登記平衡議會、命脈之泉、符石林、流塵谷與烈燚原；目前只有鳴霖三個場景具普通旅行路線，仍缺完整正式場景清單、在場 NPC、進出條件及 E1／E2／E3 對應。
- 目前已有維達利亞、安德烈與門梅司文托的公開角色原型與前端互動；私有角色設定、正式來源、初始知識與秘密解鎖條件仍待團隊提供。
- 目前白名單為 `transfer_item`、`establish_commitment`、`offer_quest`、`change_scene`、`advance_story`；Demo 公開線索與特殊路線由權威選項推進，關係、任務接受／完成、正式固定事件與結局效果仍需依 C 的正式介面加入。

## 待 B／C 協調

- B：ModelGateway 請求／回應、逾時與錯誤格式，RAG metadata 與權限 filter 介面。
- C：固定事件 ID 與分支 ID 的對應、動態事件操作格式、強制換幕與生成式玩法的兼容方式。
- C：`Truth_C` relation payload、真相保底執行順序、單階段關係增量保存方式。
- 團隊：正式起始場景，以及完整世界觀、角色核心設定、秘密解鎖與知識來源資料。

## 下一步

1. 由 FastAPI 建立持久化 3D asset job，再加入 Babylon GLB loader、transform metadata、材質策略、fallback 與實際瀏覽器驗收；瀏覽器不直接連校機。
2. 由團隊提供祭壇、符石、遺跡、枯木等獨立物件參考圖與場景擺放 metadata；避免把整張風景或單張角色正面直接當正式 3D 關卡。
3. 若 Hunyuan3D 的 mesh 品質或速度不符 Demo，再評估 Tripo／Meshy API；任何付費 provider 必須先取得成本上限與金鑰。
4. 選定正式圖片 provider／模型／金鑰環境變數，實作 ImageGateway adapter、timeout、有限重試與獨立 worker；目前無 provider 時必須保持 fallback。
5. C 確認 Demo fallback 與正式 E3-1／烈燚原入口規則的映射；目前不把暫定選項升格為正式作者設定。
6. B 提供正式文字 provider、URL、模型名稱與認證方式後，完成 M3 live AI 及 RAG 知識邊界驗收。
