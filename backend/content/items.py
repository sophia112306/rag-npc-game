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
    "dust_return_token": ItemDefinition(
        item_id="dust_return_token", name="塵歸令",
        description="門梅司文托交付的灰燼裂痕石牌，記錄一項只能由持有者做出的終局選擇。",
        image_url="/game/items/dust-return-token-v1.png",
        award_rule_event_id="E3-2_receive_dust_token",
    ),
}
