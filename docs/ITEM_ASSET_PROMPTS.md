# 固定道具美術來源

2026-11-12，使用內建 OpenAI 圖片生成工具與 imagegen 技能，一次生成、版本化保存；工具未提供底層模型名稱，記為 unknown。遊玩時不呼叫生圖服務。

## 裂隙拓印圖 v1

- 檔案：[`fissure-map-v1.png`](../frontend/public/game/items/fissure-map-v1.png)。1254×1254，RGBA，已檢查透明 alpha。
- 名稱及取得條件來源：既有故事設計、C 的 `E2-3_help_both`；美術僅是物品示意，不新增正式地名、能力或世界地理。
- 版本、SHA-256 與來源記於 [`manifest.json`](../frontend/public/game/items/manifest.json)。

完整最終 prompt：

```text
Use case: stylized-concept. Asset type: a single reusable inventory item illustration for an existing 2D post-apocalyptic realistic fantasy game, square composition. Subject: the Fissure Rubbing Map (裂隙拓印圖), an old folded parchment map carried by a traveler, with broad hand-rubbed terrain fracture lines, a few hidden paths beneath dunes, and one restrained route mark. Weathered beige paper, dark umber ink, softened painterly realism, mature and somber, low micro-detail, soft edges, readable silhouette at 64 to 96 pixels. The illustration is the physical map only, shown almost top down with a slight tilt, centered, filling about 75 percent of the frame. Truly transparent background and clean alpha, no scene, no floor, no character or hands, no text or letters, no labels, no invented place names, no jewels, no magic glow, no cartoon or cute styling, no UI frame or watermark. The map denotes known terrain routes, not a portal or magical power. This is fixed versioned game art, not a full new scene.
```

## 生死之書與塵歸令（2026-11-22 使用者提供）

下列兩張透明底圖片由使用者從 `~/Downloads/遊戲專題參考圖圖片` 指定並確認接入，
不是本次工作重新生成；不得改標為本專案工具生成。

- `frontend/public/game/props/book-of-life-and-death-v1.png`：記憶圖書館 Truth A 的調查圖，完成後顯示於調查手記。
- `frontend/public/game/items/dust-return-token-v1.png`：門梅司文托在 `E3-2_receive_dust_token` 交付的塵歸令，顯示於背包並解鎖符合條件的「塵歸」結局。

尺寸、透明度與 SHA-256 分別記於道具／物件 manifest；目前不需要再生成道具圖。

另將使用者提供的 `觀測者.jpg` 保存為 `frontend/public/images/alan.jpg`，
在 Truth C 完成後作為艾倫通訊的調查手記圖片。艾倫仍是遠端觀測者，不會被錯放成地圖上的實體 NPC。

## 餘燼護符與麻布殘片（2026-11-23 使用者提供）

這兩張圖片由使用者提供並確認接入，對應 E2-3「協助兩人」的固定獎勵；遊玩時直接引用，不呼叫圖片生成服務。

- `frontend/public/game/items/ember-amulet-v1.jpg`：餘燼護符，賽特的邊境互助信物。2752×1536，JPEG，非透明底。
- `frontend/public/game/items/cloth-fragment-v1.jpg`：麻布殘片，希拉的記錄線索。2752×1536，JPEG，非透明底。
- 兩張圖的版本、來源規則與 SHA-256 記於 [`manifest.json`](../frontend/public/game/items/manifest.json)。
- 目前使用原始 JPG 顯示；若之後要做成小尺寸道具 icon，再另行裁切或去背，不在本次自行修改素材。
