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
    ),
    "andre": CharacterProfile(
        npc_id="andre",
        name="安德烈",
        romanized_name="Andre",
        title="鳴霖精靈・邊界調查官",
        scene_name="鳴霖・平衡議會",
        portrait_url="/images/andre.png",
        description="長年在各地邊界調查的精靈，正在查找命脈之泉與林地異象的線索。",
        greeting="我剛從林地邊緣回來。最近的地脈有些異動；你在路上看見什麼異常嗎？",
    ),
    "menmesvento": CharacterProfile(
        npc_id="menmesvento",
        name="門梅司文托",
        romanized_name="Menmesvento",
        title="流塵谷隱者・古卷守護者",
        scene_name="流塵谷",
        portrait_url="/images/menmesvento.png",
        description="在流塵谷記錄名字與記憶的隱者，言談沉靜，常攜著一本古卷。",
        greeting="風沙會掩去腳印，名字卻值得留下。旅人，你是從哪條路來的？",
    ),
    "dasso": CharacterProfile(
        npc_id="dasso",
        name="達索",
        romanized_name="Dasso",
        title="首席長老・火焰長老會",
        scene_name="烈燚原",
        portrait_url="/images/dasso.jpg",
        description="掌管火焰長老會的首席長老。",
        greeting="旅人，烈燚原的火焰不會替任何人回答問題。你想知道什麼？",
    ),
    "seth": CharacterProfile(
        npc_id="seth",
        name="塞特",
        romanized_name="Seth",
        title="流塵谷旅人",
        scene_name="流塵谷",
        portrait_url="/images/seth.jpg",
        description="披著舊斗篷的木乃伊，在風沙中尋找去路。",
        greeting="別靠得太近……我只是想找一條能離開這裡的路。",
    ),
    "syra": CharacterProfile(
        npc_id="syra",
        name="希拉",
        romanized_name="Syra",
        title="逃亡的記錄員",
        scene_name="流塵谷",
        portrait_url="/images/syra.jpg",
        description="抱著記錄盒來到流塵谷的人族女孩。",
        greeting="我會記下親眼看見的事。你從哪個方向來？",
    ),
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
    ),
    "andre": CharacterDefinition(
        npc_id="andre",
        public_profile=CHARACTER_PROFILES["andre"],
        private_profile={},
        sources=[
            SourceReference(
                source_type="character_notes",
                source_id="pasted_world_document",
                locator="三、安德烈",
            )
        ],
        setting_version=1,
        completeness_status="incomplete",
    ),
    "menmesvento": CharacterDefinition(
        npc_id="menmesvento",
        public_profile=CHARACTER_PROFILES["menmesvento"],
        private_profile={},
        sources=[
            SourceReference(
                source_type="character_notes",
                source_id="pasted_world_document",
                locator="四、門梅司文托",
            )
        ],
        setting_version=1,
        completeness_status="incomplete",
    ),
    **{
        npc_id: CharacterDefinition(
            npc_id=npc_id,
            public_profile=CHARACTER_PROFILES[npc_id],
            private_profile={},
            sources=[SourceReference(
                source_type="character_notes",
                source_id="pasted_world_document",
                locator=locator,
            )],
            setting_version=1,
            completeness_status="incomplete",
        )
        for npc_id, locator in (
            ("dasso", "五.1 首席長老・達索"),
            ("seth", "六、塞特"),
            ("syra", "七、希拉"),
        )
    },
}
