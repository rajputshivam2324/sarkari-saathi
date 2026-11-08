"""Post-processing for LLM replies: make them speakable, then refuse anything unverifiable.

A prompt asks the model to behave; this module checks that it did. A reply that fails is
dropped and the caller uses the rule-based dialogue instead, so a bad generation never reaches
the person (or the text-to-speech engine).

Checks are deliberately conservative and cheap. They are a safety net, not a replacement for
the prompt.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from app.schemes_data import SCHEMES

MAX_WORDS = 60
ALWAYS_OK_NUMBERS = {112}  # national emergency number: the prompt tells the model to say it

# ----- cleaning -------------------------------------------------------------------------
_URL = re.compile(r"(?:https?://|www\.)\S+|\b[\w\-]+\.(?:gov|nic)\.in\S*", re.IGNORECASE)
_EMOJI = re.compile("[\U0001F300-\U0001FAFF\u2600-\u27BF\uFE0F\u200d]")
_MD = re.compile(r"[*_`#>~|]+")
_LIST_PREFIX = re.compile(r"^\s*(?:[-•·▪●]|\(?\d{1,2}[.)])\s+", re.MULTILINE)
_ROLE_LABEL = re.compile(r"^\s*(?:sarkari saathi|सरकारी साथी|assistant|saathi|ai)\s*[:：\-]\s*", re.IGNORECASE)
_SENT_SPLIT = re.compile(r"(?<=[.!?।॥])\s+")


def clean_for_speech(text: str) -> str:
    t = (text or "").strip()
    t = _ROLE_LABEL.sub("", t)
    t = _URL.sub("", t)
    t = _EMOJI.sub("", t)
    t = _LIST_PREFIX.sub("", t)
    t = _MD.sub("", t)
    t = re.sub(r"\(\s*\)", "", t)
    t = re.sub(r"\s*\n+\s*", " ", t)
    t = re.sub(r"\s{2,}", " ", t).strip()
    if len(t) >= 2 and t[0] in "\"'“‘" and t[-1] in "\"'”’":
        t = t[1:-1].strip()
    return t


def _sentences(text: str) -> list[str]:
    return [s.strip() for s in _SENT_SPLIT.split(text) if s.strip()]


def _is_question(sentence: str) -> bool:
    return sentence.rstrip().endswith(("?", "？", "؟"))


def _limit_questions(text: str, allow_question: bool) -> str:
    """At most one question, and none at all when the app did not allow one."""
    out: list[str] = []
    asked = False
    for s in _sentences(text):
        if _is_question(s):
            if not allow_question or asked:
                continue
            asked = True
        out.append(s)
    return " ".join(out)


def _truncate_words(text: str, max_words: int = MAX_WORDS) -> str:
    if len(text.split()) <= max_words:
        return text
    kept: list[str] = []
    count = 0
    for s in _sentences(text):
        n = len(s.split())
        if count + n > max_words:
            break
        kept.append(s)
        count += n
    return " ".join(kept)


# ----- validation -----------------------------------------------------------------------
_SCRIPTS: dict[str, tuple[int, int]] = {
    "hi-IN": (0x0900, 0x097F),
    "mr-IN": (0x0900, 0x097F),
    "bn-IN": (0x0980, 0x09FF),
    "pa-IN": (0x0A00, 0x0A7F),
    "gu-IN": (0x0A80, 0x0AFF),
    "ta-IN": (0x0B80, 0x0BFF),
    "te-IN": (0x0C00, 0x0C7F),
    "kn-IN": (0x0C80, 0x0CFF),
    "ml-IN": (0x0D00, 0x0D7F),
}

_PROMISE = re.compile(
    r"\byou(?:'re| are) (?:definitely |surely |already )?eligible\b|\byou (?:will|'ll) (?:definitely |surely )?(?:get|receive)\b"
    r"|\bguarantee[ds]?\b|\byou qualify\b|\bI(?:'ve| have) (?:applied|registered|submitted)\b"
    r"|आप पात्र हैं|आप पात्र है|आपको (?:जरूर|ज़रूर|पक्का) मिलेगा|आपको मिलेगा|गारंटी|मैंने (?:आवेदन|रजिस्टर)",
    re.IGNORECASE,
)
_LEAK = re.compile(r"\bCONTEXT\b|\bCANDIDATES\b|\bFACTS\b|system prompt|question_to_ask|reply_language", re.IGNORECASE)

# Distinctive names of curated schemes, so we can catch a reply that talks about a scheme we never offered.
_ALIASES: dict[str, list[str]] = {
    "pm-kisan": ["pm-kisan", "pm kisan samman", "kisan samman", "किसान सम्मान"],
    "ayushman-bharat": ["ayushman", "pm-jay", "pmjay", "आयुष्मान"],
    "pmay-u": ["awas yojana", "pmay", "आवास योजना"],
    "pmay-g": ["awas yojana", "pmay", "आवास योजना"],
    "ujjwala": ["ujjwala", "उज्ज्वला", "उज्जवला"],
    "mgnrega": ["mgnrega", "nrega", "मनरेगा", "नरेगा"],
    "pmjdy": ["jan dhan", "जन धन"],
    "atal-pension": ["atal pension", "अटल पेंशन"],
    "pm-fasal-bima": ["fasal bima", "फसल बीमा"],
    "mudra": ["mudra", "मुद्रा योजना"],
    "standup-india": ["stand-up india", "standup india", "stand up india"],
    "pm-svanidhi": ["svanidhi", "स्वनिधि"],
    "nsp-scholarship": ["scholarship portal", "national scholarship"],
    "eshram": ["e-shram", "eshram", "ई-श्रम", "ई श्रम"],
    "pm-kisan-maandhan": ["maandhan", "मानधन"],
    "pm-vishwakarma": ["vishwakarma", "विश्वकर्मा"],
    "nsap-ignoaps": ["indira gandhi national old age", "ignoaps", "इंदिरा गांधी राष्ट्रीय वृद्धावस्था"],
    "nrlm": ["nrlm", "aajeevika", "आजीविका मिशन"],
}

_DIGITS_INDIC = str.maketrans("०१२३४५६७८९০১২৩৪৫৬৭৮৯૦૧૨૩૪૫૬૭૮૯੦੧੨੩੪੫੬੭੮੯௦௧௨௩௪௫௬௭௮௯౦౧౨౩౪౫౬౭౮౯೦೧೨೩೪೫೬೭೮೯൦൧൨൩൪൫൬൭൮൯", "0123456789" * 8)


def _numbers(text: str) -> set[int]:
    t = text.translate(_DIGITS_INDIC)
    out: set[int] = set()
    for m in re.finditer(r"\d[\d,]*", t):
        try:
            out.add(int(m.group().replace(",", "")))
        except ValueError:
            pass
    return out


def _script_ratio(text: str, language: str) -> float:
    letters = [c for c in text if c.isalpha()]
    if not letters:
        return 0.0
    if language == "en-IN":
        return sum(1 for c in letters if c.isascii()) / len(letters)
    lo, hi = _SCRIPTS.get(language, (0x0900, 0x097F))
    return sum(1 for c in letters if lo <= ord(c) <= hi) / len(letters)


@dataclass
class Verdict:
    ok: bool
    text: str
    reason: str = ""


def sanitize(
    raw: str,
    *,
    language: str,
    candidates: list[dict[str, Any]],
    allowed_text: str,
    allow_question: bool,
    mode: str,
) -> Verdict:
    """Clean a model reply and decide whether it is safe to speak.

    allowed_text: everything the reply may legitimately quote numbers from (verified FACTS plus
    what the person said themselves).
    """
    text = clean_for_speech(raw)
    text = _limit_questions(text, allow_question)
    text = _truncate_words(text)

    if not text or len(text) < 4:
        return Verdict(False, "", "empty after cleaning")
    if _LEAK.search(text):
        return Verdict(False, text, "leaks internal prompt/context")
    if _PROMISE.search(text):
        return Verdict(False, text, "promises eligibility or claims an action")

    # Numbers/amounts must come from verified facts or from the person's own words.
    allowed_numbers = _numbers(allowed_text) | ALWAYS_OK_NUMBERS
    for n in _numbers(text):
        if n >= 100 and n not in allowed_numbers:
            return Verdict(False, text, f"number {n} not in verified facts")

    # Only offered schemes may be named.
    low = text.lower()
    offered_ids = {c.get("id") for c in candidates}
    offered_blob = " ".join(
        f"{c.get('name', '')} {c.get('name_hi', '')} {c.get('id', '')}" for c in candidates
    ).lower()
    for scheme in SCHEMES:
        if scheme["id"] in offered_ids:
            continue
        for alias in _ALIASES.get(scheme["id"], []):
            a = alias.lower()
            if a in low and a not in offered_blob:
                return Verdict(False, text, f"mentions scheme not offered: {alias}")

    # Right language (wrong-language speech would be read out in the wrong voice).
    if len(text.split()) >= 4:
        ratio = _script_ratio(text, language)
        need = 0.8 if language == "en-IN" else 0.4
        if ratio < need:
            return Verdict(False, text, f"wrong language/script (ratio {ratio:.2f})")

    return Verdict(True, text)
