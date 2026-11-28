"""Fixed item presentation and authored award conditions, separate from ownership."""

from dataclasses import dataclass

from backend.schemas.game_state import GameState, StoryPhase


@dataclass(frozen=True)
class ItemDefinition:
    item_id: str
    name: str
    description: str
    image_url: str
    award_rule_event_id: str


ITEMS = {
    "fissure_map": ItemDefinition(
        item_id="fissure_map", name="裂隙拓印圖",
        description=(
            "以流塵谷與邊境裂縫地形拓印而成的路線圖。"
            "暗線標示沙丘下的隱密裂縫與流動暗徑，"
            "可在危險時尋找通往流塵谷的退路。"
        ),
        image_url="/game/items/fissure-map-v1.png", award_rule_event_id="E2-3_help_both",
    ),
    "ember_amulet": ItemDefinition(
        item_id="ember_amulet", name="餘燼護符",
        description=(
            "以聖火餘燼為核心、纏著深色細繩與微焦金屬片的護符。"
            "它是賽特交給你的邊境互助信物，可在流塵谷的隱密路線中留下火光記號。"
        ),
        image_url="/game/items/ember-amulet-v1.jpg", award_rule_event_id="E2-3_help_both",
    ),
    "cloth_fragment": ItemDefinition(
        item_id="cloth_fragment", name="麻布殘片",
        description=(
            "印著模糊記號的麻布殘片，保留希拉保存與考證往事的痕跡。"
            "它可能成為追查記憶圖書館路徑與入侵紀錄的線索。"
        ),
        image_url="/game/items/cloth-fragment-v1.jpg", award_rule_event_id="E2-3_help_both",
    ),
    "dust_return_token": ItemDefinition(
        item_id="dust_return_token", name="塵歸令",
        description="門梅司文托交付的灰燼裂痕石牌，記錄一項只能由持有者做出的終局選擇。",
        image_url="/game/items/dust-return-token-v1.png",
        award_rule_event_id="E3-2_receive_dust_token",
    ),
    "vidalia_observation_page": ItemDefinition(
        item_id="vidalia_observation_page", name="維達利亞的觀察手札殘頁",
        description="維達利亞留在鳴霖林間石台的手札殘頁。字跡記錄了她對外來者的觀察。",
        image_url="/game/items/vidalia-observation-page-v1.jpg",
        award_rule_event_id="E1-3_find_vidalia_notes",
    ),
    "remembrance_slab": ItemDefinition(
        item_id="remembrance_slab", name="銘記石板",
        description=(
            "你在流塵谷拾起的石板。中央幾乎空白，邊緣刻有難辨的舊紋；"
            "它尚未記下任何經你查證的姓名。"
        ),
        image_url="/game/items/remembrance-slab-v1.jpg",
        award_rule_event_id="liuchen_find_remembrance_slab",
    ),
}


def vidalia_page_text(state: GameState) -> str:
    """Project the page's subjective, player-visible tone from authoritative state."""
    relation = state.npc_states["vidalia"].relation
    if (state.story_phase == StoryPhase.ACT4_ENDING and state.final_ending
            and relation >= 60 and state.axis > 0):
        return (
            "殘頁邊緣留下反覆翻閱的痕跡。她曾寫下的觀察，如今讀來像一段尚未說完的告別；"
            "那些選擇已經發生，字句卻沒有替任何人決定去向。"
        )
    if relation >= 60 and state.axis <= -20:
        return (
            "字跡在幾處停住，像寫字的人捨不得讓這段相遇結束。"
            "林間的光仍然柔和，頁角卻留下反覆摩挲的痕跡。"
        )
    if relation >= 60 and state.axis >= 20:
        return (
            "原本工整的筆跡多了塗改。她寫下對長久安穩的疑問，"
            "又在下一行停筆，似乎仍不知道該如何回答自己。"
        )
    return (
        "字跡工整而疏離，記著林間光影與一位未記載的訪客。"
        "她似乎只是好奇：這道陌生氣息為何停在鳴霖，又會往哪裡去？"
    )
