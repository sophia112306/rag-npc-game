# 固定道具美術來源

2026-11-12，使用內建 OpenAI 圖片生成工具與 imagegen 技能，一次生成、版本化保存；工具未提供底層模型名稱，記為 unknown。遊玩時不呼叫生圖服務。

## 裂隙地圖 v1

- 檔案：[`fissure-map-v1.png`](../frontend/public/game/items/fissure-map-v1.png)。1254×1254，RGBA，已檢查透明 alpha。
- 名稱及取得條件來源：既有故事設計、C 的 `E2-3_help_both`；美術僅是物品示意，不新增正式地名、能力或世界地理。
- 版本、SHA-256 與來源記於 [`manifest.json`](../frontend/public/game/items/manifest.json)。

完整最終 prompt：

```text
Use case: stylized-concept. Asset type: a single reusable inventory item illustration for an existing 2D post-apocalyptic realistic fantasy game, square composition. Subject: the Fissure Map (裂隙地圖), an old folded parchment map carried by a traveler, with a few broad hand-drawn fracture lines and one restrained route mark. Weathered beige paper, dark umber ink, softened painterly realism, mature and somber, low micro-detail, soft edges, readable silhouette at 64 to 96 pixels. The illustration is the physical map only, shown almost top down with a slight tilt, centered, filling about 75 percent of the frame. Truly transparent background and clean alpha, no scene, no floor, no character or hands, no text or letters, no labels, no invented place names, no jewels, no magic glow, no cartoon or cute styling, no UI frame or watermark. The map denotes known terrain routes, not a portal or magical power. This is fixed versioned game art, not a full new scene.
```
