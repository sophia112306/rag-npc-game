# 第一人稱動態場景 Demo 交接

更新：2026-11-11；展示：2026-11-12。正式交接分支：`main`；最新修復分支：`feat/world-map-story-guidance`（保留歷史）。

前版把插畫換場當作第一人稱完成，驗收範圍不足，已撤回該判定。現在 Babylon 頁面使用可行走地形、天空、場景專屬配置與真正載入的 Hunyuan GLB。

## 現在怎麼玩

開啟 <http://localhost:3200/experiments/babylon>，右上角「新旅程」建立新 Session，舊存檔仍保留在資料庫。

- WASD／方向鍵移動；Shift 奔跑。
- 點地面可自由步行；點人物／祭壇會走近並開啟互動。右下方向按鈕可按住移動。中文輸入法啟用時仍使用實體 WASD，對話輸入框內則正常打字。
- 按住滑鼠拖曳環視，或按「鎖定滑鼠」；Esc 釋放。
- 走近人物／地標至 3.6 公尺內按 E，才開啟對話與故事選項。
- 對話框保留自由文字輸入；Esc 或關閉按鈕回到探索。
- 左上旅途小地圖／M：查看五個場景預覽、目前位置、可走路線與未解鎖提示。遠處點「追蹤路線」先步行靠近出發點，再選目的地確認旅行。
- 對話和右上角會列出下一步；故事節點改變會顯示進度通知。抵達泉眼／符石林後，走近地標按 E 調查，取得線索後才會開放烈燚原／流塵谷的對應路線。
- Tab／「世界指令」可調整當前場景。範例：`生成 6 個符石，變成夜晚並起霧`。
- 重新整理會恢復場景、故事進度與場景配置；連續步行座標目前回到該場景入口。

## 啟動

需要 Python 3.12、Node 20.9+。依鎖檔安裝後：

```bash
git switch main
git pull --ff-only origin main
./.venv/bin/pip install -r requirements-dev.txt
HUNYUAN3D_URL=http://127.0.0.1:8081 ./.venv/bin/uvicorn backend.main:app --port 8300
```

另一個終端：

```bash
cd frontend
npm ci
npm run build
npm run start
```

即時 3D 生成需要校內 VPN、GPU Docker 服務與 SSH tunnel：

```bash
ssh -N -L 8081:127.0.0.1:8081 nccu-gpu
curl http://127.0.0.1:8081/health
```

本機 8081 health 必須為 `ready`。不使用 GPU 時省略 `HUNYUAN3D_URL`，遊戲仍能以已生成的 GLB 探索與重建配置。主機不直接安裝 apt／pip／npm；GPU 依賴都在 Docker 裡。

## 指令如何改變世界

1. `scene_command` 先由受限解析器提出 `configure_scene`，只涵蓋日夜、天氣、地形與三種環境物件數量。
2. 後端核對當前場景、玩家、配置版本與數量上限；設定與事件、回合一起寫入 SQLite。重送同 `action_id` 不重複修改。
3. Babylon 根據公開 `world_scene` 重建地形、光照、天氣與物件配置。天空和地面共用同一座標與地平線。
4. 改變物件數量／重新生成時，持久化 asset jobs 經私有 Hunyuan API 產出新 GLB。前端先保持可玩的已生成模型，然後逐一替換，畫面顯示進度。
5. 預設場景使用版本化 Hunyuan GLB；單純日夜／天氣變化保留幾何 seed，避免每個回合浪費 GPU 重新建同一物件。

平衡議會保留原版圓形祭壇、石板路、石柱及水池。森林樹木採彎曲樹幹與原版手繪樹葉，GPU 樹木只保留根部細節；符石／祭壇維持完整 GLB。這是恢復原版美術的混合呈現，尚非完整的高品質森林模型。議會生成物件會避開祭壇、水池與通路，日夜與天氣指令仍生效。

主要程式：`forest-sanctuary.ts` 負責主景及材質生命週期，`sanctuary-layout.ts` 共用水池地形／碰撞範圍，`first-person.ts` 共用鍵盤／點擊／方向按鈕移動。不要再新增另一套固定路線控制。

目前上限：48 棵樹、12 個符石、3 座祭壇。支援晴朗／薄霧／下雨／沙塵、白天／黃昏／夜晚、丘陵／沙丘／岩地。不支援的物件或超量指令會回報原因，不消耗回合。這是有明確操作邊界的場景生成；完整任意文字到整個 3D 世界尚未提供。

## 可展示路線

每次換場後，玩家要自行走到新地標按 E。

自由對話產生觀察任務後，旅行現在同時推進故事節點；舊存檔卡在泉眼／符石林時會對齊抵達節點，不加回合或線索。輸入與當前對話選項完全相同的文字，可得到與點選該選項相同的效果；一般聊天仍由目前規則替身處理，沒有模糊匹配或自動旅行。

| 路線 | 實際選項 |
| --- | --- |
| 火焰 | 平衡議會 → 前往命脈之泉 → 追查水面的灰燼 → 循餘燼前往烈燚原 → 觀察聖火輪迴／調查長老的行蹤 → 帶著聖火線索返回鳴霖 |
| 風沙 | 平衡議會 → 前往符石林 → 辨認風沙路徑 → 循風沙路標進入流塵谷 → 記下被遺忘者的名字／追查埋葬與復生 → 帶著流塵線索返回鳴霖 |

命脈之泉有泉池、薄霧；符石林有中央符石、黃昏林地；流塵谷為沙土、裂谷與沙塵；烈燚原為玄武岩、動畫聖火與熔流。角色仍使用既有肖像 billboard，尚無正式骨架動畫 GLB。

「下一章待續」代表目前這條 Demo 調查已結束，正式第二幕尚未接入。此時地圖仍可選另外一條既有調查路線，已取得的公開線索會保留；這不等於新增正式第二幕。

## 測試與畫面證據

- 全套後端測試：119 passed；含原子保存、重送／版本衝突、場景指令限額、NPC 不能擅改場景、GLB 驗證、工作恢復、兩次逾時後 fallback、議會主景保護，以及地圖／故事選項解鎖和舊存檔修復。
- 前端控制：`node --experimental-strip-types --test tests/frontend/first-person.test.ts`，7 passed；涵蓋中文輸入法、按鈕焦點、文字輸入、點地面、拖曳、方向按鈕及地圖追蹤共用步行。
- Next.js 16.4.4 production build 與 TypeScript：通過。
- 本機 Chrome WebGL：W 2.8 秒由 z=8.0 移至 z=-1.8；距離 4.2m 拒絕互動，2.8m 可互動；兩條故事路線、五場景與新旅程已實際點選。
- 即時指令生成：夜晚／薄霧與 6 個符石配置成立；三個新 Hunyuan GLB 工作均一次成功，經遊戲後端 `/model` 取得並在 Babylon 顯示 `3/3`。
- 世界指令後硬重新整理，公開 `world_scene` 與保存前完全相同。Chrome 本機 90 幀採樣約 60 FPS（不是所有裝置的效能保證）。
- 截圖見 [qa/first-person](qa/first-person)。來源參考圖、貼圖與完整 prompts 見 [3D_ASSET_PROMPTS.md](3D_ASSET_PROMPTS.md)，GLB 雜湊在 `frontend/public/game/models/manifest.json`。
- 原版森林復原、點人物步行、水池與夜晚指令的最新截圖見 [qa/forest-sanctuary](qa/forest-sanctuary)。
- 小地圖、對話推進、地點解鎖、手機地圖與非鏡像巨樹的最新截圖見 [qa/world-map](qa/world-map)。

## 下一位接手

1. 先在投影用 Chrome 彩排 WASD、E、Tab、兩條路線與 VPN／tunnel；GPU 不可用時確認版本化 GLB 仍可玩。
2. B 接正式 LLM／RAG，依 `MODEL_GATEWAY_CONTRACT.md` 驗證角色語氣與知識權限。目前故事選項和指令解析仍為規則系統，Hunyuan 負責真實 mesh 生成。
3. C 確認正式事件／結局／死亡即結束，及 provisional 場景與 Demo 路線；目前沒有完整 E1／E2／E3 結局。
4. 美術提供正式角色 GLB、骨架動畫與完整場景資產；目前參考貼圖為投影材質，側面與背面品質有限。Hunyuan Paint 尚未載入。
5. 3D 工作目前由單一 FastAPI worker 執行；多人正式部署前改成外部 worker／租約。連續步行位置需獨立的存檔／同步策略。
6. 2D 圖片 job 仍未設定即時 ImageGateway provider；不要把 3D 模型工作和 2D 雲端生圖混為一談。
