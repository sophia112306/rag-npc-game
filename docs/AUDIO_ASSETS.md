# 遊戲場景音樂素材

五個可遊玩的場景各有一首配樂；維塔的獨立預覽畫面另有一首。曲目在 `frontend/lib/scene-music.ts` 對應，音檔放在 `frontend/public/audio/`。以下來源頁均標示 **CC0 1.0**；作者與來源仍列於此，方便追溯。

| 場景 | 曲目與作者 | 來源 | 本機檔案 |
| --- | --- | --- | --- |
| 鳴霖・平衡議會 | Iremos Forest Theme Loop，beardalaxy | [OpenGameArt](https://opengameart.org/content/iremos-forest-theme-loop) | `iremos-forest-theme.ogg` |
| 鳴霖・命脈之泉 | Underwater Theme（第二變奏），Spring Spring | [OpenGameArt](https://opengameart.org/content/underwater-theme-1) | `life-spring.ogg` |
| 鳴霖・符石林 | Dark Shrine Loop，qubodup（改編自 yd 的 Shrine） | [OpenGameArt](https://opengameart.org/content/dark-shrine-loop) | `rune-grove.ogg` |
| 流塵谷 | Desert theme，yd | [OpenGameArt](https://opengameart.org/content/desert-theme) | `liuchen-valley.ogg` |
| 烈燚原 | Through Fire，KiluaBoy | [OpenGameArt](https://opengameart.org/content/through-fire-through-sea-violin-flute-loop) | `lieyi-plains.ogg` |
| 維塔・沉眠之所（預覽） | Heavenly Loop，isaiah658 | [OpenGameArt](https://opengameart.org/content/heavenly-loop) | `veta-dream.ogg` |

授權條款：[Creative Commons CC0 1.0](https://creativecommons.org/publicdomain/zero/1.0/)。

| 檔案 | SHA-256 |
| --- | --- |
| `iremos-forest-theme.ogg` | `52103c8ef155224a9faeb3a834efe589a27ec0eeb929fdfa855e23d365f8fc01` |
| `life-spring.ogg` | `1e64d4d2e56627b65a92f82a02f61fac3eeab790b9682f50e7c9ee6a9a430293` |
| `rune-grove.ogg` | `9580618dc851f70c3a11b5ff87672867de44cd38b35dabf926d6befde20e78d0` |
| `liuchen-valley.ogg` | `086f52dc18e1db9a51831708295ae6e758f2f5edf79a0241b390d72bfb858c01` |
| `lieyi-plains.ogg` | `53500cdf66cfdd1ff84c725bfccac8ec48b43ad2fee0058ff8a161caa59fcd1b` |
| `veta-dream.ogg` | `a842e9e054019132cacc8fd352e7b31c000ebb51e0b227a2511e1bccb4eb166e` |

首頁及 Babylon 試玩頁共用五個遊戲場景的音樂對應。玩家點擊「播放音樂」後開始循環播放；之後換場會切換曲目，玩家關閉音樂後換場仍保持靜音。探索音量 20%，對話時 11%，首頁 NPC 語音播放時 7%。維塔預覽畫面的音樂也由玩家自行開啟。瀏覽器無法載入或播放時，按鈕顯示重試，不影響遊戲回合。
