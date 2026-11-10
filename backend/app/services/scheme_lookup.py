"""Recognise a scheme the person names directly ("Ujjwala yojana ke baare mein batao").

Without this, a named scheme gave no "need" and the assistant fell back to "what help do you need?".

Two sources:
1. Curated schemes: aliases people really use, in English, Devanagari and romanised Hindi, including
   spelling variants. Longest alias wins and its text is blanked out, so "PM Kisan Maandhan" is not
   also read as "PM Kisan".
2. The full myScheme catalogue (3,000+ names): matches on distinctive words of the official name, for
   schemes outside the curated list ("Sukanya Samriddhi", "Janani Suraksha").
"""

from __future__ import annotations

import logging
import re
import unicodedata
from typing import Any

from app.schemes_data import SCHEMES
from app.services.myscheme import get_catalog
from app.services.retrieval import public_scheme

logger = logging.getLogger(__name__)

# id -> aliases (lower-case). Latin aliases of 3 letters or fewer must match as whole words.
ALIASES: dict[str, list[str]] = {
    "pm-kisan": ["pm-kisan", "pm kisan", "pmkisan", "kisan samman nidhi", "kisan samman", "पीएम किसान", "पी एम किसान", "पीएम-किसान", "किसान सम्मान निधि", "किसान सम्मान"],
    "pm-kisan-maandhan": ["kisan maandhan", "kisan mandhan", "maandhan", "mandhan", "maan-dhan", "kisan pension", "किसान मानधन", "मानधन", "किसान पेंशन"],
    "ayushman-bharat": ["ayushman bharat", "ayushman card", "ayushman", "pm-jay", "pmjay", "pm jay", "jan arogya", "golden card", "आयुष्मान भारत", "आयुष्मान कार्ड", "आयुष्मान", "जन आरोग्य"],
    "pmay-u": ["awas yojana urban", "awas yojana - urban", "pmay-u", "pmay u", "pmay urban", "आवास योजना शहरी", "आवास योजना – शहरी", "शहरी आवास"],
    "pmay-g": ["awas yojana gramin", "awaas yojana gramin", "pmay-g", "pmay g", "pmay gramin", "gramin awas", "indira awas", "आवास योजना ग्रामीण", "आवास योजना – ग्रामीण", "ग्रामीण आवास", "इंदिरा आवास"],
    "ujjwala": ["ujjwala", "ujwala", "ujjwal", "pmuy", "उज्ज्वला", "उज्जवला", "उज्वला", "उज्ज्वल योजना"],
    "mgnrega": ["mgnrega", "manrega", "nrega", "mahatma gandhi national rural employment", "मनरेगा", "नरेगा", "महात्मा गांधी राष्ट्रीय ग्रामीण रोजगार"],
    "pmjdy": ["jan dhan", "jandhan", "pmjdy", "जन धन", "जनधन"],
    "atal-pension": ["atal pension", "apy", "अटल पेंशन"],
    "pm-fasal-bima": ["fasal bima", "pmfby", "pradhan mantri fasal", "फसल बीमा"],
    "mudra": ["mudra yojana", "mudra loan", "mudra scheme", "mudra card", "pradhan mantri mudra", "pm mudra", "pmmy", "मुद्रा योजना", "मुद्रा लोन", "मुद्रा ऋण", "मुद्रा कार्ड", "प्रधानमंत्री मुद्रा", "पीएम मुद्रा"],
    "standup-india": ["stand-up india", "standup india", "stand up india", "स्टैंड अप इंडिया", "स्टैंड-अप इंडिया", "स्टैंडअप इंडिया"],
    "pm-svanidhi": ["svanidhi", "swanidhi", "street vendor atmanirbhar", "स्वनिधि"],
    "nsp-scholarship": ["national scholarship portal", "scholarship portal", "nsp", "राष्ट्रीय छात्रवृत्ति"],
    "eshram": ["e-shram", "eshram", "e shram", "ई-श्रम", "ई श्रम", "ईश्रम"],
    "pm-vishwakarma": ["vishwakarma", "vishvakarma", "विश्वकर्मा"],
    "nsap-ignoaps": ["ignoaps", "indira gandhi national old age", "national old age pension", "old age pension", "nsap", "वृद्धावस्था पेंशन", "वृद्ध पेंशन", "इंदिरा गांधी राष्ट्रीय वृद्धावस्था"],
    "nrlm": ["deendayal antyodaya", "day-nrlm", "nrlm", "aajeevika mission", "ajeevika mission", "दीनदयाल अंत्योदय", "आजीविका मिशन"],
}
# Generic wordings that fit more than one scheme: answered with every scheme they could mean.
AMBIGUOUS: list[tuple[list[str], list[str]]] = [
    (["pradhan mantri awas", "pradhan mantri awaas", "awas yojana", "awaas yojana", "pmay", "प्रधानमंत्री आवास", "आवास योजना"], ["pmay-g", "pmay-u"]),
]

_BY_ID = {s["id"]: s for s in SCHEMES}
_ZW = dict.fromkeys(map(ord, "\u200b\u200c\u200d\ufeff"), None)


def _norm(text: str) -> str:
    t = unicodedata.normalize("NFC", text or "").translate(_ZW).lower()
    t = t.replace("‑", "-").replace("–", "-").replace("—", "-")
    t = re.sub(r"[^\w\u0900-\u097F\- ]+", " ", t)      # keep letters, Devanagari, hyphen
    return re.sub(r"\s+", " ", t).strip()


def _pattern(alias: str) -> re.Pattern[str]:
    a = re.escape(_norm(alias)).replace(r"\ ", r"\s+")
    if alias.isascii():                                 # Latin: no matching inside other words
        return re.compile(rf"(?<![a-z0-9]){a}(?![a-z0-9])")
    return re.compile(a)


# (pattern, scheme ids, alias length) sorted longest first, so the most specific alias claims its text first
_COMPILED: list[tuple[re.Pattern[str], list[str], int]] = sorted(
    [(_pattern(a), [sid], len(a)) for sid, als in ALIASES.items() for a in als]
    + [(_pattern(a), ids, len(a)) for als, ids in AMBIGUOUS for a in als],
    key=lambda x: -x[2],
)


def find_curated(text: str) -> list[str]:
    """Curated scheme ids named in `text`, in the order they were mentioned."""
    work = _norm(text)
    found: list[tuple[int, list[str]]] = []
    for pat, ids, _len in _COMPILED:
        for m in pat.finditer(work):
            found.append((m.start(), ids))
            work = work[: m.start()] + " " * (m.end() - m.start()) + work[m.end():]   # claim the text
            break
    found.sort(key=lambda x: x[0])
    out: list[str] = []
    for _pos, ids in found:
        for sid in ids:
            if sid not in out:
                out.append(sid)
    return out


# ---- catalogue: distinctive words of official names ------------------------------------
_GENERIC = {
    "yojana", "yojna", "scheme", "schemes", "pradhan", "mantri", "mukhya", "national", "state", "government", "govt", "central",
    "programme", "program", "assistance", "financial", "support", "grant", "scholarship", "pension", "fund", "mission", "abhiyan",
    "karnataka", "bihar", "kerala", "punjab", "haryana", "gujarat", "delhi", "assam", "odisha", "jharkhand", "uttar", "pradesh",
    "tamil", "nadu", "maharashtra", "rajasthan", "bengal", "telangana", "andhra", "goa", "tripura", "mizoram", "manipur", "sikkim",
    "board", "welfare", "women", "girls", "boys", "children", "senior", "citizen", "citizens", "persons", "workers", "worker",
    "farmer", "farmers", "student", "students", "education", "health", "housing", "loan", "credit", "subsidy", "scheme", "under",
    "about", "tell", "know", "want", "need", "help", "from", "with", "this", "that", "what", "which", "kaise", "baare", "mein",
    "batao", "bataiye", "bataye", "hindi", "india", "indian", "bharat", "sarkar", "sarkari", "hai", "hain", "karo", "kare",
    # words of a question about a scheme ("what is the helpline number", "is Aadhaar mandatory"): never a name
    "helpline", "helpdesk", "number", "toll", "free", "contact", "complaint", "grievance", "appeal", "status", "document", "documents",
    "required", "application", "apply", "online", "offline", "website", "portal", "income", "limit", "eligible", "eligibility",
    "benefit", "benefits", "amount", "payment", "money", "receive", "mandatory", "certificate", "aadhaar", "aadhar", "passbook",
    "domicile", "caste", "rural", "urban", "active", "launched", "difference", "between", "compare", "approved", "rejected",
}
_index: dict[str, Any] = {"n": -1, "tokens": {}, "entries": {}}


def _tokens(text: str) -> set[str]:
    return {w for w in re.findall(r"[a-z]{4,}", _norm(text)) if w not in _GENERIC}


async def _catalogue_index() -> dict[str, Any]:
    cat = await get_catalog()
    if _index["n"] != len(cat):
        tokens: dict[str, set[str]] = {}
        entries: dict[str, dict[str, Any]] = {}
        for e in cat:
            slug = e.get("slug") or e.get("id")
            if not slug:
                continue
            entries[slug] = e
            for t in _tokens(f"{e.get('name', '')} {e.get('short_title', '')}"):
                tokens.setdefault(t, set()).add(slug)
        _index.update(n=len(cat), tokens=tokens, entries=entries)
    return _index


async def find_in_catalogue(text: str, *, exclude: set[str] | None = None) -> list[dict[str, Any]]:
    """Schemes outside the curated list whose official name the person is clearly using."""
    if not re.search(r"[a-z]{4,}", _norm(text)):
        return []
    idx = await _catalogue_index()
    words = _tokens(text)
    score: dict[str, float] = {}
    for w in words:
        slugs = idx["tokens"].get(w)
        if not slugs or len(slugs) > 25:               # a word in many names is not a name
            continue
        weight = 3.0 if len(slugs) <= 3 else 1.0
        for sl in slugs:
            score[sl] = score.get(sl, 0.0) + weight
    ranked = sorted((s for s in score.items() if s[1] >= 3.0 and not (exclude and s[0] in exclude)), key=lambda x: -x[1])
    if not ranked:
        return []
    top = ranked[0][1]
    return [idx["entries"][sl] for sl, sc in ranked[:2] if sc >= top - 0.01]


async def find_named_schemes(text: str) -> list[dict[str, Any]]:
    """Public scheme dicts (same shape as search results) for schemes the person named. Never raises."""
    try:
        ids = find_curated(text)
        if ids:
            return [public_scheme(_BY_ID[i], score=12.0, source="curated") for i in ids[:2]]
        curated_slugs = {s.get("myscheme_slug") for s in SCHEMES if s.get("myscheme_slug")}
        hits = await find_in_catalogue(text, exclude=curated_slugs)
        return [public_scheme(h, score=12.0, source="myscheme.gov.in") for h in hits]
    except Exception:
        logger.exception("named-scheme lookup failed")
        return []
