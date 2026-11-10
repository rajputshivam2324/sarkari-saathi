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

MAX_WORDS = 80
DETAIL_MAX_WORDS = 130   # questions about eligibility, documents, how to apply, ... need room for a complete answer
ALWAYS_OK_NUMBERS = {112}  # national emergency number: the prompt tells the model to say it

# ----- cleaning -------------------------------------------------------------------------
_URL = re.compile(r"(?:https?://|www\.)\S+|\b[\w\-]+\.(?:gov|nic)\.in\S*", re.IGNORECASE)
_EMOJI = re.compile("[\U0001F300-\U0001FAFF\u2600-\u27BF\uFE0F\u200d]")
_MD = re.compile(r"[*_`#>~|]+")
_LIST_PREFIX = re.compile(r"^\s*(?:[-•·▪●]|\(?\d{1,2}[.)])\s+", re.MULTILINE)
_ROLE_LABEL = re.compile(r"^\s*(?:sarkari saathi|सरकारी साथी|assistant|saathi|ai)\s*[:：\-]\s*", re.IGNORECASE)
_SENT_SPLIT = re.compile(r"(?<=[.!?।॥])\s+")


_TYPO = str.maketrans({
    "\u2010": "-", "\u2011": "-", "\u2012": "-", "\u2013": ", ", "\u2014": ", ", "\u2015": ", ",
    "\u00a0": " ", "\u202f": " ", "\u2009": " ", "\u200a": " ", "\u2007": " ", "\u200b": "", "\u2060": "", "\ufeff": "",
    "\u2018": "'", "\u2019": "'", "\u201c": '"', "\u201d": '"',
})
# "PradhanMantriFasalBimaYojana" -> "Pradhan Mantri Fasal Bima Yojana". Only splits lower->Upper inside one
# long token, so legitimate forms like "PM-KISAN", "iPhone" or "CSC" are left alone.
_CAMEL = re.compile(r"\b(?=[A-Za-z]*[a-z][A-Z])[A-Za-z]{9,}\b")
_GLUED_NUM = re.compile(r"\b(two|three|four|five|six|seven|eight|nine|ten|twenty|thirty|fifty|hundred|thousand|lakh)(percent|rupees|thousand|hundred|lakh)\b", re.IGNORECASE)


def _unglue(m: re.Match) -> str:
    return re.sub(r"(?<=[a-z])(?=[A-Z])", " ", m.group())


def clean_for_speech(text: str) -> str:
    t = (text or "").strip().translate(_TYPO)
    t = _CAMEL.sub(_unglue, t)
    t = _GLUED_NUM.sub(lambda m: f"{m.group(1)} {m.group(2)}", t)
    t = _ROLE_LABEL.sub("", t)
    t = _URL.sub("", t)
    t = _EMOJI.sub("", t)
    t = _LIST_PREFIX.sub("", t)
    t = _MD.sub("", t)
    t = re.sub(r"(\d)\s+%", r"\1%", t)
    t = re.sub(r"\s+,", ",", t)
    t = re.sub(r",\s*,+", ",", t)
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
    r"\byou(?:'re| are) (?:definitely |surely |already |fully )?(?:eligible|entitled)\b|\byou(?:'re| are) sure to\b|\byou (?:will|'ll) (?:definitely |surely )?(?:get|receive)\b"
    r"|\b(?:i|we)\s+guarantee\b|\byou(?:'re| are)\s+guaranteed\b|\bguaranteed\s+(?:to\s+)?(?:get|receive|qualify|approval|approved|selected)\b|\byou qualify\b|\bI(?:'ve| have) (?:applied|registered|submitted)\b"
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


# Named portals/apps: a reply may only send people to one the official record itself names.
_PORTALS: list[tuple[str, str, str]] = [
    ("myScheme portal", r"my\s?scheme (?:portal|website|app)|myscheme पोर्टल|myscheme वेबसाइट", r"my\s?scheme\.gov\.in|myscheme"),
    ("UMANG", r"\bumang\b|उमंग", r"umang|उमंग"),
    ("DigiLocker", r"digi\s?locker|डिजिलॉकर", r"digi\s?locker|डिजिलॉकर"),
    ("e-Shram portal", r"e-?shram (?:portal|website)", r"e-?shram"),
    ("NSP", r"national scholarship portal|\bnsp\b", r"national scholarship portal|\bnsp\b|scholarships\.gov"),
    ("Jan Seva / e-Mitra", r"jan\s?seva|e-?mitra|lok seva|sewa kendra|सेवा केंद्र", r"jan\s?seva|e-?mitra|lok seva|sewa kendra|सेवा केंद्र"),
]

# (label, pattern that must appear in the verified facts if the reply claims this document)
_DOC_CLAIMS: list[tuple[str, str, str]] = [
    ("photograph", r"\b(?:passport[- ]size(?:d)? )?(?:photo|photograph)s?\b|फोटो", r"photo|photograph|फोटो"),
    ("income certificate", r"income certificate|आय प्रमाण", r"income certificate|आय प्रमाण"),
    ("caste certificate", r"caste certificate|जाति प्रमाण", r"caste certificate|जाति प्रमाण"),
    ("ration card", r"ration card|राशन कार्ड", r"ration card|राशन"),
    ("birth certificate", r"birth certificate|जन्म प्रमाण", r"birth certificate|जन्म प्रमाण"),
    ("land ownership certificate", r"land[- ]ownership (?:certificate|document|paper)", r"land[- ]ownership|land record|land holding|khasra|khatauni|land registration"),
    ("PAN", r"\bPAN (?:card|number)\b", r"\bpan\b"),
    ("voter ID", r"voter (?:id|card)", r"voter"),
    ("domicile certificate", r"domicile certificate|निवास प्रमाण", r"domicile|निवास"),
]


def _doc_claims(text: str) -> list[tuple[str, str]]:
    low = text.lower()
    out: list[tuple[str, str]] = []
    for label, claim_pat, need_pat in _DOC_CLAIMS:
        if re.search(claim_pat, low, flags=re.IGNORECASE):
            out.append((label, need_pat))
    return out


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
    max_words: int = MAX_WORDS,
) -> Verdict:
    """Clean a model reply and decide whether it is safe to speak.

    allowed_text: everything the reply may legitimately quote numbers from (verified FACTS plus
    what the person said themselves).
    """
    text = clean_for_speech(raw)
    text = _limit_questions(text, allow_question)
    text = _truncate_words(text, max_words)

    if not text or len(text) < 4:
        return Verdict(False, "", "empty after cleaning")
    if _LEAK.search(text):
        return Verdict(False, text, "leaks internal prompt/context")
    if _PROMISE.search(text):
        return Verdict(False, text, "promises eligibility or claims an action")
    if re.search(r"\bguarantee[ds]?\b|गारंटी", text, re.IGNORECASE) and not re.search(r"guarantee|गारंटी", allowed_text, re.IGNORECASE):
        return Verdict(False, text, "uses 'guarantee' but the official record does not")

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

    # Portals/apps: only the ones the official record names (a wrong portal sends the person to the wrong place).
    for label, claim_pat, need_pat in _PORTALS:
        if re.search(claim_pat, text, flags=re.IGNORECASE) and not re.search(need_pat, allowed_text, flags=re.IGNORECASE):
            return Verdict(False, text, f"names a portal not in verified facts: {label}")

    # Documents: only name documents the official record actually mentions.
    claim = _doc_claims(text)
    if claim:
        facts_low = allowed_text.lower()
        for label, pat in claim:
            if not re.search(pat, facts_low, flags=re.IGNORECASE):
                return Verdict(False, text, f"names a document not in verified facts: {label}")

    # Right language (wrong-language speech would be read out in the wrong voice).
    if len(text.split()) >= 4:
        ratio = _script_ratio(text, language)
        need = 0.8 if language == "en-IN" else 0.4
        if ratio < need:
            return Verdict(False, text, f"wrong language/script (ratio {ratio:.2f})")

    return Verdict(True, text)
