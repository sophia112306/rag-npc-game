# Phaser 2D 主遊戲

更新：2026-11-12。玩法採固定寫實場景圖庫，依故事選項驗證、保存後換場。保留原人物、比例、末世寫實與奇幻遺跡風格，只以較低背景取樣呈現顆粒，沒有改用可愛素材。

完整設定、架構及缺口見 [根目錄 README](../README.md)。

## 啟動與入口

先在根目錄啟動 FastAPI（8300），再於本目錄執行 `npm ci`、`npm run dev`。展示用 `npm run build` 後執行 `npm run start`，皆在 3200；不要同時占用該埠。

- `/`：主遊戲。
- `/experiments`、`/experiments/babylon`：轉到同一個 2D 主頁。
- `/preview/veta`：獨立美術預覽，未接主故事。

API 預設 8300，可用 `.env.local` 的 `NEXT_PUBLIC_API_URL` 修改。不需 GPU、VPN、SSH tunnel 才能遊玩。

## 操作

WASD／方向鍵、點地面移動，右鍵或 Q／R 轉身。點人物／地標先走近互動，或靠近按 E。M 看地圖與合法路線，J 看手記／回報，滾輪或雙指縮放，Esc 關閉面板。NPC 交談保留瀏覽器 STT／TTS。

重整保留目前場景、故事與線索，步行座標暫回入口。遠處追蹤路線／回報先靠近正確互動點，抵達後確認行動。切圖由後端的正式回合結果決定。

## 程式位置

| 內容 | 位置 |
| --- | --- |
| UI、Session、回合、選項、地圖／手記、語音 | `app/page.tsx` |
| 人物、地標、Tiled、實體鍵碼、移動、相機與背景取樣 | `components/MinglinGame.tsx` |
| 共用地圖 | `components/WorldMap.tsx` |
| 共用手記 | `components/InvestigationJournal.tsx` 與 `.module.css` |
| API 型別、請求與 Session key | `lib/game-api.ts` |
| 音樂 | `lib/scene-music.ts`、`lib/use-scene-music.ts` |
| 主遊戲樣式 | `app/globals.css` |
| 原始圖庫／人物／配樂 | `public/game/`、`public/images/`、`public/audio/` |
| 歷史 3D 原型（停用） | `components/experiments/`，不由主遊戲載入 |

六份 `.tmj` 是 `minglin.tmj`、`life-spring.tmj`、`rune-grove.tmj`、`liuchen.tmj`、`lieyi-plains.tmj`、`border-ruins.tmj`。Actors 定義玩家、人物或 landmark 點，Walkable 定義安全範圍；URL 由後端 Scene Registry 的 `tilemap_url` 提供。改背景構圖時需同步校正這些點。

NPC 選項在開啟交談時由共用請求取得，沒有每位 NPC 各建一套狀態與 effect。泉眼與聖火調查仍由獨立 landmark 互動，不混入旁邊人物的對話。

背景載入後取樣為 836×471，再顯示於 1672×941 世界；原圖片不修改。角色、地標與 UI 分層呈現，不降低文字可讀性，也不需要重新生圖。

本版不呼叫 scene-image 或 scene-assets；模型／圖片服務保留介面供後續選用。正式故事 LLM／RAG 未接入，目前仍為規則分支。

## 驗證

在本目錄執行 `npm run build`。後端地圖測試檢查六地圖檔、背景一致性、出生點與互動點可達性，以及舊回合 map URL 相容。

[最新 2D 瀏覽器驗收](../docs/qa/2d-exploration/README.md)。歷史 Node 控制測試仍保留於 `tests/frontend/`，不將它們當成完整的 2D UI 驗收。
