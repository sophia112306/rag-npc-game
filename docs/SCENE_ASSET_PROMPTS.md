# 場景圖片生成紀錄

2026-11-12 方向更新：主遊戲採固定圖庫與 2D。下列原始圖片保留寫實風格與構圖，遊戲端降低取樣細緻度；不採用可愛手繪，也不每回合即時生圖。原圖與雜湊維持不變。

生成日期：2026-11-10  
執行方式：OpenAI 內建圖片生成工具  
底層模型：工具未回傳模型識別碼，因此不推測型號  
風格參考：`frontend/public/game/forest-council.png`、`frontend/public/game/forest-eye-backdrop.png`

兩張參考圖只用於風格、色彩、細節密度與鏡頭角度；不是修改目標。輸出均為 1672×941 PNG，遊戲使用版本化檔案，不在回合中重新生成。

## 命脈之泉 v1

```text
Use case: stylized-concept
Asset type: 2D game environment background
Primary request: Create a new location in the same visual family as the two reference images: the sacred Life Spring inside Minglin forest, intended as a seamless scene change in an existing narrative game.
Input images: Image 1 and Image 2 are style, palette, rendering-detail, and camera-angle references only; do not copy their exact layouts.
Scene/backdrop: an ancient forest sanctuary centered on a clear turquoise spring fed by a small natural cascade, surrounded by mossy pale stone terraces, exposed old tree roots, ferns, and small wildflowers.
Subject: the spring is the single clear focal element; a walkable stone path enters from the lower foreground and leads toward it.
Style/medium: richly detailed hand-painted fantasy game background, crisp painterly foliage and stone textures, matching the references' warm luminous greens, teal water, and storybook realism.
Composition/framing: 16:9 wide environment, elevated three-quarter/isometric-like camera angle consistent with Image 1; useful open ground near center and lower foreground for overlaying a game character.
Lighting/mood: filtered golden forest sunlight, calm, sacred, alive, soft turquoise reflections.
Color palette: deep forest green, sunlit yellow-green, turquoise, pale weathered stone, restrained violet and white flowers.
Constraints: environment only; no people, no characters, no creatures, no UI, no text, no letters, no banners, no logos, no watermark; no giant eye motif; preserve clear readable walkable space; do not reproduce the council circle or exact landmarks from the references.
Avoid: photorealism, dark horror, excessive fog, clutter covering the focal path, modern objects.
```

## 符石林 v1

```text
Use case: stylized-concept
Asset type: 2D game environment background
Primary request: Create a second new Minglin forest location in the same visual family as the two reference images: a quiet grove of ancient rune stones where the player can investigate a provisional anomaly.
Input images: Image 1 and Image 2 are style, palette, rendering-detail, and camera-angle references only; do not copy their exact layouts.
Scene/backdrop: dense old forest opening into a small mossy stone grove; several weathered upright stones and broken low ruins form an irregular path around one restrained blue-green luminous rune stone.
Subject: the rune stone is the readable focal element but not enormous; an open walkable clearing occupies the center and lower foreground for overlaying a game character.
Style/medium: richly detailed hand-painted fantasy game background, crisp painterly foliage, roots and weathered stone, matching the references' storybook realism and high-quality game concept art.
Composition/framing: 16:9 wide environment, elevated three-quarter/isometric-like camera angle consistent with Image 1; distinct layout from the council circle and Life Spring; path exits subtly toward the left rear.
Lighting/mood: late-afternoon forest shade with warm sun shafts balanced by a subtle cool cyan rune glow; mysterious but not threatening.
Color palette: deep emerald and yellow-green foliage, gray-beige mossy stone, restrained cyan-blue glow, small violet and white flowers.
Constraints: environment only; no people, no characters, no creatures, no UI, no text, no readable letters, no banners, no logos, no watermark; no giant eye motif; preserve clear readable walkable space; the rune marks should be abstract non-linguistic motifs; do not reproduce the council circle or exact landmarks from the references.
Avoid: photorealism, dark horror, neon sci-fi machinery, portal rings, excessive fog, overpowered glow, modern objects.
```

## 流塵谷 v1

參考來源：使用者於 2026-11-10 專案對話提供的「流塵谷參考設計」。該圖只作為地貌、氣氛、地標及敘事情緒參考，不是修改目標，也不複製原構圖。

```text
Use case: stylized-concept
Asset type: 2D game environment background
Primary request: Create a game-ready interpretation of 流塵谷 (Liuchen Valley / Valley of Drifting Dust), using the supplied image only as a visual reference for biome, atmosphere, landmarks, and narrative mood rather than copying its exact composition.
Input images: Image 1 is the user's visual reference, not an edit target.
Scene/backdrop: a vast eroded desert canyon filled with ochre dunes and cracked earth; weathered funerary ruins, half-buried stone monuments, dead twisted trees, deep fissures, and a powerful column of drifting dust rising in the middle distance.
Subject: the flowing dust column and a readable route through the valley are the main focal elements; include only a few small distant mummy wanderers as environmental storytelling, never as large foreground characters.
Style/medium: richly detailed hand-painted fantasy game background with crisp painterly rock, sand, cloth, and ruin textures; storybook realism consistent with a polished narrative adventure game, not photorealistic.
Composition/framing: 16:9 wide environment, elevated three-quarter view suitable for a 2D game scene and 3D horizon texture; preserve a broad open traversable area across the lower center and middle ground for overlaying the player; create a distinct layout rather than reproducing Image 1.
Lighting/mood: dramatic dusty daylight breaking through heavy storm clouds; dangerous, ancient, desolate, but still readable for gameplay.
Color palette: warm ochre, burnt umber, sandstone, charcoal storm clouds, muted bone linen, restrained pale-gold light.
Materials/textures: layered sandstone cliffs, wind-carved ruins, cracked clay, loose sand, worn linen on distant figures.
Constraints: no close-up character, no prominent foreground mummy, no named character, no gore, no combat pose, no UI, no text, no letters, no logos, no watermark; distant mummy figures must remain small and secondary; keep the playable path and ground visually clear.
Avoid: exact copying of the reference composition, photorealism, modern objects, sci-fi machinery, neon colors, giant monsters, excessive debris covering the route.
```

## 烈燚原 v1

參考來源：使用者於 2026-11-10 專案對話提供的「烈燚原參考設計」。該圖只作為火焰地貌、中央地標、氣氛及色彩關係參考，不是修改目標，也不複製原構圖。參考圖中的人物不會帶入遊戲資產。

```text
Use case: stylized-concept
Asset type: 2D game environment background
Primary request: Create a game-ready interpretation of 烈燚原 (Lieyi Plains), using the supplied image only as a visual reference for its fiery biome, central landmark, atmosphere, and color relationships rather than copying the exact composition.
Input images: Image 1 is the user's visual reference, not an edit target.
Scene/backdrop: a vast volcanic plain enclosed by dark layered basalt cliffs and ancient heat-scarred ruins; narrow glowing magma streams branch naturally across cooled purple-black rock, with sparse ember-orange trees clinging to elevated terraces.
Subject: a monumental twisting pillar of living flame rises from a broad stepped obsidian altar in the middle distance; it is the unmistakable focal landmark, while a safe-looking readable route winds through cooled stone toward the altar.
Style/medium: richly detailed hand-painted fantasy game environment, crisp painterly basalt, magma, ruin, smoke, and foliage textures; polished narrative-adventure concept art with storybook realism, not photorealistic.
Composition/framing: 16:9 wide environment, elevated three-quarter view suitable for a 2D game scene and a Babylon 3D horizon texture; keep the lower center and a connected middle-ground path open and readable for overlaying the player; create a distinct layout rather than reproducing Image 1.
Lighting/mood: intense golden firelight against smoky violet shadow; dangerous, sacred, ancient, and visually readable rather than blinding.
Color palette: molten gold, ember orange, deep crimson, charcoal basalt, muted violet-black stone, restrained ash-gray smoke.
Materials/textures: stratified basalt, glassy obsidian steps, flowing magma, scorched masonry, dry heat-touched foliage.
Constraints: environment only; no people, no babies, no children, no characters, no bodies, no creatures, no gore, no combat, no UI, no text, no letters, no logos, no watermark; the flame landmark must remain fully visible; preserve clear traversable ground and avoid lava covering every route.
Avoid: exact copying of the reference composition, pasted or collage-like figures, photorealism, modern objects, sci-fi machinery, neon rainbow colors, giant monsters, excessive bloom, fully flooded lava foreground.
```
