# 動態故事 Demo 交接

交接日期：2026-11-10

目標 Demo：2026-11-12（週四）

工作分支：`feature/demo-dynamic-story`
GitHub compare：<https://github.com/sophia112306/rag-npc-game/compare/main...feature/demo-dynamic-story>

## 目前狀態

| 範圍 | 進度 | 狀態 |
| --- | --- | --- |
| 可保存動態故事 | `██████████ 100%` | 兩條狀態式 fallback 分支、選項防偽、事件與位置同交易 |
| Babylon Scene Profile | `██████████ 100%` | 五場景遠景、地面、霧光、色盤與物件群切換 |
| 滾動圖片管線 | `████████░░ 80%` | Job／polling／快取／fallback 完成；正式 provider 尚未接入 |
| Demo 驗收與交接 | `█████████░ 90%` | 自動測試、build、兩條 live API 與 3D 載入通過；待正式彩排 |

目前可以在沒有 B 的模型、RAG 或圖片 API 時完整展示兩條可保存故事分支。介面會顯示「規則動態」及「版本化場景」，不會把 fallback 假稱為 AI 即時生成。

## 立即接手

```bash
cd /Users/qiao/rag-npc-game
git switch feature/demo-dynamic-story
git pull --ff-only origin feature/demo-dynamic-story
```

終端一（後端）：

```bash
cd /Users/qiao/rag-npc-game
./.venv/bin/pip install -r requirements-dev.txt
./.venv/bin/uvicorn backend.main:app --reload --port 8300
```

終端二（前端）：

```bash
cd /Users/qiao/rag-npc-game/frontend
npm ci
npm run dev
```

網址：

- 2D 遊戲：<http://localhost:3200>
- 3D 遊戲：<http://localhost:3200/experiments/babylon>
- FastAPI：<http://localhost:8300/docs>
- Health：<http://localhost:8300/health>

若 3200 顯示 `ERR_CONNECTION_REFUSED`，代表前端終端尚未啟動；若畫面顯示無法連線遊戲服務，檢查 8300 後端。

## Demo 路線

使用右上角重新開始按鈕可建立全新 Session。2D 與 3D 共用瀏覽器 `localStorage` 中的 Session。

### 火焰分支

1. 在平衡議會選「前往命脈之泉」。
2. 選「追查水面的灰燼」。
3. 選「循餘燼前往烈燚原」。
4. 烈燚原會顯示火焰遠景、紅黑地面、火色霧光與祭壇物件群。
5. 選「觀察中央聖火」或「追查火焰長老」。

### 風沙分支

1. 在平衡議會選「前往符石林」。
2. 選「拼合裂隙地圖」。
3. 選「沿裂隙進入流塵谷」。
4. 流塵谷會顯示風沙峽谷、沙色地面、沙霧與遺跡物件群。
5. 選「記住墓葬姓名」或「研究墓葬循環」。

重新整理後，位置、故事節點、公開線索與下一組選項仍會保留。3D 操作仍沿用原型的固定步道與互動點；若要穩定展示故事選項，可先在 2D 完成選擇，再開 3D 展示同一 Session 的場景結果。

## 架構邊界

1. `backend/content/demo_story.py` 只定義 Demo fallback 的權威選項與節點，不直接改資料庫。
2. `backend/orchestration/demo_story_director.py` 把合法選項轉成普通 `StoryProposal`。
3. `ProposalResolver` 只執行白名單操作；`advance_story` 先驗證當前可用選項，再揭露公開線索／解鎖場景。
4. 狀態、成立事件、對話、NPC 記憶與故事進度沿用既有完整回合交易；`action_id` 與 `state_version` 保持有效。
5. `backend/content/scenes.py` 是場景與 3D visual profile 的單一來源；前端不維護另一份故事路線。
6. 圖片 job 只使用公開場景、公開章節、公開線索與固定 style version，不使用 NPC 私人記憶。
7. 圖片工作在遊戲狀態提交後建立，provider 失敗只將 job 標為 `fallback`，不 rollback 故事回合。

## 圖片生成現況

已完成：

- `ImageGateway` provider-neutral protocol。
- `scene_image_jobs` Alembic migration。
- prompt fingerprint 與同 Session 去重。
- fake provider 成功、timeout fallback、Session 隔離與重啟承接測試。
- 2D／3D 非重疊 polling 與舊場景結果 guard。
- 未設定 provider 時使用 Scene Registry 的版本化圖片。

尚未完成：

- 正式圖片 provider／模型／API key 尚未選定。
- 尚無雲端 provider adapter、下載後自有儲存、MIME／尺寸驗證。
- Demo 使用 FastAPI background task；正式部署應改為 transactional outbox＋獨立 worker、claim、stale-job recovery 與有限重試。

不要把 Codex／ChatGPT 內建圖片工具當成部署端可直接呼叫的 API。正式串接前要先確認 provider、模型、金鑰環境變數、成本上限與輸出 URL 保存策略。

## 驗收紀錄

- `PYTHONPATH=. ./.venv/bin/pytest -q`：96 passed，1 個既有 Starlette deprecation warning。
- `npm run build`：Next.js 16.4.4 production build passed。
- Live 火焰分支：平衡議會 → 命脈之泉 → 烈燚原，重啟後 `state_version=4` 且仍在烈燚原。
- Live 風沙分支：平衡議會 → 符石林 → 流塵谷，公開線索含 `fissure_map`，profile 為 `liuchen_dust_valley`。
- Headless Chrome：烈燚原與流塵谷皆以 1600×913 WebGL 載入，hard refresh 後位置正確，無 JavaScript exception。
- 實機驗收曾發現遠景上下顛倒，已由 `087e82e` 修正並重新截圖確認。

## 穩定 commits

```text
087e82e fix(scenes): orient Babylon backdrops correctly
95dbbed feat(images): add persistent scene image jobs
353f499 feat(scenes): apply distinct Babylon visual profiles
9b37bcb feat(story): add validated branching demo flow
c1079b8 feat(story): persist demo story progress contract
b6efdbc docs(demo): plan dynamic story delivery
```

## 下一位接手優先順序

1. 週四前先做一次人工完整彩排，確認投影環境、Chrome WebGL、Session 重新開始及兩條路線的按鈕操作。
2. 若必須展示「即時生圖」，先取得 provider／model／key／預算，再實作一個 `ImageGateway` adapter；沒有金鑰時保留現有 fallback，不阻擋 Demo。
3. 將圖片 job 改為 turn transaction 的 outbox row，lifespan／外部 worker 只在 commit 後處理，並補 stale running recovery、timeout 與有限重試。
4. 依場景加入正式 NPC／GLB／碰撞配置；目前非鳴霖場景仍重用原型互動角色與部分幾何。
5. B 的模型可用後，依 `docs/MODEL_GATEWAY_CONTRACT.md` 接 live endpoint，驗證角色一致性、RAG 權限與多回合品質。
6. C 確認 Demo choice 與正式事件 ID、烈燚原入口、E3-1、任務完成與結局門檻的映射，再移除 provisional 標記。

## 仍需團隊提供

- B：文字模型 provider、base URL、model、認證方式、timeout／錯誤格式、RAG metadata/filter。
- C：正式事件／分支 ID、烈燚原入口與出口、E3-1 場景轉移、任務與結局操作契約。
- 圖片：provider、model、key 環境變數名稱、每 Session 預算、輸出保存與內容審核策略。
- 美術／故事：各場景正式在場 NPC、GLB 或地圖配置、碰撞區、音效及尚未確認的世界觀資料。
