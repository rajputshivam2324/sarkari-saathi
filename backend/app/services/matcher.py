"""Rule-based scheme matcher with Hindi follow-ups and spoken reply."""

from __future__ import annotations

import re
from typing import Any

from app.schemes_data import SCHEMES

MAX_FOLLOW_UPS = 3

# Follow-up questions in Hindi (asked in order of missing signal priority)
FOLLOW_UP_QUESTIONS: list[tuple[str, str]] = [
    (
        "need",
        "आपको किस तरह की मदद चाहिए — खेती, स्वास्थ्य, घर, पढ़ाई, रोजगार, पेंशन, या व्यवसाय?",
    ),
    (
        "location_type",
        "क्या आप गाँव में रहते हैं या शहर में?",
    ),
    (
        "occupation",
        "आप क्या करते हैं — किसान, मजदूर, छात्र, दुकानदार, कारीगर, या कुछ और?",
    ),
]

NEED_PATTERNS: list[tuple[str, list[str]]] = [
    (
        "agriculture",
        [
            r"farm",
            r"farmer",
            r"kisan",
            r"crop",
            r"agriculture",
            r"किसान",
            r"खेती",
            r"फसल",
            r"खेत",
        ],
    ),
    (
        "health",
        [
            r"health",
            r"hospital",
            r"medical",
            r"insurance",
            r"treatment",
            r"इलाज",
            r"अस्पताल",
            r"स्वास्थ्य",
            r"बीमा",
            r"आयुष्मान",
        ],
    ),
    (
        "housing",
        [
            r"house",
            r"housing",
            r"home",
            r"awas",
            r"flat",
            r"घर",
            r"आवास",
            r"मकान",
            r"प्लॉट",
        ],
    ),
    (
        "energy",
        [r"lpg", r"gas", r"cylinder", r"ujjwala", r"गैस", r"सिलेंडर", r"रसोई"],
    ),
    (
        "employment",
        [
            r"job",
            r"employment",
            r"wage",
            r"unemployed",
            r"nrega",
            r"mgnrega",
            r"नौकरी",
            r"रोजगार",
            r"बेरोजगार",
            r"मजदूरी",
            r"काम\s*चाहि",
        ],
    ),
    (
        "finance",
        [r"bank", r"account", r"jan\s*dhan", r"बैंक", r"खाता", r"जन\s*धन"],
    ),
    (
        "pension",
        [
            r"pension",
            r"old\s*age",
            r"senior",
            r"retirement",
            r"पेंशन",
            r"बुजुर्ग",
            r"वृद्ध",
            r"रिटायर",
        ],
    ),
    (
        "livelihood",
        [
            r"loan",
            r"business",
            r"shop",
            r"mudra",
            r"vendor",
            r"startup",
            r"ऋण",
            r"लोन",
            r"व्यवसाय",
            r"दुकान",
            r"उद्यम",
            r"रेहड़ी",
            r"ठेला",
        ],
    ),
    (
        "education",
        [
            r"student",
            r"scholarship",
            r"college",
            r"school",
            r"education",
            r"fees",
            r"छात्र",
            r"छात्रवृत्ति",
            r"स्कॉलरशिप",
            r"पढ़ाई",
            r"कॉलेज",
            r"स्कूल",
        ],
    ),
    (
        "labour",
        [
            r"labour",
            r"labor",
            r"worker",
            r"construction",
            r"unorganised",
            r"मजदूर",
            r"श्रमिक",
            r"असंगठित",
            r"कामगार",
        ],
    ),
    (
        "artisan",
        [
            r"artisan",
            r"craftsman",
            r"carpenter",
            r"potter",
            r"tailor",
            r"कारीगर",
            r"बढ़ई",
            r"दर्जी",
            r"कुम्हार",
            r"शिल्प",
        ],
    ),
]

OCCUPATION_PATTERNS: list[tuple[str, list[str]]] = [
    ("farmer", [r"farmer", r"kisan", r"किसान", r"खेती"]),
    ("student", [r"student", r"छात्र", r"स्टूडेंट", r"पढ़ता", r"पढ़ती"]),
    ("labour", [r"labour", r"labor", r"mazdoor", r"मजदूर", r"श्रमिक"]),
    ("vendor", [r"vendor", r"hawker", r"रेहड़ी", r"ठेला", r"विक्रेता"]),
    ("shopkeeper", [r"shop", r"business", r"दुकान", r"व्यवसाय", r"व्यापारी"]),
    ("artisan", [r"artisan", r"कारीगर", r"बढ़ई", r"दर्जी", r"कुम्हार"]),
    ("woman_shg", [r"shg", r"self\s*help", r"स्वयं\s*सहायता", r"समूह"]),
]

LOCATION_PATTERNS: list[tuple[str, list[str]]] = [
    ("rural", [r"village", r"rural", r"gaon", r"ग्रामीण", r"गाँव", r"गांव", r"देहात"]),
    ("urban", [r"city", r"urban", r"town", r"शहर", r"नगर", r"मेट्रो"]),
]

GENDER_PATTERNS: list[tuple[str, list[str]]] = [
    ("woman", [r"\bwom[ae]n\b", r"female", r"lady", r"girl", r"महिला", r"औरत", r"बेटी", r"स्त्री"]),
    ("man", [r"\bman\b", r"male", r"boy", r"पुरुष", r"मर्द", r"आदमी"]),
]

AGE_RE = re.compile(
    r"(?:age|umra|उम्र|आयु)\s*(?:is|hai|है|:)?\s*(\d{1,3})"
    r"|(\d{1,3})\s*(?:years?\s*old|yrs?|साल|वर्ष)",
    re.IGNORECASE,
)


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip().lower())


def _match_any(text: str, patterns: list[str]) -> bool:
    return any(re.search(p, text, flags=re.IGNORECASE) for p in patterns)


def extract_signals(text: str, prior: dict[str, Any] | None = None) -> dict[str, Any]:
    """Merge newly detected signals into prior conversation signals."""
    signals: dict[str, Any] = dict(prior or {})
    raw = text or ""
    norm = _normalize(raw)
    if not norm:
        return signals

    # Accumulate free-text need snippets
    history = list(signals.get("utterances") or [])
    history.append(raw.strip())
    signals["utterances"] = history[-8:]

    for need, patterns in NEED_PATTERNS:
        if _match_any(norm, patterns):
            needs = set(signals.get("needs") or [])
            needs.add(need)
            signals["needs"] = sorted(needs)

    for occ, patterns in OCCUPATION_PATTERNS:
        if _match_any(norm, patterns):
            signals["occupation"] = occ

    for loc, patterns in LOCATION_PATTERNS:
        if _match_any(norm, patterns):
            signals["location_type"] = loc

    for gender, patterns in GENDER_PATTERNS:
        if _match_any(norm, patterns):
            signals["gender"] = gender

    age_match = AGE_RE.search(norm)
    if age_match:
        age_str = age_match.group(1) or age_match.group(2)
        try:
            age = int(age_str)
            if 1 <= age <= 120:
                signals["age"] = age
        except ValueError:
            pass

    if signals.get("occupation") == "farmer":
        needs = set(signals.get("needs") or [])
        needs.add("agriculture")
        signals["needs"] = sorted(needs)
    if signals.get("occupation") == "student":
        needs = set(signals.get("needs") or [])
        needs.add("education")
        signals["needs"] = sorted(needs)
    if signals.get("occupation") == "artisan":
        needs = set(signals.get("needs") or [])
        needs.add("artisan")
        needs.add("livelihood")
        signals["needs"] = sorted(needs)
    if signals.get("occupation") == "vendor":
        needs = set(signals.get("needs") or [])
        needs.add("livelihood")
        signals["needs"] = sorted(needs)

    if signals.get("age") and signals["age"] >= 60:
        needs = set(signals.get("needs") or [])
        needs.add("pension")
        signals["needs"] = sorted(needs)

    return signals


def _missing_signal_keys(signals: dict[str, Any]) -> list[str]:
    missing: list[str] = []
    if not signals.get("needs"):
        missing.append("need")
    if not signals.get("location_type"):
        missing.append("location_type")
    if not signals.get("occupation"):
        missing.append("occupation")
    return missing


def next_follow_up(
    signals: dict[str, Any], follow_ups_asked: int
) -> tuple[str | None, str | None]:
    """Return (signal_key, hindi_question) or (None, None) if ready to match."""
    if follow_ups_asked >= MAX_FOLLOW_UPS:
        return None, None

    # If we already have a clear need, we can match with fewer questions
    missing = _missing_signal_keys(signals)
    if not missing:
        return None, None

    # Strong need alone is enough after one clarifying turn? Prefer asking
    # location/occupation only when need is vague or multi-category.
    needs = signals.get("needs") or []
    if needs and follow_ups_asked >= 1 and len(needs) == 1:
        return None, None

    if needs and not missing:
        return None, None

    asked = set(signals.get("asked_keys") or [])
    for key, question in FOLLOW_UP_QUESTIONS:
        if key in missing and key not in asked:
            return key, question

    return None, None


def _kw_in(kw: str, text: str) -> bool:
    """Keyword match. Short Latin keywords ("sc", "st", "ac") must be whole words, otherwise they match
    inside ordinary words ("small tea stall" contains "st")."""
    if kw.isascii() and len(kw) <= 3:
        return re.search(rf"(?<![a-z0-9]){re.escape(kw)}(?![a-z0-9])", text) is not None
    return kw in text


def score_schemes(signals: dict[str, Any], limit: int = 3) -> list[dict[str, Any]]:
    """Score catalogue schemes against extracted signals; return top N."""
    needs = set(signals.get("needs") or [])
    occupation = signals.get("occupation")
    location = signals.get("location_type")
    gender = signals.get("gender")
    age = signals.get("age")
    utterances = " ".join(signals.get("utterances") or []).lower()

    scored: list[tuple[float, dict[str, Any]]] = []
    for scheme in SCHEMES:
        score = 0.0
        keywords = [k.lower() for k in scheme.get("eligibility_keywords") or []]
        category = scheme.get("category") or ""

        if category in needs:
            score += 5.0

        for kw in keywords:
            if _kw_in(kw, utterances):
                score += 2.0

        # Occupation boosts
        if occupation == "farmer" and category in {"agriculture", "pension"}:
            score += 3.0 if scheme["id"] != "nsap-ignoaps" else 0.5
        if occupation == "student" and category == "education":
            score += 4.0
        if occupation == "labour" and category in {"employment", "labour"}:
            score += 3.5
        if occupation == "vendor" and scheme["id"] == "pm-svanidhi":
            score += 5.0
        if occupation == "shopkeeper" and category == "livelihood":
            score += 3.0
        if occupation == "artisan" and scheme["id"] == "pm-vishwakarma":
            score += 5.0
        if occupation == "woman_shg" and scheme["id"] == "nrlm":
            score += 5.0

        if location == "rural":
            if scheme["id"] in {"mgnrega", "pmay-g", "pm-kisan", "nrlm"}:
                score += 2.0
            if scheme["id"] == "pmay-u":
                score -= 1.5
        if location == "urban":
            if scheme["id"] in {"pmay-u", "pm-svanidhi"}:
                score += 2.0
            if scheme["id"] == "pmay-g":
                score -= 1.5

        # Stand-Up India is only for SC/ST and women entrepreneurs: without any of those words it should
        # not outrank general small-business schemes such as MUDRA.
        if scheme["id"] == "standup-india" and gender != "woman" and not any(
            _kw_in(w, utterances) for w in ("sc", "st", "scheduled caste", "scheduled tribe", "dalit", "tribal", "दलित", "आदिवासी", "अनुसूचित")
        ):
            score -= 3.0

        if gender == "woman":
            if scheme["id"] in {"ujjwala", "standup-india", "nrlm"}:
                score += 2.0

        if age is not None:
            if age >= 60 and scheme["id"] == "nsap-ignoaps":
                score += 4.0
            if 18 <= age <= 40 and scheme["id"] in {"atal-pension", "pm-kisan-maandhan"}:
                score += 1.5
            if age > 40 and scheme["id"] in {"atal-pension", "pm-kisan-maandhan"}:
                score -= 1.0

        if score > 0:
            item = dict(scheme)
            item["score"] = round(score, 2)
            scored.append((score, item))

    scored.sort(key=lambda x: x[0], reverse=True)

    # Fallback: keyword-overlap soft match if nothing scored
    if not scored:
        for scheme in SCHEMES:
            soft = sum(1 for kw in scheme["eligibility_keywords"] if _kw_in(kw.lower(), utterances))
            if soft:
                item = dict(scheme)
                item["score"] = float(soft)
                scored.append((float(soft), item))
        scored.sort(key=lambda x: x[0], reverse=True)

    return [item for _, item in scored[:limit]]


def build_reply_hi(
    schemes: list[dict[str, Any]],
    *,
    follow_up: str | None = None,
) -> str:
    """Build a short Hindi spoken reply."""
    if follow_up:
        return follow_up

    if not schemes:
        return (
            "मुझे अभी स्पष्ट योजना नहीं मिली। "
            "कृपया बताइए आपको खेती, स्वास्थ्य, घर, पढ़ाई, रोजगार या पेंशन में से किसमें मदद चाहिए।"
        )

    parts: list[str] = ["आपके लिए ये योजनाएँ सही लगती हैं।"]
    for i, scheme in enumerate(schemes, start=1):
        name_hi = scheme.get("name_hi") or scheme.get("name")
        desc = scheme.get("description_hi") or scheme.get("description") or ""
        # Keep TTS short: first sentence-ish
        short = desc.split("।")[0].strip()
        if short and not short.endswith("।"):
            short = short + "।"
        url = scheme.get("official_url") or ""
        parts.append(f"{i}. {name_hi}। {short} आधिकारिक लिंक: {url}")

    parts.append("आवेदन से पहले आधिकारिक वेबसाइट पर पात्रता ज़रूर जाँचें।")
    return " ".join(parts)


def process_turn(
    user_text: str,
    context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Full matcher turn:
    - extract/merge signals
    - ask up to 3 Hindi follow-ups
    - otherwise score top 3 schemes and build reply
    """
    ctx = dict(context or {})
    signals = extract_signals(user_text, ctx.get("signals"))
    follow_ups_asked = int(ctx.get("follow_ups_asked") or 0)
    asked_keys = list(signals.get("asked_keys") or [])

    key, question = next_follow_up(signals, follow_ups_asked)
    if question:
        asked_keys.append(key)  # type: ignore[arg-type]
        signals["asked_keys"] = asked_keys
        follow_ups_asked += 1
        reply = build_reply_hi([], follow_up=question)
        new_ctx = {
            "signals": signals,
            "follow_ups_asked": follow_ups_asked,
        }
        return {
            "follow_up": question,
            "reply_text": reply,
            "schemes": [],
            "context": new_ctx,
            "ready": False,
        }

    schemes = score_schemes(signals, limit=3)
    reply = build_reply_hi(schemes)
    new_ctx = {
        "signals": signals,
        "follow_ups_asked": follow_ups_asked,
    }
    return {
        "follow_up": None,
        "reply_text": reply,
        "schemes": schemes,
        "context": new_ctx,
        "ready": True,
    }


def apply_evon_refinement(
    match_result: dict[str, Any],
    evon_content: str,
) -> dict[str, Any]:
    """
    Optionally blend Evon output into the spoken reply when Evon actually ran.
    Keeps scheme list from the local matcher (source of truth for URLs).
    """
    content = (evon_content or "").strip()
    if not content:
        return match_result

    # Prefer Evon Hindi prose for speech, but keep structured schemes/URLs.
    updated = dict(match_result)
    if match_result.get("schemes"):
        # Append official links so TTS still mentions them if Evon omitted them
        links = []
        for s in match_result["schemes"]:
            links.append(f"{s.get('name_hi') or s.get('name')}: {s.get('official_url')}")
        updated["reply_text"] = f"{content} आधिकारिक लिंक — " + " ; ".join(links)
    else:
        updated["reply_text"] = content
    return updated
