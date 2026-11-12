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
        item_id="fissure_map", name="裂隙地圖",
        description="協助塞特與希拉後取得的地圖，記錄裂隙的通行方向。",
        image_url="/game/items/fissure-map-v1.png", award_rule_event_id="E2-3_help_both",
    ),
}
