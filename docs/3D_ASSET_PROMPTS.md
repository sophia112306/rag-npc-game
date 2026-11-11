# 3D 環境資產來源

參考圖使用內建 imagegen 工具生成，保存於 `frontend/public/game/models/references/`。底層圖片模型名稱未由工具提供。GLB 使用校內 Hunyuan3D-2mini-turbo，採用 shape generation、20,000 面限制、參考圖投影貼圖與平滑法線；未載入 Hunyuan Paint。資產暫定，沒有新增核心世界觀。

重建指令：`PYTHONPATH=. ./.venv/bin/python scripts/generate_scene_models.py`。需要既有的 SSH tunnel 到本機 8081；產出版本、大小與 SHA-256 見 `frontend/public/game/models/manifest.json`。

## tree

```text
Use case: stylized-concept. Asset type: isolated image-to-3D reference for Hunyuan3D in a first-person fantasy forest game. Primary request: one mature ancient broadleaf tree, entire tree including roots and a dense organically rounded canopy visible, sturdy twisting gnarled trunk, balanced branching, rich small green leaves in irregular billowing masses, fine bark, moss accents. Three-quarter orthographic product view, believable natural proportions, detailed sculpted game asset style with physically coherent volume, soft neutral diffuse studio light. Transparent background, one centered object with 10% margin, no ground plane, no scenery, no cast shadow, no text, no UI, no characters. No conical trunk or faceted low-poly look. This is an independent environmental prop; do not imply new story facts.
```

## runestone

```text
Use case: stylized-concept. Asset type: isolated image-to-3D reference for Hunyuan3D in a first-person fantasy game. Primary request: one ancient standing rune stone, roughly human height, irregular rounded weathered stone slab with worn beveled edges, broad base of integrated natural rock, a shallow carved branching spiral glyph recessed in the front, fine cracks and small moss patches. Three-quarter front orthographic view, whole object visible, sculpted high-quality fantasy game asset, credible thickness and stone volume. Neutral grey-green stone, soft diffuse studio illumination. Transparent background, one centered object with 12% margin, no surrounding environment or ground plane, no additional objects, no text, no UI, no characters. No strong glowing haze. This is a provisional environmental prop, not a story artifact.
```

## altar

```text
Use case: stylized-concept. Asset type: isolated image-to-3D reference for Hunyuan3D for a fantasy first-person game. Primary request: one broad ancient circular stone altar, three concentric worn steps leading up to a heavy shallow circular basin on top, convincingly carved rock, chipped edges and naturally eroded carved bands. A low squat structure, wide enough for a human to stand on, height about one third of diameter. Entire object in three-quarter orthographic view from slightly above, crafted high-quality realistic fantasy game prop, charcoal basalt and dark warm grey stone, neutral diffuse studio illumination. Transparent background, one centered object, 12% margin, no fire, no lava, no ground plane, no characters, no letters or UI, no extra objects. Provisional environment prop only.
```

