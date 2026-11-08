"""Understanding layer: turn what people say (any supported language) into a structured profile.

The profile is rebuilt from *all* user turns on every request, so the conversation is stateless
on the server and nothing the person said earlier is lost.
"""

from __future__ import annotations

import re
from typing import Any

from app.services import matcher

# --------------------------------------------------------------------------------------
# Needs. The matcher already knows Hindi + English for the core categories; these patterns
# add the other Indian languages and romanised Hindi ("Hinglish"), and two categories the
# curated catalogue does not cover (disability, women/child) which are served from myScheme.
# Patterns for Indic scripts are plain substrings (word boundaries do not work for them).
# --------------------------------------------------------------------------------------
EXTRA_NEEDS: dict[str, list[str]] = {
    "agriculture": [
        r"\bkheti\b", r"\bkisaan\b", r"\bfasal\b", r"\bkhet\b",
        "விவசாய", "రైతు", "వ్యవసాయ", "ಕೃಷಿ", "ರೈತ", "കൃഷി", "കർഷക",
        "शेती", "शेतकरी", "চাষ", "কৃষক", "ખેતી", "ખેડૂત", "ਖੇਤੀ", "ਕਿਸਾਨ",
    ],
    "health": [
        r"\bilaaj\b", r"\bilaj\b", r"\bdawai\b", r"\bbimari\b", r"\baspatal\b", r"\bsick\b", r"\bsurgery\b", r"\boperation\b",
        "மருத்துவ", "சிகிச்சை", "ஆரோக்கிய", "ఆరోగ్య", "వైద్య", "ಆರೋಗ್ಯ", "ಚಿಕಿತ್ಸೆ",
        "ആരോഗ്യ", "ചികിത്സ", "आरोग्य", "उपचार", "স্বাস্থ্য", "চিকিৎসা",
        "આરોગ્ય", "સારવાર", "ਸਿਹਤ", "ਇਲਾਜ", "दवाई", "बीमार", "ऑपरेशन",
    ],
    "housing": [
        r"\bghar\b", r"\bawas\b", r"\bmakaan\b", r"\bkaccha\b", r"\bpakka\b", r"\broof\b",
        "வீடு", "ఇల్లు", "గృహ", "ಮನೆ", "വീട്", "বাড়ি", "আবাস", "આવાસ", "ઘર", "ਘਰ", "मकान", "कच्चा",
    ],
    "education": [
        r"\bpadhai\b", r"\bchhatravritti\b", r"\bchatravritti\b", r"\bvazifa\b", r"\bexam\b", r"\btuition\b",
        "கல்வி", "படிப்பு", "உதவித்தொகை", "చదువు", "విద్య", "ಶಿಕ್ಷಣ", "ವಿದ್ಯಾರ್ಥಿ",
        "വിദ്യാഭ്യാസ", "പഠന", "शिक्षण", "शिष्यवृत्ती", "শিক্ষা", "বৃত্তি", "পড়াশোনা",
        "શિક્ષણ", "શિષ્યવૃત્તિ", "ਪੜ੍ਹਾਈ", "ਵਜ਼ੀਫ਼ਾ", "छात्रवृत्ति", "पढ़ाई", "कॉलेज", "स्कूल",
    ],
    "pension": [
        r"\bbuzurg\b", r"\bbujurg\b", r"\bbudhapa\b", r"\bvidhwa\b", r"\bwidow\b", r"\belderly\b", r"\bold age\b",
        "ஓய்வூதிய", "పింఛ", "పెన్షన్", "ಪಿಂಚಣಿ", "പെൻഷൻ", "निवृत्तीवेतन", "पेन्शन", "পেনশন",
        "ভাতা", "પેન્શન", "ਪੈਨਸ਼ਨ", "बुज़ुर्ग", "बूढ़ी", "बूढ़े", "विधवा", "वृद्धावस्था",
    ],
    "employment": [
        r"\bnaukri\b", r"\brozgar\b", r"\brojgar\b", r"\bkaam\b", r"\bbekaar\b", r"\bunemployed\b", r"\bneed a job\b", r"\blooking for work\b",
        "வேலை", "ఉద్యోగ", "ఉపాధి", "ಉದ್ಯೋಗ", "ಕೆಲಸ", "ജോലി", "തൊഴിൽ", "नोकरी", "रोजगार",
        "চাকরি", "কাজ", "નોકરી", "રોજગાર", "ਨੌਕਰੀ", "ਰੋਜ਼ਗਾਰ", "काम", "बेरोज़गार", "बेरोजगार",
    ],
    "livelihood": [
        r"\bdukaan\b", r"\bdukan\b", r"\bvyapar\b", r"\bvyavsay\b", r"\bkarz\b", r"\bkarza\b", r"\bloan\b", r"\bshop\b",
        r"\bbusiness\b", r"\bstartup\b", r"\bself.?employ",
        "கடன்", "தொழில்", "రుణం", "వ్యాపార", "ಸಾಲ", "ವ್ಯಾಪಾರ", "വായ്പ", "വ്യാപാര",
        "कर्ज", "व्यवसाय", "ঋণ", "ব্যবসা", "લોન", "ધંધો", "વ્યવસાય", "ਕਰਜ਼ਾ", "ਕਾਰੋਬਾਰ", "दुकान", "व्यापार", "कारोबार",
    ],
    "finance": [r"\bbank account\b", r"\bjan.?dhan\b", r"\bzero balance\b", "खाता खुलवा", "खाता खोल"],
    "disability": [
        r"\bdisab", r"\bhandicap", r"\bviklang\b", r"\bdivyang", r"\bblind\b", r"\bdeaf\b", r"\bwheelchair\b",
        "दिव्यांग", "विकलांग", "अपंग", "அங்கவீன", "மாற்றுத்திறன", "వికలాంగ", "ವಿಕಲಚೇತನ", "ഭിന്നശേഷി", "প্রতিবন্ধী", "દિવ્યાંગ", "ਅਪਾਹਜ",
    ],
    "women": [
        r"\bpregnan", r"\bmaternity\b", r"\bgirl child\b", r"\bdaughter'?s marriage\b", r"\bsukanya\b",
        "गर्भवती", "प्रसव", "बेटी की शादी", "कन्या", "लाडली",
    ],
    "energy": [r"\bcylinder\b", r"\blpg\b", r"\bujjwala\b", "सिलेंडर", "गैस कनेक्शन"],
    "labour": [r"\bmazdoor\b", r"\bmajdoor\b", r"\bconstruction worker\b", "मजदूर", "मज़दूर", "श्रमिक"],
}

# English words used to query the myScheme catalogue per need (catalogue names are English).
NEED_QUERY: dict[str, str] = {
    "agriculture": "farmer agriculture crop kisan",
    "health": "health medical treatment hospital",
    "housing": "housing awas house",
    "education": "scholarship student education",
    "pension": "pension old age widow",
    "employment": "employment wage skill",
    "livelihood": "loan enterprise business self-employment",
    "finance": "bank account insurance",
    "disability": "disability divyang disabled",
    "women": "women girl maternity widow",
    "energy": "lpg gas cylinder",
    "labour": "labour worker unorganised",
    "artisan": "artisan craftsman",
}

RELATIONS: list[tuple[str, list[str]]] = [
    ("mother", [r"\bmother\b", r"\bmom\b", r"\bmaa\b", r"\bmummy\b", "माँ", "मां", "माता", "अम्मा", "आई"]),
    ("father", [r"\bfather\b", r"\bdad\b", r"\bpapa\b", r"\bpitaji\b", "पिता", "पापा", "बाबूजी"]),
    ("parents", [r"\bparents\b", "माता-पिता", "माँ-बाप", "मां-बाप"]),
    ("wife", [r"\bwife\b", r"\bpatni\b", "पत्नी", "बीवी", "घरवाली"]),
    ("husband", [r"\bhusband\b", r"\bpati\b", "पति", "घरवाले"]),
    ("daughter", [r"\bdaughter\b", r"\bbeti\b", "बेटी"]),
    ("son", [r"\bson\b", r"\bbeta\b", "बेटा"]),
    ("child", [r"\bchild(?:ren)?\b", r"\bkids?\b", r"\bbachch", "बच्चे", "बच्चा", "बच्ची"]),
    ("grandparent", [r"\bgrand(?:mother|father|parent)", r"\bdadi\b", r"\bnani\b", r"\bdada\b", r"\bnana\b", "दादी", "नानी", "दादा", "नाना"]),
]

_AGE_PATTERNS = [
    re.compile(r"(?:\bis|\bam|\bare|\baged?|\bturned|\bumar|\bumra|उम्र|आयु)\s*[:=]?\s*(\d{2,3})\b(?!\s*(?:km|kg|%|rs|rupee|₹|acre|bigha|lakh|thousand|हज़ार|हजार|लाख|एकड़|बीघा|वर्ग))"),
    re.compile(r"(\d{2,3})\s*(?:years?|yrs?|साल|वर्ष|वर्षीय|बरस|saal|varsh)\b"),
    re.compile(r"(\d{2,3})\s*(?:की|के)\s*(?:उम्र|आयु)"),
]

_GREETING = re.compile(
    r"^\W*(?:hi+|hello+|hey+|namaste|namaskar|नमस्ते|नमस्कार|हेलो|हैलो|हाय|good\s*(?:morning|afternoon|evening)|sat sri akal|vanakkam|வணக்கம்|నమస్కారం|ನಮಸ್ಕಾರ|നമസ്കാരം|নমস্কার|નમસ્તે|ਸਤ ਸ੍ਰੀ ਅਕਾਲ)\W*$",
    re.IGNORECASE,
)
_THANKS = re.compile(r"\b(thanks?|thank you|thx|shukriya|dhanyavad)\b|धन्यवाद|शुक्रिया|नन्द|நன்றி|ధన్యవాదాలు|ಧನ್ಯವಾದ|നന്ദി|ধন্যবাদ|આભાર|ਧੰਨਵਾਦ", re.IGNORECASE)
_BYE = re.compile(r"\b(bye|goodbye|see you|that'?s all|nothing else|alvida)\b|अलविदा|बस इतना|और कुछ नहीं|ठीक है धन्यवाद", re.IGNORECASE)


_YES = re.compile(r"\b(yes|yeah|yep|yup|sure|correct|right|haan|han|ji haan|ji)\b|^\s*(हाँ|हां|जी|जी हाँ|जी हां|है|ठीक)\b|हाँ|हां", re.IGNORECASE)
_NO = re.compile(r"\b(no|nope|nahi|nahin|not|don'?t|do not|never)\b|नहीं|नही|नहि", re.IGNORECASE)
_APPLY = re.compile(r"\b(how (?:do|can|to|should) (?:i |we )?(?:apply|register|enrol|enroll|get it)|apply|application|form|register)\b|आवेदन|अप्लाई|फॉर्म|रजिस्टर|कैसे (?:करें|करूं|मिलेगा|मिलेगी)", re.IGNORECASE)
_DOCS = re.compile(r"\b(documents?|papers?|proof|certificate|aadhaar|aadhar)\b|दस्तावेज़?|कागज़?|कागज|प्रमाण", re.IGNORECASE)


def is_yes(text: str) -> bool:
    return bool(_YES.search(text or "")) and not _NO.search(text or "")


def is_no(text: str) -> bool:
    return bool(_NO.search(text or ""))


def followup_topic(text: str) -> str | None:
    """What a follow-up question is about, for the rule-based dialogue: 'apply' | 'docs' | None."""
    if _DOCS.search(text or ""):
        return "docs"
    if _APPLY.search(text or ""):
        return "apply"
    return None


def _hit(text: str, patterns: list[str]) -> bool:
    return any(re.search(p, text, flags=re.IGNORECASE) for p in patterns)


def classify_intent(text: str) -> str:
    """greeting | thanks | bye | other. Only used for short utterances."""
    t = (text or "").strip()
    if len(t.split()) > 6:
        return "other"
    if _BYE.search(t):
        return "bye"
    if _GREETING.match(t):
        return "greeting"
    if _THANKS.search(t):
        return "thanks"
    return "other"


def _latest_age(turns: list[str]) -> int | None:
    for turn in reversed(turns):
        low = turn.lower()
        for pat in _AGE_PATTERNS:
            m = pat.search(low)
            if m:
                age = int(m.group(1))
                if 1 <= age <= 120:
                    return age
    return None


def build_profile(user_turns: list[str]) -> dict[str, Any]:
    """Structured understanding of the person, from everything they said so far."""
    turns = [t.strip() for t in user_turns if t and t.strip()]

    signals: dict[str, Any] = {}
    for t in turns:
        signals = matcher.extract_signals(t, signals)

    joined = " ".join(turns).lower()
    needs = set(signals.get("needs") or [])
    for need, pats in EXTRA_NEEDS.items():
        if _hit(joined, pats):
            needs.add(need)

    age = _latest_age(turns)
    if age is not None:
        signals["age"] = age
        if age >= 60:
            needs.add("pension")

    relation = None
    for name, pats in RELATIONS:
        if _hit(joined, pats):
            relation = name
            break

    signals["needs"] = sorted(needs)
    signals["relation"] = relation
    signals["turns"] = len(turns)
    return signals


def public_profile(signals: dict[str, Any]) -> dict[str, Any]:
    """The subset that is safe/useful to show an LLM or return to the client."""
    keys = ("needs", "occupation", "location_type", "gender", "age", "relation")
    return {k: signals[k] for k in keys if signals.get(k) not in (None, [], "")}
