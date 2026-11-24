"""Author-bounded fallback story choices for the Thursday demo.

The definitions provide a reliable path when the live model or RAG is unavailable.
They only combine facts already present in the supplied story background; every
state change still passes through the normal proposal resolver.
"""

from dataclasses import dataclass

from backend.content.characters import CHARACTER_PROFILES, npc_is_present
from backend.content.npc_dialogue import NPC_DIALOGUE_CHOICES
from backend.schemas.game_state import GameState
from backend.schemas.player_action import ActionMode
from backend.schemas.player_choice import PlayerChoice
from backend.rules.ending_rules import EndingRules


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
    rule_event_id: str | None = None
    witness_npc_ids: tuple[str, ...] = ()
    narrate_response: bool = False
    speaker_npc_id: str | None = None
    required_completed_choice_ids: tuple[str, ...] = ()
    epilogue_answer_key: str | None = None
    epilogue_answer_value: str | None = None
    rune_site: str | None = None  # E2-4：放置觀測符印的地點（寫入 flags["placed_runes"]，供之後拆除）
    # 觸發條件（規格 v3 事件清單）：全部符合才會出現
    min_relations: tuple[tuple[str, int], ...] = ()  # 例如 (("vidalia", 60),)
    axis_min: int | None = None
    axis_max: int | None = None
    required_any_flags: tuple[str, ...] = ()  # 任一旗標為真即可
    requires_placed_runes: bool = False
    once_group: str | None = None  # 同群組任一選項做過後，整組不再出現
    removes_placed_runes: bool = False  # 依已放置的符印數，每處套用一次 E2-4_remove
    ending_id: str | None = None

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
        "meet_andre",
        "fissure_arrival",
        "fissure",
        "與安德烈交談",
        "我和安德烈交談，請他帶我前往鳴霖。",
        "你醒在屏障裂隙邊。這裡不是適合久留的地方——跟我走，我帶你去鳴霖的議會。",
        "minglin_path_open",
        "鳴霖・未記載之物",
        action_mode=ActionMode.DIALOGUE,
        target_npc_id="andre",
        destination_scene_id="minglin",
    ),
    _choice(
        "meet_andre",
        "minglin_arrival",
        "minglin",
        "與安德烈交談",
        "我和安德烈交談，請告訴我接下來該怎麼走。",
        "你醒在鳴霖林間的入口。先別急著靠近議會庭——沿著前方的路走，等你看清這片森林，我再告訴你該找誰。",
        "minglin_path_open",
        "鳴霖・前往議會庭",
        action_mode=ActionMode.DIALOGUE,
        target_npc_id="andre",
    ),
    _choice(
        "walk_to_council",
        "minglin_path_open",
        "minglin",
        "沿著前方道路前進",
        "我沿著鳴霖前方的道路往前走。",
        "林霧在前方散開，一名金髮精靈站在議會庭的石環中央。她似乎早已察覺你的到來。",
        "minglin_council",
        "鳴霖・議會庭",
        action_mode=ActionMode.MOVEMENT,
    ),
    _choice(
        "meet_vidalia",
        "minglin_council",
        "minglin",
        "與維達利亞交談",
        "我向維達利亞說明自己剛才的遭遇，請她告訴我這裡是什麼地方。",
        "旅人，歡迎來到鳴霖。你身上的氣息沒有被命脈之泉記下；先告訴我，你在屏障裂隙看見了什麼？",
        "minglin_orientation",
        "鳴霖異象・調查委託",
        action_mode=ActionMode.DIALOGUE,
        target_npc_id="vidalia",
    ),
    _choice(
        "ask_location",
        "minglin_briefed",
        "minglin",
        "詢問目前所在地",
        "這裡是什麼地方？泉水和現在的異象有關嗎？",
        "這裡是鳴霖的平衡議會。命脈之泉已經很久沒有向外延伸；最近又出現異象，我還不知道兩者是否相關。",
        "minglin_briefed",
        "兩條調查路線",
        action_mode=ActionMode.DIALOGUE,
        target_npc_id="vidalia",
        reveal_clue_ids=("spring_stopped_expanding",),
    ),
    _choice(
        "ask_for_task",
        "minglin_orientation",
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
    _choice(
        "ask_about_anomaly",
        "minglin_briefed",
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
    _choice(
        "ask_about_factions",
        "minglin_briefed",
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
    _choice(
        "preview_border_ruins",
        "demo_complete",
        "minglin",
        "前往邊境廢墟",
        "我已走訪烈燚原和流塵谷，想去邊境廢墟看看。",
        "兩地的線索在邊境交會。殘破石門下，兩名旅人似乎正為各自的去路爭執。",
        "border_ruins_preview",
        "邊境的抉擇",
        action_mode=ActionMode.MOVEMENT,
        destination_scene_id="border_ruins",
        unlock_scene_ids=("border_ruins",),
        special_scene_transition=True,
    ),
    _choice(
        "return_from_border_ruins",
        "border_ruins_preview",
        "border_ruins",
        "返回鳴霖整理線索",
        "我先離開邊境廢墟，返回鳴霖。",
        "你暫時離開邊境廢墟，將已確認的相遇與線索帶回鳴霖。",
        "demo_complete",
        "下一章待續",
        action_mode=ActionMode.MOVEMENT,
        destination_scene_id="minglin",
        special_scene_transition=True,
    ),
    _choice(
        "border_help_both", "border_ruins_preview", "border_ruins",
        "協助塞特與希拉", "我決定協助塞特與希拉，讓兩人繼續前行。",
        "你決定協助塞特與希拉。裂隙拓印圖已收進背包，圖書館的路線成為可追查的線索。",
        "border_choice_resolved", "邊境抉擇：協助兩人",
        action_mode=ActionMode.DIALOGUE, target_npc_id="seth", rule_event_id="E2-3_help_both",
        witness_npc_ids=("seth", "syra"), narrate_response=True,
        reveal_clue_ids=("library_route_lead",),
    ),
    _choice(
        "border_report", "border_ruins_preview", "border_ruins",
        "選擇通報長老會", "我選擇向長老會通報這次邊境相遇。",
        "你選擇通報長老會，這次行動將沿長老協力的方向承接。你沒有取得裂隙拓印圖。",
        "border_choice_resolved", "邊境抉擇：長老協力",
        action_mode=ActionMode.DIALOGUE, target_npc_id="seth", rule_event_id="E2-3_report",
        witness_npc_ids=("seth", "syra"), narrate_response=True,
    ),
    _choice(
        "border_ignore", "border_ruins_preview", "border_ruins",
        "暫不介入兩人的處境", "我決定暫不介入兩人的處境。",
        "你暫不介入兩人的處境，沒有取得新的道具或路線。",
        "border_choice_resolved", "邊境抉擇：暫不介入",
        action_mode=ActionMode.DIALOGUE, target_npc_id="seth", rule_event_id="E2-3_ignore",
        witness_npc_ids=("seth", "syra"), narrate_response=True,
    ),
    _choice(
        "return_after_border_choice", "border_choice_resolved", "border_ruins",
        "帶著邊境的選擇返回鳴霖", "我帶著這次邊境的選擇返回鳴霖。",
        "你離開邊境廢墟。這次選擇與實際持有的物品會隨旅程保存。",
        "demo_complete", "邊境之後",
        action_mode=ActionMode.MOVEMENT, destination_scene_id="minglin", special_scene_transition=True,
    ),
    _choice(
        "enter_memory_library_with_map", "demo_complete", "minglin",
        "依裂隙拓印圖前往記憶圖書館", "我依照塞特與希拉交付的裂隙拓印圖前往記憶圖書館。",
        "裂隙拓印圖在暮光下顯出一條被抹去的路。石門之後，封存輪迴記錄的古老藏庫重新出現在你面前。",
        "memory_library_arrival", "記憶圖書館",
        action_mode=ActionMode.MOVEMENT, destination_scene_id="memory_library",
        unlock_scene_ids=("memory_library",), special_scene_transition=True,
        required_completed_choice_ids=("border_help_both",),
    ),
    _choice(
        "enter_memory_library_with_elders", "demo_complete", "minglin",
        "沿長老會檔案前往記憶圖書館", "我沿長老會留下的檔案索引前往記憶圖書館。",
        "通報換來的檔案只標出入口，沒有替你解釋其中內容。你穿過石門，獨自走進被暮光照亮的藏庫。",
        "memory_library_arrival", "記憶圖書館",
        action_mode=ActionMode.MOVEMENT, destination_scene_id="memory_library",
        unlock_scene_ids=("memory_library",), special_scene_transition=True,
        required_completed_choice_ids=("border_report",),
    ),
    _choice(
        "enter_memory_library_alone", "demo_complete", "minglin",
        "自行追蹤邊境殘痕", "我不依靠任何一方，自己追蹤邊境殘留的記憶痕跡。",
        "你花了更久才找出石門。沒有地圖也沒有引路人，只有沿途反覆出現的空白書頁指向古老藏庫。",
        "memory_library_arrival", "記憶圖書館",
        action_mode=ActionMode.MOVEMENT, destination_scene_id="memory_library",
        unlock_scene_ids=("memory_library",), special_scene_transition=True,
        required_completed_choice_ids=("border_ignore",),
    ),
    _choice(
        "inspect_life_death_book", "memory_library_arrival", "memory_library",
        "翻閱古老生死之書", "我翻閱石台上的生死之書，找自己的名字。",
        "書頁記得每一次埋葬與重生，輪到你時卻只剩空白。你不在這個世界原有的生死循環裡。",
        "memory_truth_a", "真相一：無名者",
        rule_event_id="Truth_A", reveal_clue_ids=("truth_a_blank_page",),
    ),
    _choice(
        "inspect_invasion_archive", "memory_library_arrival", "memory_library",
        "檢查千年前的入侵紀錄", "我檢查藏庫中被封存的第一次入侵紀錄。",
        "紀錄中的入侵者與你頸後的接縫完全一致。這場異象不是第一次發生，而你帶著同一來源的痕跡。",
        "memory_truth_b", "真相二：第一次入侵",
        rule_event_id="Truth_B", reveal_clue_ids=("truth_b_invasion_record",),
    ),
    _choice(
        "inspect_invasion_archive", "memory_truth_a", "memory_library",
        "對照千年前的入侵紀錄", "我把空白書頁與第一次入侵紀錄放在一起比對。",
        "紀錄中的入侵者與你頸後的接縫完全一致。空白不是遺漏，而是你來自這個輪迴之外的證據。",
        "memory_truth_ab", "兩份相合的真相",
        rule_event_id="Truth_B", reveal_clue_ids=("truth_b_invasion_record",),
    ),
    _choice(
        "inspect_life_death_book", "memory_truth_b", "memory_library",
        "以生死之書驗證紀錄", "我用生死之書驗證入侵紀錄裡的身分。",
        "書頁記得每一次埋葬與重生，輪到你時卻只剩空白。你確實不在這個世界原有的循環裡。",
        "memory_truth_ab", "兩份相合的真相",
        rule_event_id="Truth_A", reveal_clue_ids=("truth_a_blank_page",),
    ),
    _choice(
        "contact_alan_observer", "memory_truth_ab", "memory_library",
        "回應觀測者艾倫", "我回應藏庫中出現的外界通訊。",
        "觀測者艾倫承認：外界技術評議會把維塔的永生夢境當成可長期保存意識的資料系統，而你的進入重新啟動了被壓住的因果衝突。",
        "memory_truths_complete", "真相三：夢境之外",
        rule_event_id="Truth_C", reveal_clue_ids=("truth_c_alan_transmission",),
        speaker_npc_id="alan",
    ),
    _choice(
        "seek_menmesvento_after_truths", "memory_truths_complete", "memory_library",
        "帶著真相尋找門梅司文托", "我帶著三份真相前往流塵谷，尋找門梅司文托。",
        "門梅司文托讀完你帶來的紀錄，將一枚帶著灰燼裂痕的石牌放在生死之書旁，讓你決定是否收下。",
        "dust_token_offer", "門梅司文托的託付",
        action_mode=ActionMode.MOVEMENT, destination_scene_id="liuchen_valley",
        unlock_scene_ids=("liuchen_valley",), special_scene_transition=True,
    ),
    _choice(
        "accept_dust_return_token", "dust_token_offer", "liuchen_valley",
        "收下塵歸令", "我收下塵歸令，保留終止外來因果的選擇。",
        "門梅司文托把石牌交給你。它不會替你做決定，只會在維塔面前證明你願意承擔消失的代價。",
        "dust_token_decided", "塵歸令",
        action_mode=ActionMode.DIALOGUE, target_npc_id="menmesvento",
        witness_npc_ids=("menmesvento",), rule_event_id="E3-2_receive_dust_token",
    ),
    _choice(
        "decline_dust_return_token", "dust_token_offer", "liuchen_valley",
        "不收下塵歸令", "我不收下塵歸令，但會親自面對維塔。",
        "門梅司文托收回石牌，接受你的決定。通往命脈之泉源頭的路仍然為你開啟。",
        "dust_token_decided", "不以消失換取終結",
        action_mode=ActionMode.DIALOGUE, target_npc_id="menmesvento",
    ),
    _choice(
        "return_to_minglin_for_veta", "dust_token_decided", "liuchen_valley",
        "返回鳴霖尋找維塔", "我返回鳴霖，前往命脈之泉源頭。",
        "三份真相讓沉默的泉水重新顯出流向。維達利亞在議會前等你，沒有阻止你走向源頭。",
        "veta_route_ready", "命脈之泉源頭",
        action_mode=ActionMode.MOVEMENT, destination_scene_id="minglin",
        special_scene_transition=True,
    ),
    _choice(
        "enter_veta_source", "veta_route_ready", "minglin",
        "前往維塔沉眠之所", "我沿重新顯現的水脈前往維塔沉眠之所。",
        "古根與泉水在你面前分開。沉睡巨龍伏在石台上，意識越過夢境，向你提出最後三個問題。",
        "veta_question_one", "維塔三問：生命",
        action_mode=ActionMode.MOVEMENT, destination_scene_id="veta_source",
        unlock_scene_ids=("veta_source",), special_scene_transition=True,
    ),
    _choice(
        "veta_q1_each_life", "veta_question_one", "veta_source",
        "生命因只有一次而珍貴", "我回答維塔：生命因為終會結束，每一次選擇才真正重要。",
        "維塔聽見你承認死亡，也聽見你仍願意珍惜每一次存在。泉水向外流動了一步。",
        "veta_question_two", "維塔三問：記憶",
        speaker_npc_id="veta",
        rule_event_id="VETA_Q1_EACH_LIFE", epilogue_answer_key="answer_q1",
        epilogue_answer_value="生命因為終會結束，每一次選擇才真正重要。",
    ),
    _choice(
        "veta_q1_recurring_life", "veta_question_one", "veta_source",
        "延續本身也有價值", "我回答維塔：即使生命重複，延續與守護仍然有價值。",
        "維塔的夢安靜下來。你沒有否定輪迴中的感情，但也必須承擔停滯可能帶來的代價。",
        "veta_question_two", "維塔三問：記憶",
        speaker_npc_id="veta",
        rule_event_id="VETA_Q1_RECURRING", epilogue_answer_key="answer_q1",
        epilogue_answer_value="即使生命重複，延續與守護仍然有價值。",
    ),
    _choice(
        "veta_q2_remember", "veta_question_two", "veta_source",
        "記住痛苦，讓它成為見證", "我回答維塔：記憶即使痛苦，也不該被替他人抹去。",
        "被埋葬的名字沿泉水浮現。維塔讓你看見可用現有歷史承擔的最後選擇。",
        "veta_final_choice", "維塔三問：世界的去向",
        speaker_npc_id="veta",
        rule_event_id="VETA_Q2_REMEMBER", epilogue_answer_key="answer_q2",
        epilogue_answer_value="記憶即使痛苦，也不該被替他人抹去。",
    ),
    _choice(
        "veta_q2_release", "veta_question_two", "veta_source",
        "允許放下，但不能竄改", "我回答維塔：可以選擇放下痛苦，但不能把他人的歷史改成不存在。",
        "維塔接受遺忘也必須出於選擇。泉面映出你與兩位守護者共同改寫夢境的可能。",
        "veta_final_choice", "維塔三問：世界的去向",
        speaker_npc_id="veta",
        rule_event_id="VETA_Q2_RELEASE", epilogue_answer_key="answer_q2",
        epilogue_answer_value="可以選擇放下痛苦，但不能把他人的歷史改成不存在。",
    ),
    _choice(
        "veta_q2_control", "veta_question_two", "veta_source",
        "把記憶當成可以控制的資料", "我回答維塔：記憶只是可以重寫的資料，應由能掌控它的人決定。",
        "世界邊緣的裂痕同時張開。你把問答變成奪權宣告，維塔的控制權開始動搖。",
        "veta_usurp_warning", "篡夢警告",
        speaker_npc_id="veta",
        rule_event_id="VETA_Q2_CONTROL", epilogue_answer_key="answer_q2",
        epilogue_answer_value="記憶只是可以重寫的資料，應由能掌控它的人決定。",
    ),
    _choice(
        "confirm_usurp_after_warning", "veta_usurp_warning", "veta_source",
        "在五次警告脈衝後仍選擇奪權", "我理解警告，仍要在第五次脈衝後奪取維塔的控制權。",
        "五次警告脈衝逐一熄滅，你仍沒有退後。篡夢倒數啟動，其他世界去向隨控制權關閉。",
        "veta_final_choice", "維塔三問：世界的去向",
        speaker_npc_id="veta",
        rule_event_id="VETA_USURP_CONFIRM",
    ),
    _choice(
        "choose_long_sleep", "veta_final_choice", "veta_source",
        "讓維塔繼續長眠", "我選擇維持夢境，讓維塔繼續長眠。",
        "泉水恢復平靜，世界留在熟悉的輪迴中。你保住了夢，也接受它不再向外生長。",
        "ending_long_sleep", "結局：長眠", ending_id="長眠",
    ),
    _choice(
        "choose_wake", "veta_final_choice", "veta_source",
        "喚醒維塔", "我選擇喚醒維塔，讓這個世界接受死亡與真實。",
        "巨龍第一次睜開眼。輪迴停止替眾人逃避終點，而每一段生命也因此重新成為唯一。",
        "ending_wake", "結局：醒來", ending_id="醒來",
    ),
    _choice(
        "choose_new_dream", "veta_final_choice", "veta_source",
        "共同編織新夢", "我選擇與維塔和兩位守護者共同編織新的夢境。",
        "新夢不再抹除死亡與記憶，而讓每個人保有離開或留下的權利。舊輪迴從此成為可被選擇的道路。",
        "ending_new_dream", "結局：新夢", ending_id="新夢",
    ),
    _choice(
        "choose_dust_return", "veta_final_choice", "veta_source",
        "啟動塵歸令", "我選擇啟動塵歸令，從夢境中抹除外來因果。",
        "石牌化為灰燼。你的痕跡從因果中退去，維塔與三族得到一個不再被外界重啟的未來。",
        "ending_dust_return", "結局：塵歸", ending_id="塵歸",
    ),
    _choice(
        "choose_usurp", "veta_final_choice", "veta_source",
        "奪取維塔的夢", "我選擇奪取維塔的控制權，讓夢境服從我的意志。",
        "你取代沉睡巨龍成為夢的控制者。世界得以延續，代價是所有記憶都開始依附你的意志。",
        "ending_usurp", "結局：篡夢", ending_id="篡夢",
    ),
    # -----------------------------------------------------------------
    # 階段二選做支線：解決邊境廢墟後、進入記憶圖書館前，可回到三處各做一次。
    # 規格 v3 E2-1 抽泉裝置試運轉、E2-4 觀測符印（命脈之泉／流塵谷地脈裂隙／聖火反應爐）。
    # 艾倫此時尚未曝光身分，只以「視網膜上的字」出現。
    # -----------------------------------------------------------------
    _choice(
        "side_spring_anomaly", "demo_complete", "minglin",
        "回命脈之泉查看異常", "我回命脈之泉看看泉水的異常。",
        "泉眼旁的岩縫裡多了一具陌生的金屬裝置，管線深深插進泉脈，正一下一下地抽動。裝置上刻著烈燚原長老會能源長老的印記。",
        "side_spring_pump", "泉脈裡的裝置",
        action_mode=ActionMode.MOVEMENT, destination_scene_id="minglin_life_spring",
    ),
    _choice(
        "pump_prevent", "side_spring_pump", "minglin_life_spring",
        "拆下裝置並告訴安德烈", "我把這具裝置拆下來，並把它的來歷告訴安德烈。",
        "你切斷管線，把裝置拖離泉眼。安德烈聽完你的說明，沉默地收起那枚長老會的印記：「這件事，我會讓平衡議會知道。」"
        "這時，視網膜上浮現一行字：「在泉眼放下觀測符印，這是修復世界的步驟。」",
        "side_spring_rune", "泉眼旁的訊號", rule_event_id="E2-1_prevent", narrate_response=True,
    ),
    _choice(
        "pump_assist", "side_spring_pump", "minglin_life_spring",
        "協助長老校準裝置", "我照長老會的刻痕，幫忙把裝置校準。",
        "你依著刻痕調整閥門，裝置的抽動變得平穩而有力。泉水的聲音更低了，岩縫深處傳來長老會的回應訊號——他們記下了你的協力。"
        "這時，視網膜上浮現一行字：「在泉眼放下觀測符印，這是修復世界的步驟。」",
        "side_spring_rune", "泉眼旁的訊號", rule_event_id="E2-1_assist", narrate_response=True,
    ),
    _choice(
        "pump_ignore", "side_spring_pump", "minglin_life_spring",
        "不碰這具裝置", "我不碰這具裝置，先把它留在原地。",
        "你沒有碰那具裝置。它在你身後繼續抽動，泉水的流聲一點一點變得遙遠。"
        "這時，視網膜上浮現一行字：「在泉眼放下觀測符印，這是修復世界的步驟。」",
        "side_spring_rune", "泉眼旁的訊號", rule_event_id="E2-1_ignore", narrate_response=True,
    ),
    _choice(
        "rune_place_spring", "side_spring_rune", "minglin_life_spring",
        "在泉眼放下觀測符印", "我照視網膜上的指示，在泉眼放下觀測符印。",
        "符印貼上泉眼的岩面，微光沿著水脈滲了下去。視網膜角落的數字輕輕跳動了一下。你沿林道回到鳴霖。",
        "demo_complete", "邊境之後", rule_event_id="E2-4_place", rune_site="minglin_life_spring",
        action_mode=ActionMode.MOVEMENT, destination_scene_id="minglin", narrate_response=True,
    ),
    _choice(
        "rune_refuse_spring", "side_spring_rune", "minglin_life_spring",
        "拒絕在泉眼放下符印", "我不打算在泉眼放下這種東西。",
        "視網膜上的字停了一會兒，才換成較溫和的語氣：「那只是觀測用的標記，不會傷害任何人。」你沒有回應，沿林道回到鳴霖。",
        "demo_complete", "邊境之後", rule_event_id="E2-4_refuse",
        action_mode=ActionMode.MOVEMENT, destination_scene_id="minglin", narrate_response=True,
    ),
    _choice(
        "side_fire_reactor", "demo_complete", "minglin",
        "前往烈燚原的聖火反應爐", "我再去一趟烈燚原，看看聖火反應爐。",
        "你再次踏進烈燚原。聖火反應爐的熱浪撲面而來，爐壁上的紋路與泉眼旁那具裝置如出一轍。"
        "視網膜上浮現一行字：「在反應爐放下觀測符印，這是修復世界的步驟。」",
        "side_fire_rune", "聖火反應爐",
        action_mode=ActionMode.MOVEMENT, destination_scene_id="lieyi_plains", special_scene_transition=True,
    ),
    _choice(
        "rune_place_fire", "side_fire_rune", "lieyi_plains",
        "在反應爐放下觀測符印", "我照視網膜上的指示，在聖火反應爐放下觀測符印。",
        "符印貼上滾燙的爐壁，沒有被火焰吞沒，反而讓火光短暫地停頓了一瞬。視網膜角落的數字輕輕跳動了一下。你離開烈燚原，回到鳴霖。",
        "demo_complete", "邊境之後", rule_event_id="E2-4_place", rune_site="lieyi_plains",
        action_mode=ActionMode.MOVEMENT, destination_scene_id="minglin", special_scene_transition=True,
        narrate_response=True,
    ),
    _choice(
        "rune_refuse_fire", "side_fire_rune", "lieyi_plains",
        "拒絕在反應爐放下符印", "我不打算在聖火反應爐放下這種東西。",
        "視網膜上的字閃了閃：「只是一個標記而已，你在擔心什麼？」你沒有回應，離開烈燚原回到鳴霖。",
        "demo_complete", "邊境之後", rule_event_id="E2-4_refuse",
        action_mode=ActionMode.MOVEMENT, destination_scene_id="minglin", special_scene_transition=True,
        narrate_response=True,
    ),
    _choice(
        "side_dust_fissure", "demo_complete", "minglin",
        "前往流塵谷的地脈裂隙", "我再去一趟流塵谷，看看地脈裂隙。",
        "你再次走進流塵谷。風沙在一道地脈裂隙前打著旋，裂隙深處傳來與泉眼相同的低鳴。"
        "視網膜上浮現一行字：「在裂隙放下觀測符印，這是修復世界的步驟。」",
        "side_dust_rune", "地脈裂隙",
        action_mode=ActionMode.MOVEMENT, destination_scene_id="liuchen_valley", special_scene_transition=True,
    ),
    _choice(
        "rune_place_dust", "side_dust_rune", "liuchen_valley",
        "在裂隙放下觀測符印", "我照視網膜上的指示，在地脈裂隙放下觀測符印。",
        "符印沉進裂隙的陰影裡，周圍的風沙忽然安靜下來。視網膜角落的數字輕輕跳動了一下。你離開流塵谷，回到鳴霖。",
        "demo_complete", "邊境之後", rule_event_id="E2-4_place", rune_site="liuchen_valley",
        action_mode=ActionMode.MOVEMENT, destination_scene_id="minglin", special_scene_transition=True,
        narrate_response=True,
    ),
    _choice(
        "rune_refuse_dust", "side_dust_rune", "liuchen_valley",
        "拒絕在裂隙放下符印", "我不打算在地脈裂隙放下這種東西。",
        "視網膜上的字沉默了片刻：「你遲早會明白這是必要的步驟。」你沒有回應，離開流塵谷回到鳴霖。",
        "demo_complete", "邊境之後", rule_event_id="E2-4_refuse",
        action_mode=ActionMode.MOVEMENT, destination_scene_id="minglin", special_scene_transition=True,
        narrate_response=True,
    ),
)


_E3_CHOICES = (
    # -----------------------------------------------------------------
    # 階段三：真相之後、前往維塔之前的事件（規格 v3 E3-2～E3-4、真相 C 後拒絕艾倫、拆除符印）
    # 關係值門檻主要靠敘事 AI 判讀對話累積；條件不符時不會出現，不影響主線。
    # -----------------------------------------------------------------
    _choice(
        "reject_alan_after_truths", "memory_truths_complete", "memory_library",
        "明確拒絕艾倫", "我不會再替外界評議會做任何事，艾倫。",
        "通訊另一端安靜了很久。艾倫最後只留下一句：「你會後悔的。」視網膜上的數字停止跳動，雜音一點一點退去。",
        "memory_truths_complete", "真相三：夢境之外", rule_event_id="Truth_C_reject_alan",
        narrate_response=True, once_group="reject_alan",
    ),
    _choice(
        "agree_wake_veta", "dust_token_decided", "liuchen_valley",
        "答應他喚醒維塔的請求", "我答應你，會去喚醒維塔。",
        "門梅司文托閉上眼，像是終於放下了千年的重量：「那就去吧。讓他醒來，親眼看看這個世界。」",
        "dust_token_decided", "門梅司文托的請求", rule_event_id="E3-2_agree",
        action_mode=ActionMode.DIALOGUE, target_npc_id="menmesvento", witness_npc_ids=("menmesvento",),
        min_relations=(("menmesvento", 60),), once_group="e3_2",
    ),
    _choice(
        "refuse_wake_veta", "dust_token_decided", "liuchen_valley",
        "婉拒他喚醒維塔的請求", "這件事，我還不能答應你。",
        "門梅司文托沒有追問，只是把視線移回生死之書：「無妨。每個人都該自己決定要叫醒誰。」",
        "dust_token_decided", "門梅司文托的請求",
        action_mode=ActionMode.DIALOGUE, target_npc_id="menmesvento", witness_npc_ids=("menmesvento",),
        min_relations=(("menmesvento", 60),), once_group="e3_2",
    ),
    # E3-3 維達利亞的感情節點：依主軸三選一，只發生一次
    _choice(
        "vidalia_offer_weaving", "veta_route_ready", "minglin",
        "聽維達利亞想說的話", "維達利亞，妳想對我說什麼？",
        "維達利亞的聲音比平常輕：「留下來吧。我可以用織夢術讓你成為精靈，從此不必再回到那個會死去的世界。」"
        "她頓了頓，又說：「但你要想清楚，一旦織成，就再也回不去了。」",
        "side_vidalia_offer", "織夢之約",
        action_mode=ActionMode.DIALOGUE, target_npc_id="vidalia",
        min_relations=(("vidalia", 60),), axis_max=-20, once_group="e3_3",
    ),
    _choice(
        "accept_dream_weaving", "side_vidalia_offer", "minglin",
        "接受織夢，成為精靈", "我願意留下來，成為精靈。",
        "維達利亞牽起你的手，林間的霧絲纏上你的指尖。等霧散去，你聽見的風聲已經和她一樣。你成了鳴霖的精靈，再也不是外來者。",
        "veta_route_ready", "命脈之泉源頭", rule_event_id="E3-3_accept_transformation",
        action_mode=ActionMode.DIALOGUE, target_npc_id="vidalia",
    ),
    _choice(
        "decline_dream_weaving", "side_vidalia_offer", "minglin",
        "婉拒織夢", "謝謝妳，但我還不能留下。",
        "維達利亞收回手，笑得有些勉強：「我知道。只是……想問問看而已。」",
        "veta_route_ready", "命脈之泉源頭",
        action_mode=ActionMode.DIALOGUE, target_npc_id="vidalia",
    ),
    _choice(
        "vidalia_confides_wavering", "veta_route_ready", "minglin",
        "聽維達利亞想說的話", "維達利亞，妳想對我說什麼？",
        "維達利亞望著議會庭外的雨霧，很久才開口：「我一直以為，只要什麼都不改變就好。可是看著你，我開始不確定了……我其實不想讓這個世界改變，這樣是錯的嗎？」",
        "veta_route_ready", "命脈之泉源頭",
        action_mode=ActionMode.DIALOGUE, target_npc_id="vidalia",
        min_relations=(("vidalia", 60),), axis_min=20, once_group="e3_3",
    ),
    _choice(
        "vidalia_asks_outside", "veta_route_ready", "minglin",
        "聽維達利亞想說的話", "維達利亞，妳想對我說什麼？",
        "維達利亞歪著頭看你：「外面的世界是什麼樣子？那裡的雨，也會這樣下個不停嗎？」你說起那個一切都會結束的世界，她安靜地聽到最後。",
        "veta_route_ready", "命脈之泉源頭",
        action_mode=ActionMode.DIALOGUE, target_npc_id="vidalia",
        min_relations=(("vidalia", 60),), axis_min=-19, axis_max=19, once_group="e3_3",
    ),
    _choice(
        "andre_shows_breach", "veta_route_ready", "minglin",
        "跟安德烈去看屏障裂縫", "安德烈，你想給我看什麼？",
        "安德烈帶你回到屏障破裂的地方。裂縫比你醒來那天寬了許多，邊緣還在緩慢地剝落。「我查過了，」他說，「裂縫開始擴大的時間，和你出現的那天完全吻合。」"
        "他另外告訴你，裂縫附近有一處隱藏的採集洞穴，危急時可以躲進去。",
        "veta_route_ready", "命脈之泉源頭", rule_event_id="E3-4",
        action_mode=ActionMode.DIALOGUE, target_npc_id="andre",
        min_relations=(("andre", 60),), once_group="e3_4",
    ),
    _choice(
        "remove_placed_runes", "veta_route_ready", "minglin",
        "拆除各地的觀測符印", "我要把先前放下的觀測符印全部拆掉。",
        "你回到每一處放過符印的地方，把它們一一剝下。符印離開岩面時發出細微的碎裂聲，視網膜角落的數字也跟著往回跳。",
        "veta_route_ready", "命脈之泉源頭", narrate_response=True,
        requires_placed_runes=True, required_any_flags=("warning_event_done", "truth_c_unlocked"),
        removes_placed_runes=True, once_group="remove_runes",
    ),
)

DEMO_STORY_CHOICES = DEMO_STORY_CHOICES + _E3_CHOICES

# 一次性群組：同群組任一選項做過後，整組不再出現
ONCE_GROUP_MEMBERS: dict[str, frozenset[str]] = {
    group: frozenset(choice.choice_id for choice in DEMO_STORY_CHOICES if choice.once_group == group)
    for group in {choice.once_group for choice in DEMO_STORY_CHOICES if choice.once_group}
}


def _choice_conditions_met(choice: DemoStoryChoiceDefinition, state: GameState, completed: set[str]) -> bool:
    """規格 v3 事件的觸發條件：關係值、主軸、旗標、已放置的符印與一次性。"""

    for npc_id, minimum in choice.min_relations:
        npc = state.npc_states.get(npc_id)
        if npc is None or npc.relation < minimum:
            return False
    if choice.axis_min is not None and state.axis < choice.axis_min:
        return False
    if choice.axis_max is not None and state.axis > choice.axis_max:
        return False
    if choice.required_any_flags and not any(state.flags.get(flag) for flag in choice.required_any_flags):
        return False
    if choice.requires_placed_runes and not state.flags.get("placed_runes"):
        return False
    if choice.once_group and ONCE_GROUP_MEMBERS[choice.once_group] & completed:
        return False
    return True


# 階段二選做支線的入口；每處只能去一次，只在解決邊境廢墟之後出現
SIDE_EVENT_ENTRY_IDS = frozenset(("side_spring_anomaly", "side_fire_reactor", "side_dust_fissure"))

# 警告事件 W（規格 v3）：篡奪值第一次達 75 後強制發生，不屬於任何固定節點
WARNING_RULE_IDS = frozenset(("W", "W_expose_elders"))

BORDER_RULE_IDS = frozenset(("E2-3_help_both", "E2-3_report", "E2-3_ignore"))
BORDER_RESOLUTION_IDS = frozenset(choice.choice_id for choice in DEMO_STORY_CHOICES if choice.rule_event_id in BORDER_RULE_IDS)
MEMORY_LIBRARY_ENTRY_IDS = frozenset(
    ("enter_memory_library_with_map", "enter_memory_library_with_elders", "enter_memory_library_alone")
)
AUTHORED_RULE_IDS = frozenset(
    choice.rule_event_id for choice in DEMO_STORY_CHOICES if choice.rule_event_id
) | WARNING_RULE_IDS


def pending_warning_choices(state: GameState) -> tuple[DemoStoryChoiceDefinition, ...]:
    """警告事件 W：篡奪值第一次達 75 後的下一回合強制出現，只發生一次。

    維塔源頭有自己的篡夢警告流程（veta_usurp_warning），那裡不另外插入 W。
    """

    node_id = state.story_progress.node_id
    if (
        state.game_status != "active"
        or not state.warning_triggered
        or state.flags.get("warning_event_done")
        or node_id.startswith("veta_")
    ):
        return ()
    guide_id = max(
        (npc_id for npc_id in ("andre", "vidalia", "menmesvento") if npc_id in state.npc_states),
        key=lambda npc_id: state.npc_states[npc_id].relation,
    )
    guide = CHARACTER_PROFILES[guide_id].name
    sight = (
        f"{guide}帶你走到林地邊緣。樹幹表面泛著金屬的冷光，泉水沿著溝渠倒流回源頭。"
        f"{guide}看著你：「異象是從你去過的地方開始的。」"
    )
    chapter = state.story_progress.chapter_title
    return (
        _choice(
            "warning_witness", node_id, state.current_scene_id,
            "記下眼前的異象", "我記下眼前的異象，沒有多說什麼。",
            sight + "你把這一幕記在心裡。若那些符印真與異象有關，現在拆除還來得及。",
            node_id, chapter, rule_event_id="W", narrate_response=True,
        ),
        _choice(
            "warning_expose_elders", node_id, state.current_scene_id,
            "當場揭發長老會", "我把長老會在各地動的手腳全部說出來。",
            sight + "你說出長老會的裝置與他們的打算。消息很快傳開，長老會不得不暫時收手。",
            node_id, chapter, rule_event_id="W_expose_elders", narrate_response=True,
        ),
    )


def available_demo_story_choices(state: GameState) -> tuple[DemoStoryChoiceDefinition, ...]:
    """Return at most four choices valid for the authoritative story position."""

    if state.game_status != "active":
        return ()
    warning = pending_warning_choices(state)
    if warning:
        return warning
    completed = set(state.story_progress.completed_choice_ids)
    visited_both_regions = {"enter_lieyi_plains", "enter_liuchen_valley"}.issubset(
        completed
    )
    border_resolution = BORDER_RESOLUTION_IDS.intersection(completed)
    available_endings = set(EndingRules.evaluate_available_endings(state))
    available = tuple(
        choice
        for choice in DEMO_STORY_CHOICES
        if choice.source_node_id == state.story_progress.node_id
        and choice.source_scene_id == state.current_scene_id
        and (
            choice.choice_id != "preview_border_ruins"
            or (visited_both_regions and not border_resolution)
        )
        and (choice.choice_id not in BORDER_RESOLUTION_IDS or not border_resolution)
        and set(choice.required_completed_choice_ids).issubset(completed)
        and (
            not border_resolution
            or state.story_progress.node_id != "demo_complete"
            or choice.choice_id in MEMORY_LIBRARY_ENTRY_IDS
            or choice.choice_id in SIDE_EVENT_ENTRY_IDS
        )
        and (
            choice.choice_id not in SIDE_EVENT_ENTRY_IDS
            or (border_resolution and choice.choice_id not in completed)
        )
        and (choice.ending_id is None or choice.ending_id in available_endings)
        and _choice_conditions_met(choice, state, completed)
        and not (
            state.story_progress.node_id == "minglin_briefed"
            and choice.destination_scene_id is None
            and choice.choice_id in completed
        )
    )
    if state.story_progress.node_id == "minglin_briefed":
        # Once the task is accepted, put the two authored destinations first;
        # optional follow-up questions must not hide the investigation routes.
        available = tuple(
            sorted(available, key=lambda choice: choice.destination_scene_id is None)
        )
    return available[:4]


def available_npc_dialogue_choices(state: GameState, npc_id: str) -> tuple[DemoStoryChoiceDefinition, ...]:
    """Fixed replies preserve the current scene, story node and item ownership."""
    if not npc_is_present(npc_id, state.current_scene_id):
        return ()
    if npc_id == "vidalia" and state.current_scene_id == "minglin":
        return ()  # Council dialogue already belongs to the story definitions.
    return tuple(
        _choice(
            definition.choice_id, state.story_progress.node_id, state.current_scene_id,
            definition.label, definition.message, definition.response_text,
            state.story_progress.node_id, state.story_progress.chapter_title,
            action_mode=ActionMode.DIALOGUE, target_npc_id=npc_id,
        )
        for definition in NPC_DIALOGUE_CHOICES.get(npc_id, ())
    )


def find_available_demo_story_choice(
    state: GameState,
    choice_id: str,
) -> DemoStoryChoiceDefinition | None:
    return next(
        (
            choice
            for choice in (
                *available_demo_story_choices(state),
                *(choice for npc_id in NPC_DIALOGUE_CHOICES
                  for choice in available_npc_dialogue_choices(state, npc_id)),
            )
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
