"""Public character profiles sourced from the existing frontend prototype."""

from backend.schemas.character import CharacterProfile
from backend.schemas.content import CharacterDefinition, SourceReference


CHARACTER_PROFILES: dict[str, CharacterProfile] = {
    "vidalia": CharacterProfile(
        npc_id="vidalia",
        name="維達利亞",
        romanized_name="Vidalia",
        title="初代精靈・平衡議會調解人",
        scene_name="鳴霖・平衡議會",
        portrait_url="/images/vidalia.png",
        description="鳴霖的精靈領袖與史官，守護命脈之泉，也在世界異象中尋找平衡。",
        greeting="旅人，歡迎來到鳴霖。命脈之泉近來沉默得太久了；你願意告訴我，你沿途看見了什麼嗎？",
    )
}


CHARACTER_DEFINITIONS: dict[str, CharacterDefinition] = {
    "vidalia": CharacterDefinition(
        npc_id="vidalia",
        public_profile=CHARACTER_PROFILES["vidalia"],
        private_profile={},
        sources=[
            SourceReference(
                source_type="frontend_prototype",
                source_id="frontend/babylon-game",
                locator="frontend/app/page.tsx",
            )
        ],
        setting_version=1,
        completeness_status="incomplete",
    )
}
