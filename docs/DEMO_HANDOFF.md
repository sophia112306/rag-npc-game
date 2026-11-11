# 動態故事 Demo 交接

交接日期：2026-11-11

目標 Demo：2026-11-12（週四）

工作分支：`feature/hunyuan3d-gpu-gateway`
GitHub compare：<https://github.com/sophia112306/rag-npc-game/compare/main...feature/hunyuan3d-gpu-gateway>

GitHub 現況：`origin/main` 的 PR #7 只合到 `087e82e`；後續四筆故事／視覺修正及三筆 Hunyuan3D commits 都在本交接分支。下一位不要直接從舊 `feature/demo-dynamic-story` 或本機過期的 `main` 開始。

## 目前狀態

| 範圍 | 進度 | 狀態 |
| --- | --- | --- |
| 可保存動態故事 | `██████████ 100%` | 兩條狀態式 fallback 分支、選項防偽、事件與位置同交易 |
| Babylon 場景呈現 | `██████░░░░ 60%` | 透視衝突與錯誤幾何已移除；目前為 2.5D 視覺原型，正式材質 GLB／碰撞與 loader 待完成 |
| Hunyuan3D GPU gateway | `██████████ 100%` | 校機 shape-only API、SSH tunnel、持久化 cache、減面與真實 GLB 均已驗收 |
| 滾動圖片管線 | `████████░░ 80%` | Job／polling／快取／fallback 完成；正式 provider 尚未接入 |
| Demo 驗收與交接 | `█████████░ 90%` | 自動測試、build、兩條 live API 與 3D 載入通過；待正式彩排 |

目前可以在沒有 B 的模型、RAG 或圖片 API 時完整展示兩條可保存故事分支。介面會顯示「規則動態」及「版本化場景」，不會把 fallback 假稱為 AI 即時生成。

## 立即接手

```bash
cd /Users/qiao/rag-npc-game
git switch feature/hunyuan3d-gpu-gateway
git pull --ff-only origin feature/hunyuan3d-gpu-gateway
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
4. 烈燚原會顯示完整火焰遠景、目前章節與該分支專屬選項。
5. 選「觀察中央聖火」或「追查火焰長老」。

### 風沙分支

1. 在平衡議會選「前往符石林」。
2. 選「拼合裂隙地圖」。
3. 選「沿裂隙進入流塵谷」。
4. 流塵谷會顯示完整風沙遠景、目前章節與該分支專屬選項。
5. 選「記住墓葬姓名」或「研究墓葬循環」。

重新整理後，位置、故事節點、公開線索與下一組選項仍會保留。平衡議會只保留接近維達利亞的引導；固定尋找符石支線與不相干的地板／柱子已移除。其他場景直接顯示狀態式故事面板。

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

## Hunyuan3D GPU gateway

已完成：

- 校機 RTX 5060 Ti／16 GB，以 rootless Docker＋NVIDIA CDI 執行。
- Hunyuan3D-2mini shape-only，固定 CUDA 12.8、PyTorch 2.7.1+cu128 與 upstream commit。
- 遠端只綁 `127.0.0.1:8081`，本機透過 `ssh -N -L 8081:127.0.0.1:8081 nccu-gpu` 使用。
- Hunyuan、Hugging Face 與 U2Net cache 都在 named volume；強制重建 container 後 42 秒恢復 `ready`，不重抓 7.2 GB 權重。
- 校機帳號目前 `Linger=no`；主機重開或使用者 session 結束後，可能要重新啟動 rootless Docker 與 Compose，操作見 Hunyuan 部署文件。
- `/generate` 限制單工、圖片大小／格式、octree、steps 與 `max_faces`；輸出經官方 FloaterRemover、DegenerateFaceRemover、FaceReducer 後回傳 GLB。
- 正式 API 驗收：6.75 秒、687,488 bytes、17,222 vertices／40,000 faces、watertight。

本機健康檢查：

```bash
curl http://127.0.0.1:8081/health
```

校機管理與完整量測見 `docs/HUNYUAN3D_GPU_SETUP.md`。原始測試 GLB 沒有提交 Git：視覺檢查顯示人形輪廓成立，但無材質且晶體感明顯，不應直接取代維達利亞。下一位應先建立 FastAPI 持久化 3D asset job，再讓 Babylon 讀取已核准、已減面且附 transform／材質 metadata 的 GLB；瀏覽器不要直接呼叫 GPU gateway。

## 驗收紀錄

- `PYTHONPATH=. ./.venv/bin/pytest -q`：100 passed，1 個既有 Starlette deprecation warning。
- `npm run build`：Next.js 16.4.4 production build passed。
- Live 火焰分支：平衡議會 → 命脈之泉 → 烈燚原，重啟後 `state_version=4` 且仍在烈燚原。
- Live 風沙分支：平衡議會 → 符石林 → 流塵谷，公開線索含 `fissure_map`，profile 為 `liuchen_dust_valley`。
- Headless Chrome：烈燚原與流塵谷皆以 1600×913 WebGL 載入，hard refresh 後位置正確，無 JavaScript exception。
- 實機驗收曾發現遠景上下顛倒，已由 `087e82e` 修正並重新截圖確認。
- 實機後續發現交叉遠景平面形成巨大棕色三角遮蔽；已改為單一 screen-space layer，並隱藏非議會場景的角色、符石、假地面與錯誤物件群。獨立 WebGL 截圖確認流塵谷／烈燚原皆無遮蔽，且顯示不同故事選項。
- 議會後續截圖發現完整背景圖與 Babylon 水平地面使用不同地平線；已停用第二套地面及所有 primitive 場景物件，並移除固定符石任務。入口與接近維達利亞兩張 WebGL 截圖均無接縫或巨大幾何，四個後端故事選項可見。
- 舊 Session＋既有任務曾使 `travel_to_minglin` 被誤判成過期 Demo choice；已補 action 完整比對與 live 返回路線驗收。
- Hunyuan3D：容器內 GPU capability 12.0、PyTorch cu128、API health、cache recreate、128／256 GLB 與 40k-face 後處理均已實機驗收；container 0 restart、未 OOM。

## 穩定 commits

```text
4bc6ba8 feat(3d): bound generated mesh complexity
30efc21 fix(3d): persist Hunyuan model caches
1c2ac18 feat(3d): add private Hunyuan GPU gateway
f6a6e21 fix(visuals): unify council scene perspective
92dd67d fix(3d): separate story scenes from council prototype
da16300 fix(story): preserve legacy clickable choices
5438104 docs(handoff): document dynamic demo operation
087e82e fix(scenes): orient Babylon backdrops correctly
95dbbed feat(images): add persistent scene image jobs
353f499 feat(scenes): apply distinct Babylon visual profiles
9b37bcb feat(story): add validated branching demo flow
c1079b8 feat(story): persist demo story progress contract
b6efdbc docs(demo): plan dynamic story delivery
```

## 下一位接手優先順序

1. 週四前先做一次人工完整彩排，確認投影環境、Chrome WebGL、Session 重新開始及兩條路線的按鈕操作。
2. 建立 3D asset job／migration／provider adapter，讓 FastAPI 經 tunnel 呼叫 Hunyuan；保存 job 狀態、fingerprint、GLB metadata 與失敗 fallback，瀏覽器不直接連 8081。
3. 取得獨立物件參考圖，先做祭壇或符石；加入 Babylon GLB loader、transform／材質／碰撞 metadata，實際檢查遮擋與相機穿模。正式資產完成前不恢復基本幾何拼貼。
4. 若必須展示「即時生圖」，先取得 provider／model／key／預算，再實作一個 `ImageGateway` adapter；沒有金鑰時保留現有 fallback，不阻擋 Demo。
5. 將圖片 job 改為 turn transaction 的 outbox row，lifespan／外部 worker 只在 commit 後處理，並補 stale running recovery、timeout 與有限重試。
6. B 的模型可用後，依 `docs/MODEL_GATEWAY_CONTRACT.md` 接 live endpoint，驗證角色一致性、RAG 權限與多回合品質。
7. C 確認 Demo choice 與正式事件 ID、烈燚原入口、E3-1、任務完成與結局門檻的映射，再移除 provisional 標記。

## 仍需團隊提供

- B：文字模型 provider、base URL、model、認證方式、timeout／錯誤格式、RAG metadata/filter。
- C：正式事件／分支 ID、烈燚原入口與出口、E3-1 場景轉移、任務與結局操作契約。
- 圖片：provider、model、key 環境變數名稱、每 Session 預算、輸出保存與內容審核策略。
- 3D：祭壇、符石、遺跡、枯木等獨立物件參考圖，以及每個資產的場景、位置、尺寸、旋轉、材質與碰撞需求；若 Hunyuan 品質不足，再決定是否使用 Tripo／Meshy 預算。
- 美術／故事：各場景正式在場 NPC、地圖配置、碰撞區、音效及尚未確認的世界觀資料。
