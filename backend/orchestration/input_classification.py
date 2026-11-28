"""Small deterministic helpers for routing player text safely."""

import re
import unicodedata


_EDGE_PUNCTUATION = "。．.!！?？,，、:：;；『』「」\"'“”‘’（）()【】[]"
_CLAUSE_BOUNDARY = re.compile(r"[。．.!！?？,，、:：;；]\s*")
_NEGATION_IN_CLAUSE = re.compile(
    r"(?:別|别|无须|無須|无需|無需|不用|不要|不想|不會|不会|不能|"
    r"不願|不愿|不打算|不準備|不准备|不答應|不答应|不承諾|不承诺|"
    r"不是|沒要|没要|沒有|没有|並非|并非|拒絕|拒绝|婉拒)"
)


def normalize_authored_choice_text(value: str) -> str:
    """Normalize harmless transcription differences without fuzzy matching.

    Authored story choices still require the same text after Unicode,
    whitespace, case, and surrounding-punctuation normalization.  Words are
    never added, removed, or semantically inferred here.
    """

    normalized = unicodedata.normalize("NFKC", value).casefold()
    normalized = normalized.strip(f" \t\r\n{_EDGE_PUNCTUATION}")
    return re.sub(r"\s+", "", normalized)


def contains_non_negated_phrase(text: str, phrases: tuple[str, ...]) -> bool:
    """Return true when at least one phrase is not immediately negated."""

    normalized = unicodedata.normalize("NFKC", text).casefold()
    for phrase in phrases:
        candidate = unicodedata.normalize("NFKC", phrase).casefold()
        start = 0
        while True:
            index = normalized.find(candidate, start)
            if index < 0:
                break
            prefix = _CLAUSE_BOUNDARY.split(normalized[:index])[-1]
            directly_negated = prefix.rstrip().endswith(("不", "沒", "没"))
            if not directly_negated and _NEGATION_IN_CLAUSE.search(prefix) is None:
                return True
            start = index + len(candidate)
    return False


def explicitly_requests_authored_event(choice_id: str, text: str) -> bool:
    """Recognize explicit Act 3 dialogue intents before asking AI to review them.

    Only these authored dialogue actions may be inferred. Scene travel, rune
    removal, the pre-Veta ±20 stances, and endings still require their buttons.
    The AI must independently confirm the matching label before any event runs.
    """

    normalized = unicodedata.normalize("NFKC", text).casefold()

    def mentions(*phrases: str) -> bool:
        return any(phrase in normalized for phrase in phrases)

    if choice_id == "accept_dust_return_token":
        return mentions("塵歸令", "石牌") and contains_non_negated_phrase(
            normalized, ("收下", "接受", "拿起")
        )
    if choice_id == "decline_dust_return_token":
        return mentions("塵歸令", "石牌") and mentions(
            "不收", "不要", "拒絕", "不能接受", "不願接受"
        )
    if choice_id == "agree_wake_veta":
        return (
            contains_non_negated_phrase(normalized, ("答應", "同意", "願意"))
            and contains_non_negated_phrase(
                normalized, ("喚醒維塔", "叫醒維塔", "讓維塔醒來")
            )
        )
    if choice_id == "refuse_wake_veta":
        return mentions("喚醒維塔", "叫醒維塔", "讓維塔醒來") and mentions(
            "不答應", "不會", "不願", "不想", "拒絕", "不能答應"
        )
    if choice_id in {
        "vidalia_offer_weaving", "vidalia_confides_wavering", "vidalia_asks_outside"
    }:
        return (
            mentions("維達利亞", "妳", "你")
            and mentions("想對我說", "有話對我說", "想說的話", "心事")
            and contains_non_negated_phrase(normalized, ("說", "聊", "聽"))
        )
    if choice_id == "accept_dream_weaving":
        return mentions("織夢", "精靈") and contains_non_negated_phrase(
            normalized, ("接受", "答應", "願意", "想變成", "成為")
        )
    if choice_id == "decline_dream_weaving":
        return mentions("織夢", "精靈") and mentions(
            "不接受", "不能接受", "拒絕", "不願", "不想"
        )
    if choice_id == "andre_shows_breach":
        return mentions("裂縫", "屏障") and contains_non_negated_phrase(
            normalized, ("帶我去看", "去看", "一起看", "看看", "瞧瞧")
        )
    return False
