# 鳴霖森林遊戲場景

在專案根目錄先啟動後端：

```bash
python3.12 -m venv .venv
./.venv/bin/pip install -r requirements.txt
./.venv/bin/uvicorn backend.main:app --reload --port 8300
```

另開終端機啟動前端：

```bash
cd frontend
npm ci
npm run dev
```

開啟 http://localhost:3200 。前端會呼叫 http://localhost:8300 的角色資料和遊戲 API。若後端使用其他位置，可複製 `.env.example` 為 `.env.local` 並修改 `NEXT_PUBLIC_API_URL`。

Phaser 會載入 [`public/game/minglin.tmj`](public/game/minglin.tmj) 內的 `Actors` 與 `Walkable` 物件圖層，並顯示 [`public/game/forest-council.png`](public/game/forest-council.png) 作為場景。可用 Tiled 編輯 NPC 出生點及多邊形可行走區；背景圖與 Tiled 的 `Background` 影像圖層使用同一張圖。調整背景構圖時，請一併校正地圖中的角色座標和可行走區。

操作：左鍵點擊可行走的地面，角色會轉向並走向點擊位置；右鍵點擊可讓角色原地面向該方向，Q／R 可逐步轉身。WASD 或方向鍵依畫面方向移動，角色會跟著轉向。滑鼠滾輪、畫面右側 ＋／－ 或手機雙指可縮放地圖，倍率範圍為 100%～220%；點倍率可回到全景。放大後鏡頭會在地圖範圍內隨角色移動，視角方向保持固定。點擊維達利亞，角色會走近並開始對話；靠近她後也可按 E。按 Esc 關閉對話。小螢幕另有移動及轉身按鈕。玩家與 NPC 是獨立的透明圖片，可以在背景上移動或替換。

目前可點擊的 NPC：鳴霖議會的維達利亞、安德烈；命脈之泉的維達利亞；首次進流塵谷只有門梅司文托；烈燚原有達索。塞特與希拉在第二幕的邊境廢墟同場，須先完成流塵谷、烈燚原各一條 Demo 調查路線並返回鳴霖，才能選「前往邊境廢墟（第二幕預覽）」。邊境廢墟使用 [`border-ruins.tmj`](public/game/border-ruins.tmj)；肖像採用使用者原圖，達索、塞特、希拉的地圖人物依原圖重做全身透明圖。這是對話與場景預覽，正式 E2-3 抉擇和裂隙地圖獎勵尚未實作。

PoC 介面提供操作說明、重新開始確認、初次載入及斷線重試畫面。對話文字會暫存在目前瀏覽器；只有當後端 Session 的回合與更新時間相符時才恢復，避免服務重啟後顯示不屬於新進度的舊紀錄。遊戲回合、事件與 NPC 記憶由後端 SQLite 保存。

目前未設定外部模型時，由後端「規則動態」依輸入、回合、記憶、承諾、任務與背包產生不同回覆及事件提案；設定 ModelGateway 後，標示會切換為「AI 動態」。Session 與完整回合已保存於 SQLite，後端重新啟動後可接續。前端在不確定請求是否成功時會保留原 `action_id` 重送；後端會回傳原結果，並拒絕同 ID 不同內容或過期狀態。

開啟對話後會顯示三個由後端依目前 Session 產生的行動選項。點擊後直接提交正式回合；任務建立後選項也會更新。自由文字與語音輸入仍保留。

## 第一人稱 3D 試玩

開啟 `http://localhost:3200/experiments/babylon` 進入 Babylon.js 幽藍遺跡版。`/experiments` 會直接轉到此頁；原本的 Phaser 場景仍在 `/`。

點擊石板路或目標，角色會沿預設路線前進；點地面可走到該路段，點畫面按鈕可走到下一個任務點。行走時從角色眼睛看出去，腳步帶動視角輕微上下起伏，路線轉彎時鏡頭自動轉向。抵達維達利亞或符石後自動觸發定點觀察，這時才可拖曳環顧四周、點擊符石記錄線索；Esc 結束觀察。WASD／方向鍵不控制這個版本的移動。

維達利亞使用 [`public/game/vidalia-cutout.png`](public/game/vidalia-cutout.png) 原圖材質，貼在輕微彎曲、會面向鏡頭的表面上；對話時角色會輕微上下晃動。這能保留正面的原圖細節，但仍屬 2.5D 呈現，無法提供完整的角色背面模型。

3D 版本目前是前端互動原型，NPC 對白與符石線索為固定示範內容，尚未接入後端劇情 API。只在進入此頁時載入 Babylon.js，渲染解析度也設上限。
