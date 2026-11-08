"""Rule-based dialogue used when no LLM is configured, or when an LLM reply fails a guardrail.

It is a safety net, but it should still sound like a person: it acknowledges what was said,
varies its wording turn to turn, says what each scheme is for, and asks at most one useful
question. Hindi and English are written out fully. For the other eight languages it reuses the
existing, already-translated strings in languages.py instead of inventing text we cannot review.
"""

from __future__ import annotations

import re
from typing import Any

from app.services import languages as L

# --------------------------------------------------------------------------------------
# Questions: key -> (English intent for the LLM, English text, Hindi text)
# --------------------------------------------------------------------------------------
QUESTIONS: dict[str, tuple[str, str, str]] = {
    "land": (
        "Ask if they own the land they farm (many farm schemes need land in their name).",
        "Do you own the land you farm?",
        "क्या आप जिस ज़मीन पर खेती करते हैं, वह आपके नाम पर है?",
    ),
    "age": (
        "Ask how old the person is who needs the pension.",
        "How old is the person this is for?",
        "जिनके लिए यह चाहिए, उनकी उम्र कितनी है?",
    ),
    "location": (
        "Ask whether they live in a village or in a city.",
        "Do you live in a village or in a city?",
        "आप गाँव में रहते हैं या शहर में?",
    ),
    "level": (
        "Ask whether the studies are for school or for college.",
        "Is this for school or for college?",
        "यह स्कूल की पढ़ाई के लिए है या कॉलेज के लिए?",
    ),
    "business": (
        "Ask what kind of work or business they want to start or grow.",
        "What kind of work or business do you want to start or grow?",
        "आप कौन सा काम या व्यापार शुरू करना या बढ़ाना चाहते हैं?",
    ),
}


def choose_question(profile: dict[str, Any], candidates: list[dict[str, Any]]) -> str:
    """The single most useful question for a first presentation, or '' if none helps."""
    needs = profile.get("needs") or []
    if not candidates:
        return ""
    if "agriculture" in needs:
        return "land"
    if "pension" in needs and not profile.get("age"):
        return "age"
    if "education" in needs:
        return "level"
    if "livelihood" in needs:
        return "business"
    if ("housing" in needs or "employment" in needs) and not profile.get("location_type"):
        return "location"
    return ""


def question_intent(key: str) -> str:
    return QUESTIONS[key][0] if key in QUESTIONS else ""


def question_text(key: str, lang: str) -> str:
    if key not in QUESTIONS:
        return ""
    return QUESTIONS[key][2] if lang == "hi-IN" else QUESTIONS[key][1]


# --------------------------------------------------------------------------------------
# Phrase tables
# --------------------------------------------------------------------------------------
NEED_PHRASE_EN = {
    "agriculture": "farming support",
    "health": "help with health costs",
    "housing": "help with a home",
    "education": "help with studies",
    "pension": "a pension",
    "employment": "work",
    "livelihood": "help starting or growing a business",
    "finance": "a bank account",
    "disability": "support for a person with a disability",
    "women": "support for women and girls",
    "energy": "a cooking gas connection",
    "labour": "support for workers",
    "artisan": "support for artisans",
}
NEED_PHRASE_HI = {
    "agriculture": "खेती में मदद",
    "health": "इलाज के खर्च में मदद",
    "housing": "घर के लिए मदद",
    "education": "पढ़ाई में मदद",
    "pension": "पेंशन",
    "employment": "रोज़गार",
    "livelihood": "काम या व्यापार शुरू करने में मदद",
    "finance": "बैंक खाता",
    "disability": "दिव्यांग व्यक्ति के लिए सहायता",
    "women": "महिलाओं और बेटियों के लिए सहायता",
    "energy": "रसोई गैस कनेक्शन",
    "labour": "मज़दूरों के लिए सहायता",
    "artisan": "कारीगरों के लिए सहायता",
}
REL_EN = {
    "mother": "your mother", "father": "your father", "parents": "your parents", "wife": "your wife",
    "husband": "your husband", "daughter": "your daughter", "son": "your son", "child": "your child",
    "grandparent": "your grandparent",
}
REL_HI = {
    "mother": "आपकी माँ", "father": "आपके पिताजी", "parents": "आपके माता-पिता", "wife": "आपकी पत्नी",
    "husband": "आपके पति", "daughter": "आपकी बेटी", "son": "आपके बेटे", "child": "आपके बच्चे",
    "grandparent": "आपके दादा-दादी या नाना-नानी",
}
NEED_PRIORITY = ["pension", "disability", "women", "health", "housing", "education", "agriculture",
                 "livelihood", "employment", "labour", "artisan", "energy", "finance"]

ACKS_EN = ["Got it, you need {np}.", "Okay, so you're looking for {np}.", "I understand, you're looking for {np}.", "Thanks for telling me. Let's look at {np}."]
ACKS_HI = ["समझ गया, {np} चाहिए।", "ठीक है, आपको {np} चाहिए।", "जी, {np} के बारे में देखते हैं।", "बताने के लिए धन्यवाद। {np} के बारे में देखते हैं।"]
ACKS_REL_EN = ["Got it, {np} for {rel}.", "Okay, {np} for {rel}.", "I understand, this is for {rel}."]
ACKS_REL_HI = ["समझ गया, {rel} के लिए {np}।", "ठीक है, {rel} के लिए {np} देखते हैं।", "जी, यह {rel} के लिए है।"]

GREET_EN = [
    "Hello, welcome! I can help you find government schemes. Tell me what you need, maybe farming, health, a house, studies or a job?",
    "Namaste! I'm Sarkari Saathi. What kind of help are you looking for today?",
    "Hello! Tell me a little about what you need, and I'll look for schemes that may help.",
]
GREET_HI = [
    "नमस्ते! मैं सरकारी साथी हूँ। बताइए, आपको किस चीज़ में मदद चाहिए, जैसे खेती, इलाज, घर, पढ़ाई या रोज़गार?",
    "नमस्ते, स्वागत है! आप अपनी बात बताइए, मैं देखता हूँ कि कौन सी योजना काम आ सकती है।",
    "जी नमस्ते! आज आपको किस तरह की मदद चाहिए?",
]
THANKS_EN = ["You're welcome! If you want to know about anything else, just ask.", "Happy to help. Is there anything else I can look up for you?"]
THANKS_HI = ["आपका स्वागत है! और कुछ जानना हो तो बेझिझक पूछिए।", "खुशी हुई मदद करके। क्या कुछ और देखना है?"]
BYE_EN = ["Take care! Come back any time you need help."]
BYE_HI = ["ठीक है, ध्यान रखिएगा। जब भी मदद चाहिए, दोबारा आइए।"]

ASK_EN = [
    "Tell me a little about your situation. What do you need help with?",
    "Sure. What would you like help with, for example farming, health, a house, studies, a pension or a job?",
]
ASK_HI = [
    "अपनी स्थिति थोड़ा बताइए। आपको किस चीज़ में मदद चाहिए?",
    "ज़रूर। आपको किसमें मदद चाहिए, जैसे खेती, इलाज, घर, पढ़ाई, पेंशन या रोज़गार?",
]
UNCLEAR_EN = "Sorry, I didn't catch that. Could you say it once more?"
UNCLEAR_HI = "माफ़ कीजिए, मैं ठीक से सुन नहीं पाया। क्या आप एक बार फिर बोल सकते हैं?"

CLOSE_EN = ["The details and official links are on your screen.", "You'll find the details and official links on your screen."]
CLOSE_HI = ["पूरी जानकारी और आधिकारिक लिंक आपकी स्क्रीन पर हैं।", "आधिकारिक लिंक और जानकारी स्क्रीन पर दिख रही है।"]

NONE_FOUND_EN = "I couldn't find a clear match for that yet. Your nearest Common Service Centre can help you search. Or tell me a bit more about what you need."
NONE_FOUND_HI = "इसके लिए मुझे अभी कोई साफ़ योजना नहीं मिली। नज़दीकी कॉमन सर्विस सेंटर आपकी मदद कर सकता है। या आप थोड़ा और बताइए कि क्या चाहिए।"
APPLY_EN = "I can't file applications for you. You apply on the official page, and the link is on your screen. Your nearest Common Service Centre can also help with the form."
APPLY_HI = "आवेदन मैं आपकी तरफ़ से नहीं कर सकता। आवेदन आधिकारिक पेज पर होता है, उसका लिंक आपकी स्क्रीन पर है। नज़दीकी कॉमन सर्विस सेंटर भी फ़ॉर्म भरने में मदद कर सकता है।"
DOCS_EN = "I don't have a verified list of documents, and I don't want to guess. The official page or your nearest Common Service Centre can tell you exactly what to carry."
DOCS_HI = "दस्तावेज़ों की पक्की सूची मेरे पास नहीं है, और मैं अंदाज़ा नहीं लगाना चाहता। आधिकारिक पेज या नज़दीकी कॉमन सर्विस सेंटर बता देगा कि क्या ले जाना है।"
FOLLOWUP_EN = "I don't have verified details on that, so I won't guess. The official page or your nearest Common Service Centre can tell you exactly."
FOLLOWUP_HI = "इसकी पक्की जानकारी मेरे पास नहीं है, इसलिए अंदाज़ा नहीं लगाऊँगा। आधिकारिक पेज या नज़दीकी कॉमन सर्विस सेंटर आपको सही बता देगा।"


ANSWERS: dict[str, dict[str, tuple[str, str]]] = {
    # key -> outcome -> (English, Hindi)
    "land": {
        "yes": ("Good, then these farm schemes look like a real fit. Check the official page on your screen, or visit a Common Service Centre to confirm and register.",
                "बहुत अच्छा, तो ये खेती की योजनाएँ आपके काम की लग रही हैं। स्क्रीन पर आधिकारिक पेज देखिए, या कॉमन सर्विस सेंटर जाकर पक्का कर लीजिए।"),
        "no": ("That's okay. Some farm schemes do need land in your name, so check each official page, and a Common Service Centre can tell you what applies to you.",
               "कोई बात नहीं। कुछ योजनाओं में ज़मीन आपके नाम पर होना ज़रूरी है, इसलिए हर आधिकारिक पेज देख लीजिए, और कॉमन सर्विस सेंटर बता देगा कि आपके लिए क्या लागू है।"),
        "other": ("Thanks, that helps. The official pages on your screen will confirm what applies to you.",
                  "धन्यवाद, यह मददगार है। आपके लिए क्या लागू होता है, यह स्क्रीन पर दिए आधिकारिक पेज बता देंगे।"),
    },
    "age": {"other": ("Thanks, that helps. Age is one of the things the official page checks, so look at the details on your screen.",
                      "धन्यवाद, यह मददगार है। उम्र उन बातों में है जो आधिकारिक पेज जाँचता है, इसलिए स्क्रीन पर दी जानकारी देख लीजिए।")},
    "location": {"other": ("Got it, thanks. Some schemes are different for villages and cities, so the details on your screen will show what fits.",
                           "समझ गया, धन्यवाद। कुछ योजनाएँ गाँव और शहर के लिए अलग होती हैं, इसलिए स्क्रीन पर दी जानकारी देख लीजिए।")},
    "level": {"other": ("Okay, thanks. Look at the scholarship details on your screen, and your school or college office can help with the form.",
                        "ठीक है, धन्यवाद। स्क्रीन पर छात्रवृत्ति की जानकारी देखिए, और आपके स्कूल या कॉलेज का दफ़्तर फ़ॉर्म में मदद कर सकता है।")},
    "business": {"other": ("That sounds like a good plan. The schemes on your screen are a good place to start, and a bank or Common Service Centre can guide you on the paperwork.",
                           "यह अच्छी योजना लगती है। स्क्रीन पर दी योजनाएँ शुरुआत के लिए सही हैं, और बैंक या कॉमन सर्विस सेंटर कागज़ी काम में मदद कर सकता है।")},
}
ANSWER_GENERIC = (
    "Thanks, that helps. The details on your screen will show what applies to you.",
    "धन्यवाद, यह मददगार है। आपके लिए क्या लागू होता है, यह स्क्रीन पर दी जानकारी बता देगी।",
)


def question_key_from_text(question: str) -> str:
    """Which known question a previous assistant message was asking ('' if unknown / rephrased)."""
    q = (question or "").strip()
    for key, (_, en, hi) in QUESTIONS.items():
        if en in q or hi in q:
            return key
    return ""


def _pick(pool: list[str], turn: int) -> str:
    return pool[turn % len(pool)]


_CUT = re.compile(r"\s+[—–-]\s+|\s*[(;]")
_CONNECTIVES = (" under ", " with ", " from ", " against ", " through ", " via ", " and related ", " administered ", " for ")


def _first_sentence(text: str, limit_words: int = 14) -> str:
    """One short, speakable clause from a document-style description."""
    t = re.split(r"(?<=[.।!?])\s", (text or "").strip())[0].strip().rstrip(".।")
    t = _CUT.split(t)[0].strip().rstrip(",")
    words = t.split()
    if len(words) > limit_words:
        head = " ".join(words[:limit_words])
        # Prefer to stop before a connective so the clause ends on a natural boundary.
        cut = max((head.rfind(c) for c in _CONNECTIVES), default=-1)
        t = head[:cut] if cut > 20 else head
        t = t.rstrip(", ")
    return t


def _main_need(profile: dict[str, Any]) -> str | None:
    needs = profile.get("needs") or []
    for n in NEED_PRIORITY:
        if n in needs:
            return n
    return needs[0] if needs else None


def _present(profile, candidates, lang, turn, question_key) -> str:
    hi = lang == "hi-IN"
    need = _main_need(profile)
    rel = profile.get("relation")
    np = (NEED_PHRASE_HI if hi else NEED_PHRASE_EN).get(need or "", "")

    parts: list[str] = []
    if np:
        if rel and rel in REL_EN:
            pool = ACKS_REL_HI if hi else ACKS_REL_EN
            parts.append(_pick(pool, turn).format(np=np, rel=(REL_HI if hi else REL_EN)[rel]))
        else:
            parts.append(_pick(ACKS_HI if hi else ACKS_EN, turn).format(np=np))

    top = candidates[:2]
    first = top[0]
    name = (first.get("name_hi") or first.get("name")) if hi else first.get("name")
    desc = _first_sentence(first.get("description_hi") if hi else first.get("description"))
    if hi:
        parts.append(f"{name} से आपको मदद मिल सकती है। {desc}।" if desc else f"{name} आपके काम की हो सकती है।")
    else:
        parts.append(f"{name} may help. {desc}." if desc else f"{name} looks relevant for you.")

    if len(top) > 1:
        second = top[1]
        n2 = (second.get("name_hi") or second.get("name")) if hi else second.get("name")
        parts.append(f"{n2} भी देखने लायक है।" if hi else f"{n2} is also worth a look.")

    parts.append(_pick(CLOSE_HI if hi else CLOSE_EN, turn))
    q = question_text(question_key, lang)
    if q:
        parts.append(q)

    text = " ".join(parts)
    # Keep it speakable: drop the second scheme if the whole thing runs long.
    if len(text.split()) > 60 and len(top) > 1:
        parts.pop(2 if np else 1)
        text = " ".join(parts)
    return text


def compose(
    *,
    mode: str,
    intent: str,
    language: str,
    profile: dict[str, Any],
    candidates: list[dict[str, Any]],
    question_key: str,
    turn: int,
    ask_count: int = 0,
    unclear: bool = False,
    topic: str | None = None,
    answered_key: str = "",
    answer_yes: bool | None = None,
) -> str:
    """Build the spoken reply for one turn. `language` is already normalised."""
    hi, en = language == "hi-IN", language == "en-IN"
    rich = hi or en

    if mode == "chat":
        if not rich:
            return L.greeting(language) if intent == "greeting" else L.follow_need(language)
        pool = {"greeting": (GREET_HI, GREET_EN), "thanks": (THANKS_HI, THANKS_EN), "bye": (BYE_HI, BYE_EN)}.get(
            intent, (GREET_HI, GREET_EN)
        )
        return _pick(pool[0] if hi else pool[1], turn)

    if mode == "ask":
        if unclear and rich:
            return UNCLEAR_HI if hi else UNCLEAR_EN
        if not rich:
            return L.follow_need(language)
        return _pick(ASK_HI if hi else ASK_EN, ask_count)

    if mode == "answer":
        if not rich:
            return L.MATCH_SUFFIX[language]
        table = ANSWERS.get(answered_key)
        outcome = "yes" if answer_yes is True else "no" if answer_yes is False else "other"
        pair = (table.get(outcome) or table.get("other")) if table else None
        return (pair or ANSWER_GENERIC)[0 if en else 1]

    if mode == "followup":
        if not rich:
            return L.MATCH_SUFFIX[language]
        if topic == "apply":
            return APPLY_HI if hi else APPLY_EN
        if topic == "docs":
            return DOCS_HI if hi else DOCS_EN
        return FOLLOWUP_HI if hi else FOLLOWUP_EN

    # present
    if not candidates:
        return (NONE_FOUND_HI if hi else NONE_FOUND_EN) if rich else L.NO_MATCH[language]
    if not rich:
        # Existing reviewed translations, but names joined naturally instead of "1. ... 2. ...".
        names = ", ".join(c.get("name") or c.get("name_hi") or "" for c in candidates[:2])
        return f"{L.MATCH_PREFIX[language]} {names}. {L.MATCH_SUFFIX[language]}"
    return _present(profile, candidates, language, turn, question_key)
