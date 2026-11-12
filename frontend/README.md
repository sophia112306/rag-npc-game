# 前端導覽｜Phaser 2D 與 Babylon 3D

更新：2026-11-12。整個專案的世界設定、故事線、架構、API 與缺口以 [根目錄 README](../README.md) 為準；本文件只補前端入口與編輯位置。

## 啟動

先依根目錄 README 啟動 FastAPI（8300），再於本目錄執行：

```bash
npm ci
npm run dev
```

展示可用 `npm run build` 後執行 `npm run start`，皆在 3200；不要同時占用該埠。API 預設 `http://localhost:8300`，可將 `.env.example` 複製為 `.env.local` 設定 `NEXT_PUBLIC_API_URL`。

## 頁面與目前功能

| 路徑 | 入口／功能 |
| --- | --- |
| `/` | `app/page.tsx`＋`components/MinglinGame.tsx`：Phaser 2D、人物、對話、後端回合、瀏覽器 STT／TTS。 |
| `/experiments/babylon` | `app/experiments/babylon/page.tsx` 掛載 `components/experiments/TrialExperience.tsx`：自由第一人稱、後端故事、M 地圖、J 手記、Tab 世界指令與 GLB 工作輪詢。 |
| `/experiments` | 轉向 Babylon 頁。 |
| `/preview/veta` | 維塔獨立預覽，尚非主遊戲章節。 |

3D 使用 WASD／方向鍵移動、Shift 奔跑、點地面步行、拖曳環視、近距離 E 互動。它已接入 FastAPI／SQLite，舊版固定路線與「WASD 無效、未接後端」的描述已失效。人物目前仍是肖像 billboard，非完整骨架人物模型。

目前 2D 可點擊的 NPC：鳴霖議會的維達利亞、安德烈；命脈之泉的維達利亞；首次進流塵谷只有門梅司文托；烈燚原有達索。3D 可點擊維達利亞、門梅司文托、達索，以及邊境廢墟的塞特與希拉。須先完成流塵谷、烈燚原各一條 Demo 調查路線並返回鳴霖，才能選「前往邊境廢墟（第二幕預覽）」。邊境廢墟使用 [`border-ruins.tmj`](public/game/border-ruins.tmj)；肖像採用使用者原圖，達索、塞特、希拉的地圖人物依原圖重做全身透明圖。這是對話與場景預覽，正式 E2-3 抉擇和裂隙地圖獎勵尚未實作。

2D 可左鍵點地面／人物、WASD／方向鍵移動、右鍵或 Q／R 轉身、滾輪／按鈕縮放，靠近人物按 E。語音依瀏覽器能力、權限與 localhost／HTTPS 支援；3D 尚未加入同等語音 UI。

## 編輯位置

| 範圍 | 位置 |
| --- | --- |
| 3D UI、Session 同步、正式回合送出與模型輪詢 | `components/experiments/TrialExperience.tsx` |
| 共用第一人稱控制 | `components/experiments/first-person.ts` |
| Babylon 模型、材質、光照、地形與碰撞 | `components/experiments/babylon-driver.ts` |
| 地形高度與 driver 介面 | `components/experiments/world.ts` |
| 原版森林主景、樹葉與水池 | `forest-sanctuary.ts`、`sanctuary-layout.ts`、`water-material.ts`，均位於 `components/experiments/` |
| 生成模型尺寸檢查、調查手記 | 同目錄 `asset-layout.ts`、`InvestigationJournal.tsx` |
| 共用地圖 | `components/WorldMap.tsx`；合法路線由後端提供，3D 可追蹤／確認旅行，2D 目前沒有傳入旅行 callback |
| 2D UI／語音與 Phaser 移動／碰撞 | `app/page.tsx`、`components/MinglinGame.tsx` |
| 共用 API 型別、請求、Session key | `lib/game-api.ts` |
| 場景音樂與播放 | `lib/scene-music.ts`、`lib/use-scene-music.ts` |
| 全域／2D、3D 樣式 | `app/globals.css`、`components/experiments/TrialExperience.module.css` |

`public/game/minglin.tmj`、`minglin-life-spring.tmj`、`liuchen.tmj`、`lieyi.tmj`、`border-ruins.tmj` 的 Actors／Walkable 圖層定義 2D 角色點與可走區。符石林尚未有專屬 Tiled 地圖。背景構圖變更時需一起校正角色點和可走區。

`public/game/scenes/` 保存版本化插畫，`models/` 保存預設 GLB／參考圖／manifest，`materials/` 是地表材質；`public/images/` 是肖像，`public/audio/` 是配樂。動態 GLB 由 FastAPI 下載，不把本機生成檔寫進前端原始碼。

故事內容與事件合法性由後端負責：不要在前端另寫分支判定、直接增加物品或硬切場景。兩頁共用 Session 與 API 契約，但語音、手記、世界指令仍有功能差異。重整保留場景／故事，步行座標暫回入口。

## 驗證

從專案根目錄執行：

```bash
node --experimental-strip-types --test tests/frontend/*.test.ts
```

需使用支援該旗標的 Node。production build 在本目錄執行 `npm run build`；最新瀏覽器操作證據見 [故事與場景 QA](../docs/qa/story-consequences/README.md)。
