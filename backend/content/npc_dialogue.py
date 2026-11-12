"""Prepared public replies; no model call or private character facts required."""

from dataclasses import dataclass


@dataclass(frozen=True)
class NPCDialogueDefinition:
    choice_id: str
    label: str
    message: str
    response_text: str


_ELDER_REPLY = "聖火與長老會的事，得依現場證據談。你看見了什麼異常？"
_SETH_REPLY = "風把每條路都吹得模糊。我還在找能走出去的方向。"
_SYRA_REPLY = "這只盒子裝著我不想遺失的記錄。其他事，等我確定能信任你再說。"

NPC_DIALOGUE_CHOICES = {
    "vidalia": (
        NPCDialogueDefinition("vidalia_ask_spring", "詢問泉水的變化", "泉水最近有什麼能確認的變化？",
            "命脈之泉已經很久沒有向外延伸；最近又出現異象，我還不知道兩者是否相關。"),
        NPCDialogueDefinition("vidalia_ask_inspection", "詢問如何調查泉眼", "在泉眼附近應該先觀察什麼？",
            "先在岸邊查探灰燼與裂響，記下親眼確認的痕跡，再根據結果比對。"),
    ),
    "andre": (
        NPCDialogueDefinition("andre_ask_anomaly", "詢問林地異象", "你在林地邊緣觀察到什麼異象？",
            "林地邊緣的地脈最近有幾次不尋常的震顫，泉水也久未向外延伸。我正在核對兩者是否相關。"),
        NPCDialogueDefinition("andre_ask_trail", "詢問調查路線", "我可以從哪裡開始調查？",
            "先去命脈之泉與符石林看看。把你親眼確認的變化記下來，回來再與我比對。"),
    ),
    "menmesvento": (
        NPCDialogueDefinition("menmesvento_ask_names", "詢問流塵谷的名字", "為什麼這裡的人如此重視名字？",
            "這裡的風很快就會抹去足跡。有些人只盼自己的名字仍有人願意聽見；先聽他們說吧。"),
        NPCDialogueDefinition("menmesvento_ask_record", "詢問手中的古卷", "你在古卷裡記錄什麼？",
            "我記下願意留下的名字與親眼可證的往事。書頁上還有許多未釐清的痕跡，現在不能把猜測當成答案。"),
    ),
    "dasso": (
        NPCDialogueDefinition("dasso_ask_1", "詢問聖火", "這裡的聖火目前有什麼異常？", _ELDER_REPLY),
        NPCDialogueDefinition("dasso_ask_2", "詢問長老會", "長老會正在調查什麼？", _ELDER_REPLY),
    ),
    "seth": (
        NPCDialogueDefinition("seth_ask_1", "詢問去向", "你想往哪個方向走？", _SETH_REPLY),
        NPCDialogueDefinition("seth_ask_2", "詢問風沙", "流塵谷最近的風沙有什麼變化？", _SETH_REPLY),
    ),
    "syra": (
        NPCDialogueDefinition("syra_ask_1", "詢問記錄盒", "你懷裡的記錄盒是做什麼的？", _SYRA_REPLY),
        NPCDialogueDefinition("syra_ask_2", "詢問旅途", "你是怎麼來到流塵谷的？", _SYRA_REPLY),
    ),
}

NPC_DIALOGUE_BY_ID = {
    choice.choice_id: choice
    for choices in NPC_DIALOGUE_CHOICES.values()
    for choice in choices
}
