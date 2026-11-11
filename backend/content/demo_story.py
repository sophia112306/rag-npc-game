"""Author-bounded fallback story choices for the Thursday demo.

The definitions provide a reliable path when the live model or RAG is unavailable.
They only combine facts already present in the supplied story background; every
state change still passes through the normal proposal resolver.
"""

from dataclasses import dataclass

from backend.schemas.game_state import GameState
from backend.schemas.player_action import ActionMode
from backend.schemas.player_choice import PlayerChoice


@dataclass(frozen=True)
class DemoStoryChoiceDefinition:
    choice_id: str
    source_node_id: str
    source_scene_id: str
    label: str
    message: str
    response_text: str
    next_node_id: str
    next_chapter_title: str
    action_mode: ActionMode = ActionMode.INTERACTION
    target_npc_id: str | None = None
    destination_scene_id: str | None = None
    reveal_clue_ids: tuple[str, ...] = ()
    unlock_scene_ids: tuple[str, ...] = ()
    special_scene_transition: bool = False
    visual_signal: str | None = None

    def to_player_choice(self) -> PlayerChoice:
        return PlayerChoice(
            choice_id=self.choice_id,
            story_choice_id=self.choice_id,
            label=self.label,
            message=self.message,
            target_npc_id=self.target_npc_id,
            action_mode=self.action_mode,
            destination_scene_id=self.destination_scene_id,
        )


def _choice(
    choice_id: str,
    source_node_id: str,
    source_scene_id: str,
    label: str,
    message: str,
    response_text: str,
    next_node_id: str,
    next_chapter_title: str,
    **changes: object,
) -> DemoStoryChoiceDefinition:
    return DemoStoryChoiceDefinition(
        choice_id=choice_id,
        source_node_id=source_node_id,
        source_scene_id=source_scene_id,
        label=label,
        message=message,
        response_text=response_text,
        next_node_id=next_node_id,
        next_chapter_title=next_chapter_title,
        **changes,
    )


_MINGLIN_TRAVEL = (
    {
        "choice_id": "travel_to_minglin_life_spring",
        "label": "前往命脈之泉",
        "message": "我先去命脈之泉調查停止擴張的泉水。",
        "response_text": "維達利亞讓開林間道路。越靠近泉眼，原本應該流動的水聲越顯得不自然。",
        "next_node_id": "life_spring_arrival",
        "next_chapter_title": "沉默的泉眼",
        "destination_scene_id": "minglin_life_spring",
    },
    {
        "choice_id": "travel_to_minglin_rune_grove",
        "label": "前往符石林",
        "message": "我先去符石林調查異象留下的痕跡。",
        "response_text": "維達利亞指向林後的舊路。符石之間的微光正以不屬於森林的節奏閃動。",
        "next_node_id": "rune_grove_arrival",
        "next_chapter_title": "失序的符石",
        "destination_scene_id": "minglin_rune_grove",
    },
)


def _minglin_travel_choices(node_id: str) -> tuple[DemoStoryChoiceDefinition, ...]:
    return tuple(
        _choice(
            source_node_id=node_id,
            source_scene_id="minglin",
            action_mode=ActionMode.MOVEMENT,
            target_npc_id=None,
            **values,
        )
        for values in _MINGLIN_TRAVEL
    )


DEMO_STORY_CHOICES: tuple[DemoStoryChoiceDefinition, ...] = (
    _choice(
        "ask_location",
        "minglin_arrival",
        "minglin",
        "詢問目前所在地",
        "這裡是什麼地方？泉水和現在的異象有關嗎？",
        "這裡是鳴霖的平衡議會。命脈之泉已經很久沒有向外延伸；最近又出現異象，我還不知道兩者是否相關。",
        "minglin_orientation",
        "鳴霖異象",
        action_mode=ActionMode.DIALOGUE,
        target_npc_id="vidalia",
        reveal_clue_ids=("spring_stopped_expanding",),
    ),
    _choice(
        "ask_for_task",
        "minglin_arrival",
        "minglin",
        "詢問能幫什麼忙",
        "我可以先從哪裡調查這場異象？",
        "命脈之泉與符石林都留下了異常。你選擇先看哪一處，之後能追到的線索也會不同。",
        "minglin_briefed",
        "兩條調查路線",
        action_mode=ActionMode.DIALOGUE,
        target_npc_id="vidalia",
        reveal_clue_ids=("minglin_anomaly",),
    ),
    *_minglin_travel_choices("minglin_arrival"),
    _choice(
        "ask_for_task",
        "minglin_orientation",
        "minglin",
        "追問異象來源",
        "我應該先調查哪一種異象？",
        "泉眼保存著世界擴張停止後的痕跡；符石則記錄近期的空間失序。兩條路都可能把你帶離鳴霖。",
        "minglin_briefed",
        "兩條調查路線",
        action_mode=ActionMode.DIALOGUE,
        target_npc_id="vidalia",
        reveal_clue_ids=("minglin_anomaly",),
    ),
    *_minglin_travel_choices("minglin_orientation"),
    _choice(
        "ask_about_factions",
        "minglin_orientation",
        "minglin",
        "詢問其他勢力",
        "除了精靈，還有哪些勢力會追查這場異象？",
        "人族長老與流塵谷的居民都在留意這場異象。各自為何而來，還需要查證。",
        "minglin_briefed",
        "兩條調查路線",
        action_mode=ActionMode.DIALOGUE,
        target_npc_id="vidalia",
        reveal_clue_ids=("factions_notice_anomaly",),
    ),
    *_minglin_travel_choices("minglin_briefed"),
    _choice(
        "ask_about_fire_elder",
        "minglin_briefed",
        "minglin",
        "追問火焰長老",
        "火焰長老在調查什麼？",
        "我們只知道長老會最近在泉水附近活動；他們的目的尚無確證。",
        "minglin_briefed",
        "兩條調查路線",
        action_mode=ActionMode.DIALOGUE,
        target_npc_id="vidalia",
        reveal_clue_ids=("elders_near_spring",),
    ),
    _choice(
        "ask_about_mummies",
        "minglin_briefed",
        "minglin",
        "追問木乃伊",
        "流塵谷的人怎麼看待這場異象？",
        "流塵谷的人很重視記憶與名字。若你遇見他們，先聽他們說自己的故事。",
        "minglin_briefed",
        "兩條調查路線",
        action_mode=ActionMode.DIALOGUE,
        target_npc_id="vidalia",
        reveal_clue_ids=("mummies_value_names",),
    ),
    _choice(
        "study_spring_ash",
        "life_spring_arrival",
        "minglin_life_spring",
        "追查水面的灰燼",
        "我沿著逆流灰燼尋找它來自哪裡。",
        "灰燼沒有沉入泉底，反而逆著水脈指向遙遠的聖火。烈燚原的方向被短暫照亮。",
        "ember_route_ready",
        "通往聖火的餘燼",
        visual_signal="ember",
        reveal_clue_ids=("ember_current",),
        unlock_scene_ids=("lieyi_plains",),
    ),
    _choice(
        "study_spring_echo",
        "life_spring_arrival",
        "minglin_life_spring",
        "聆聽泉底裂響",
        "我記下泉底傳來的裂響與風沙節奏。",
        "裂響與泉水無關，像是從世界另一側的峽谷傳回。碎光拼出一段通往流塵谷的裂隙路徑。",
        "fissure_route_ready",
        "裂隙中的風沙",
        visual_signal="dust",
        reveal_clue_ids=("dust_route_trace",),
        unlock_scene_ids=("liuchen_valley",),
    ),
    _choice(
        "return_to_council",
        "life_spring_arrival",
        "minglin_life_spring",
        "返回平衡議會",
        "我先返回議會整理目前的線索。",
        "你帶著尚未釐清的觀察回到維達利亞面前。兩條調查路線仍然開放。",
        "minglin_briefed",
        "兩條調查路線",
        action_mode=ActionMode.MOVEMENT,
        destination_scene_id="minglin",
    ),
    _choice(
        "read_ember_runes",
        "rune_grove_arrival",
        "minglin_rune_grove",
        "解讀灼熱符痕",
        "我追蹤符石上反覆出現的灼熱紋路。",
        "灼熱紋路不是精靈文字，卻與人族聖火的方向一致。烈燚原成為可以追查的暫定路線。",
        "ember_route_ready",
        "通往聖火的符痕",
        visual_signal="ember",
        reveal_clue_ids=("ember_rune_trace",),
        unlock_scene_ids=("lieyi_plains",),
    ),
    _choice(
        "trace_dust_runes",
        "rune_grove_arrival",
        "minglin_rune_grove",
        "辨認風沙路徑",
        "我從符石間的風沙軌跡辨認流塵谷的方向。",
        "符石的缺口指向流塵谷。你記下這條暫定路線，準備前往查探。",
        "fissure_route_ready",
        "流塵谷的路標",
        visual_signal="dust",
        reveal_clue_ids=("dust_route_trace",),
        unlock_scene_ids=("liuchen_valley",),
    ),
    _choice(
        "return_to_council",
        "rune_grove_arrival",
        "minglin_rune_grove",
        "返回平衡議會",
        "我先返回議會整理目前的線索。",
        "你帶著尚未釐清的觀察回到維達利亞面前。兩條調查路線仍然開放。",
        "minglin_briefed",
        "兩條調查路線",
        action_mode=ActionMode.MOVEMENT,
        destination_scene_id="minglin",
    ),
    _choice(
        "enter_lieyi_plains",
        "ember_route_ready",
        "minglin_life_spring",
        "循餘燼前往烈燚原",
        "我沿著餘燼指引進入烈燚原。",
        "泉面映出的火光凝成通路。當熱浪取代林霧時，中央聖火已在黑色祭壇上升起。",
        "lieyi_arrival",
        "烈燚原的聖火",
        action_mode=ActionMode.MOVEMENT,
        destination_scene_id="lieyi_plains",
        special_scene_transition=True,
    ),
    _choice(
        "enter_lieyi_plains",
        "ember_route_ready",
        "minglin_rune_grove",
        "循符痕前往烈燚原",
        "我沿著灼熱符痕進入烈燚原。",
        "符石的光轉為熾金，林地在熱浪中退去。中央聖火正照亮玄武岩原野。",
        "lieyi_arrival",
        "烈燚原的聖火",
        action_mode=ActionMode.MOVEMENT,
        destination_scene_id="lieyi_plains",
        special_scene_transition=True,
    ),
    _choice(
        "enter_liuchen_valley",
        "fissure_route_ready",
        "minglin_life_spring",
        "依裂隙回聲進入流塵谷",
        "我依照記下的裂隙路徑進入流塵谷。",
        "泉底裂響撕開一線風沙。你穿過不穩定的地理優勢，在追兵合圍前落入流塵谷。",
        "liuchen_arrival",
        "流塵谷的名字",
        action_mode=ActionMode.MOVEMENT,
        destination_scene_id="liuchen_valley",
        special_scene_transition=True,
    ),
    _choice(
        "enter_liuchen_valley",
        "fissure_route_ready",
        "minglin_rune_grove",
        "循風沙路標進入流塵谷",
        "我沿著符石間辨認的風沙方向進入流塵谷。",
        "符石路徑在腳下崩解，你循著先前記下的風沙方向穿過裂隙，進入流塵谷。",
        "liuchen_arrival",
        "流塵谷的名字",
        action_mode=ActionMode.MOVEMENT,
        destination_scene_id="liuchen_valley",
        special_scene_transition=True,
    ),
    _choice(
        "observe_sacred_fire",
        "lieyi_arrival",
        "lieyi_plains",
        "觀察聖火輪迴",
        "我觀察木乃伊進入聖火後的轉生規則。",
        "聖火不是單純的毀滅：它把木乃伊送回人族，讓兩族爭奪同一批靈魂的矛盾顯現出來。",
        "demo_fire_complete",
        "Demo 完成：輪迴的代價",
        visual_signal="ember",
        reveal_clue_ids=("sacred_fire_cycle",),
    ),
    _choice(
        "question_fire_elder_motive",
        "lieyi_arrival",
        "lieyi_plains",
        "調查長老的行蹤",
        "我先查長老會在這裡做了什麼，不憑猜測下結論。",
        "長老會也在關注聖火，但你還沒有足夠證據判斷他們的目的。",
        "demo_fire_complete",
        "Demo 完成：長老的行蹤",
        visual_signal="ember",
        reveal_clue_ids=("elders_surveyed_fire",),
    ),
    _choice(
        "listen_to_forgotten_names",
        "liuchen_arrival",
        "liuchen_valley",
        "記下被遺忘者的名字",
        "我願意聽他們說出希望被記住的名字。",
        "他們希望自己的名字不只留在沙裡。你記住了其中幾個，卻還不知道這份請求背後的原因。",
        "demo_dust_complete",
        "Demo 完成：被記住的人",
        visual_signal="dust",
        reveal_clue_ids=("mummies_seek_remembrance",),
    ),
    _choice(
        "study_burial_cycle",
        "liuchen_arrival",
        "liuchen_valley",
        "追查埋葬與復生",
        "我追查人被埋葬後轉化成木乃伊的過程。",
        "墓葬痕跡證明人族與木乃伊並不是兩批靈魂，而是同一群存在在埋葬與聖火之間循環。",
        "demo_dust_complete",
        "Demo 完成：同一批靈魂",
        visual_signal="dust",
        reveal_clue_ids=("burial_fire_cycle",),
    ),
    _choice(
        "return_with_fire_findings",
        "demo_fire_complete",
        "lieyi_plains",
        "帶著聖火線索返回鳴霖",
        "我帶著已確認的聖火線索返回鳴霖。",
        "你沒有替世界決定正式結局，而是把已成立的證據帶回鳴霖，準備讓下一章承接。",
        "demo_complete",
        "下一章待續",
        action_mode=ActionMode.MOVEMENT,
        destination_scene_id="minglin",
        special_scene_transition=True,
    ),
    _choice(
        "return_with_dust_findings",
        "demo_dust_complete",
        "liuchen_valley",
        "帶著流塵線索返回鳴霖",
        "我帶著已確認的流塵谷線索返回鳴霖。",
        "你沒有替世界決定正式結局，而是把已成立的證據帶回鳴霖，準備讓下一章承接。",
        "demo_complete",
        "下一章待續",
        action_mode=ActionMode.MOVEMENT,
        destination_scene_id="minglin",
        special_scene_transition=True,
    ),
    _choice(
        "review_demo_findings",
        "demo_complete",
        "minglin",
        "回報這次調查結果",
        "我把這次已記錄的調查結果告訴你，請協助整理。",
        "維達利亞只整理你實際建立的公開線索；尚未核准的推測、正式結局與其他角色秘密都保留到下一章。",
        "demo_complete",
        "下一章待續",
        action_mode=ActionMode.DIALOGUE,
        target_npc_id="vidalia",
    ),
    *_minglin_travel_choices("demo_complete"),
)


def available_demo_story_choices(state: GameState) -> tuple[DemoStoryChoiceDefinition, ...]:
    """Return at most four choices valid for the authoritative story position."""

    return tuple(
        choice
        for choice in DEMO_STORY_CHOICES
        if choice.source_node_id == state.story_progress.node_id
        and choice.source_scene_id == state.current_scene_id
    )[:4]


def find_available_demo_story_choice(
    state: GameState,
    choice_id: str,
) -> DemoStoryChoiceDefinition | None:
    return next(
        (
            choice
            for choice in available_demo_story_choices(state)
            if choice.choice_id == choice_id
        ),
        None,
    )


def find_demo_story_choice_definition(
    choice_id: str,
    source_scene_id: str,
) -> DemoStoryChoiceDefinition | None:
    """Find a definition after its node has advanced within the same event."""

    return next(
        (
            choice
            for choice in DEMO_STORY_CHOICES
            if choice.choice_id == choice_id
            and choice.source_scene_id == source_scene_id
        ),
        None,
    )
