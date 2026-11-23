"""Fixed item presentation and authored award conditions, separate from ownership."""

from dataclasses import dataclass


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
}
