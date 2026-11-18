"""Small deterministic helpers for routing player text safely."""

import re
import unicodedata


_EDGE_PUNCTUATION = "。．.!！?？,，、:：;；『』「」\"'“”‘’（）()【】[]"
_CLAUSE_BOUNDARY = re.compile(r"[。．.!！?？,，、:：;；]\s*")
_NEGATION_IN_CLAUSE = re.compile(
    r"(?:別|别|无须|無須|无需|無需|不用|不要|不想|不會|不会|不能|"
    r"不願|不愿|不打算|不準備|不准备|不答應|不答应|不承諾|不承诺|"
    r"不是|沒要|没要|沒有|没有|並非|并非)"
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
