"""Author-bounded fallback story choices for the Thursday demo.

The definitions provide a reliable path when the live model or RAG is unavailable.
They only combine facts already present in the supplied story background; every
state change still passes through the normal proposal resolver.
"""

from dataclasses import dataclass

from backend.content.characters import npc_is_present
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
    ending_id: str | None = None
    emotion: str | None = None

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
        "你決定協助塞特與希拉。裂隙地圖已收進背包，圖書館的路線成為可追查的線索。",
        "border_choice_resolved", "邊境抉擇：協助兩人",
        action_mode=ActionMode.DIALOGUE, target_npc_id="seth", rule_event_id="E2-3_help_both",
        witness_npc_ids=("seth", "syra"), narrate_response=True,
        reveal_clue_ids=("library_route_lead",),
    ),
    _choice(
        "border_report", "border_ruins_preview", "border_ruins",
        "選擇通報長老會", "我選擇向長老會通報這次邊境相遇。",
        "你選擇通報長老會，這次行動將沿長老協力的方向承接。你沒有取得裂隙地圖。",
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
        "依裂隙地圖前往記憶圖書館", "我依照塞特與希拉交付的裂隙地圖前往記憶圖書館。",
        "裂隙地圖在暮光下顯出一條被抹去的路。石門之後，封存輪迴記錄的古老藏庫重新出現在你面前。",
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
)

BORDER_RULE_IDS = frozenset(("E2-3_help_both", "E2-3_report", "E2-3_ignore"))
BORDER_RESOLUTION_IDS = frozenset(choice.choice_id for choice in DEMO_STORY_CHOICES if choice.rule_event_id in BORDER_RULE_IDS)
MEMORY_LIBRARY_ENTRY_IDS = frozenset(
    ("enter_memory_library_with_map", "enter_memory_library_with_elders", "enter_memory_library_alone")
)
AUTHORED_RULE_IDS = frozenset(
    choice.rule_event_id for choice in DEMO_STORY_CHOICES if choice.rule_event_id
)


def available_demo_story_choices(state: GameState) -> tuple[DemoStoryChoiceDefinition, ...]:
    """Return at most four choices valid for the authoritative story position."""

    if state.game_status != "active":
        return ()
    completed = set(state.story_progress.completed_choice_ids)
    visited_both_regions = {"enter_lieyi_plains", "enter_liuchen_valley"}.issubset(
        completed
    )
    border_resolution = BORDER_RESOLUTION_IDS.intersection(completed)
    available_endings = set(EndingRules.evaluate_available_endings(state))
    return tuple(
        choice
        for choice in DEMO_STORY_CHOICES
        if choice.source_node_id == state.story_progress.node_id
        and choice.source_scene_id == state.current_scene_id
        and (choice.choice_id != "preview_border_ruins" or (visited_both_regions and not border_resolution))
        and (choice.choice_id not in BORDER_RESOLUTION_IDS or not border_resolution)
        and set(choice.required_completed_choice_ids).issubset(completed)
        and (not border_resolution or state.story_progress.node_id != "demo_complete" or choice.choice_id in MEMORY_LIBRARY_ENTRY_IDS)
        and (choice.ending_id is None or choice.ending_id in available_endings)
    )[:4]


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
            emotion=definition.emotion,
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
