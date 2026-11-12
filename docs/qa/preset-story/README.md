# 固定選項與背景柔化驗收

2026-11-12；分支 `feat/preset-story-choices`。Chrome／CDP 獨立測試瀏覽器，Next.js production 3200、FastAPI 8300。

## 背景柔化

背景仍取樣為 836×471，套用 0.55px Canvas 柔化與線性插值。只在背景載入時處理一次，人物、文字與原圖不變；未改變寫實比例或美術風格。

production build 通過。Chrome 1600×900 已實際查看森林、祭壇與水池，介面文字清楚。

![輕度柔化的原始森林](01-softened-council.jpg)
