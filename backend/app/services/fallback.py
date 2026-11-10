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
from app.services import scheme_details as SD

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

UNKNOWN_EN = "I don't have verified details on that scheme, so I won't guess. Its official website or your nearest Common Service Centre can tell you exactly. If you tell me what help you need, I can look for other schemes."
UNKNOWN_HI = "इस योजना की पक्की जानकारी मेरे पास नहीं है, इसलिए मैं अंदाज़ा नहीं लगाऊँगा। उसकी आधिकारिक वेबसाइट या नज़दीकी कॉमन सर्विस सेंटर आपको सही बता देगा। आप बताइए कि आपको क्या मदद चाहिए, तो मैं दूसरी योजनाएँ देख सकता हूँ।"
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


ACK_NEXT_EN = [
    "Sure. Would you like to know how to apply, or which documents to keep ready?",
    "Okay. I can tell you who is eligible, or walk you through how to apply. Which would help?",
]
ACK_NEXT_HI = [
    "ठीक है। क्या मैं बताऊँ कि आवेदन कैसे करना है, या कौन से कागज़ तैयार रखने हैं?",
    "जी। मैं बता सकता हूँ कि कौन पात्र है, या आवेदन कैसे करें। आपको क्या जानना है?",
]

_STEP = re.compile(r"^\s*(?:step\s*\d+\s*[:.\-]?|\d+[.)])\s*", re.IGNORECASE)
_DOCLINE = re.compile(r"document|aadhaar|aadhar|passbook|certificate|proof|photo|ration card|bank|दस्तावेज|आधार|पासबुक|प्रमाण|फोटो|राशन", re.IGNORECASE)
_SHOW_STEPS_EN = "The full steps and links are on your screen under Details."
_SHOW_STEPS_HI = "पूरे चरण और लिंक आपकी स्क्रीन पर Details में हैं।"


def _bullets(md: str, limit: int = 3, hi: bool = False) -> list[str]:
    """First few meaningful, speakable lines of a section, as plain sentences."""
    out: list[str] = []
    for raw in SD.md_to_text(md).splitlines():
        line = re.sub(r"^\s*(?:[-*•]|\d{1,2}[.)])\s*", "", raw).strip()
        line = re.sub(r"^\d{1,2}[.)]\s+", "", line)
        if len(line) >= 12 and speakable(line, hi):
            line = line.rstrip(" ;,")
            out.append(line if line.endswith((".", "।", "!", "?")) else line + ".")
        if len(out) >= limit:
            break
    return out


_URL = re.compile(r"(?:https?://|www\.)\S+", re.IGNORECASE)


_JUNK = re.compile(r"&|;\s*[^\s;]{1,6}\s*;|(?:\bएएमपी\b|\bएम्प\b|\bamp\b)|\bnbsp\b|<|>|\[|\]|\|", re.IGNORECASE)


def speakable(text: str, hi: bool) -> bool:
    """Is this snippet of official text fit to be read aloud? Rejects machine-translation debris."""
    t = (text or "").strip()
    if len(t) < 12 or _JUNK.search(t):
        return False
    letters = [c for c in t if c.isalpha()]
    if not letters:
        return False
    if hi:   # a Hindi sentence should be mostly Devanagari; heavy Latin/number clutter means a broken translation
        dev = sum("\u0900" <= c <= "\u097f" for c in letters)
        if dev / len(letters) < 0.55:
            return False
    return t.count(";") <= 2


def _clip_words(text: str, n: int) -> str:
    text = _URL.sub("", text)
    text = re.sub(r"\s{2,}", " ", text).strip()
    w = text.split()
    return text if len(w) <= n else " ".join(w[:n]).rstrip(",;: ") + "…"


def _apply_phrase(rec: dict, hi: bool) -> str:
    modes = " ".join((a.get("mode") or "") for a in rec.get("apply") or []).lower()
    ways: list[str] = []
    if "online" in modes and "csc" not in modes.replace("online - via csc", "") or ("online" in modes):
        ways.append("ऑनलाइन आधिकारिक पोर्टल पर" if hi else "online on the official portal")
    if "csc" in modes:
        ways.append("कॉमन सर्विस सेंटर के ज़रिए" if hi else "through a Common Service Centre")
    if "offline" in modes:
        ways.append("संबंधित दफ़्तर में जाकर" if hi else "at the concerned office")
    ways = list(dict.fromkeys(ways))
    if not ways:
        return ""
    joiner = " या " if hi else " or "
    return ("आप " + joiner.join(ways) + " आवेदन कर सकते हैं।") if hi else ("You can apply " + joiner.join(ways) + ".")


_HEADING = re.compile(r"^\s*#{1,6}\s*")
_ITEM_START = re.compile(r"^\s*(?:(?:step|चरण)\s*\d+\s*[:.\-]?|\d{1,2}[.)]|[-*•])\s*", re.IGNORECASE)
_GLUED_NUM = re.compile(r"(?<=[.!?।'\"”’])\s*(?=\d{1,2}[.)]\s)")


def _steps(rec: dict, n: int = 4) -> list[str]:
    """Spoken-length application steps from whatever layout the official text uses.

    Handles "Step 1:" lines, numbered or bulleted lists, "### Process 1:" headings, numbered items glued
    after a full stop, and plain sentences. Online route first.
    """
    apply = sorted(rec.get("apply") or [], key=lambda a: 0 if (a.get("mode") or "").lower() == "online" else 1)
    for a in apply:
        text = SD.md_to_text(a.get("steps_md"))
        text = _GLUED_NUM.sub("\n", text)
        steps: list[str] = []
        for raw in text.splitlines():
            line = _HEADING.sub("", raw).strip()
            if not line:
                continue
            is_item = bool(_ITEM_START.match(line))
            line = _ITEM_START.sub("", line).strip(" *_")
            # headings such as "Process 1:" / "Registration Process:" are labels, not steps
            if not line or re.fullmatch(r"(?:process|step|चरण|प्रक्रिया)[^.!?।]{0,28}[:：]?", line, re.IGNORECASE):
                continue
            if is_item or len(line.split()) >= 5:
                steps.append(_clip_words(line, 24))
        steps = [s for s in steps if len(s) > 8]
        if steps:
            return steps[:n]
    return []


def _supplement_answer(topic: str | None, sup: dict[str, Any]) -> str | None:
    """English answer from the verified supplement (helpline, documents, fee). None when it has nothing for the topic."""
    def line(v: Any) -> str:
        return "; ".join(v) if isinstance(v, list) else str(v)

    if topic == "help" and (sup.get("helpline") or sup.get("grievance")):
        return " ".join(line(sup[k]).rstrip(".") + "." for k in ("helpline", "grievance") if sup.get(k))
    if topic == "docs" and sup.get("documents"):
        return "The official pages list these documents: " + line(sup["documents"]).rstrip(".") + ". " + _SHOW_STEPS_EN
    if topic == "apply" and sup.get("fee"):
        return line(sup["fee"])
    return None


def _details_answer(topic: str | None, rec: dict | None, hi: bool) -> str | None:
    """A concrete answer to a follow-up, straight from the official record. None if the record lacks it."""
    if not rec:
        return None
    name = rec.get("short_title") or rec.get("name") or ""
    if topic == "eligibility" and rec.get("eligibility_md"):
        b = _bullets(rec["eligibility_md"], 3, hi)
        if b:
            tail = (" कुछ लोग इस योजना से बाहर हैं, इसलिए आधिकारिक पेज पर सूची ज़रूर देखिए।" if hi else " Some people are excluded, so please check the list on the official page.") if rec.get("exclusions_md") else ""
            lead = f"{name} के लिए: " if hi else f"For {name}: "
            return (lead + " ".join(_clip_words(x, 34) for x in b) + tail).replace("..", ".").replace(".।", "।")
    if topic == "benefits" and rec.get("benefits_md"):
        b = _bullets(rec["benefits_md"], 2, hi)
        if b:
            return (f"{name} में आपको मिलता है: " if hi else f"With {name} you get: ") + " ".join(_clip_words(x, 36) for x in b)
    if topic == "apply":
        if hi:
            # The Hindi record is machine-translated into long run-on text (26 of 56 sampled records), which
            # sounds wrong when spoken. Describe the routes and send the person to the Details on screen.
            how = _apply_phrase(rec, True)
            if how:
                return f"{name} के लिए {how} पूरे चरण, लिंक और ज़रूरी कागज़ आपकी स्क्रीन पर Details में हैं।"
            return None
        steps = _steps(rec)
        if steps:
            return "Here is how to apply. " + " ".join(steps) + " " + _SHOW_STEPS_EN
    if topic == "docs":
        found: list[str] = []
        probes = [  # (pattern, English label, Hindi label): only what the official steps actually mention
            (r"aadhaar|aadhar|आधार", "Aadhaar", "आधार"),
            (r"passbook|bank (?:account|detail)|बैंक", "bank passbook or account details", "बैंक पासबुक या खाते की जानकारी"),
            (r"land (?:record|holding|registration|paper|detail|ownership|tenure)|khasra|khata|khatauni|ज़मीन|जमीन|खसरा|खतौनी", "land ownership or tenancy papers", "ज़मीन के मालिकाना या पट्टे के कागज़"),
            (r"ration card|राशन", "ration card", "राशन कार्ड"),
            (r"income certificate|आय प्रमाण", "income certificate", "आय प्रमाण पत्र"),
            (r"caste certificate|जाति प्रमाण", "caste certificate", "जाति प्रमाण पत्र"),
            (r"photograph|photo|फोटो", "a passport-size photo", "पासपोर्ट साइज़ फोटो"),
            (r"mobile number|मोबाइल", "a mobile number linked to Aadhaar", "आधार से जुड़ा मोबाइल नंबर"),
        ]
        blob = " ".join(SD.md_to_text(a.get("steps_md")) for a in rec.get("apply") or [])
        for pat, en, hin in probes:
            if re.search(pat, blob, re.IGNORECASE):
                found.append(hin if hi else en)
        if found:
            joined = ", ".join(found[:-1]) + ((" और " if hi else " and ") + found[-1] if len(found) > 1 else found[0] if len(found) == 1 else "")
            joined = joined if len(found) > 1 else found[0]
            lead = "आधिकारिक आवेदन प्रक्रिया में इनका ज़िक्र है: " if hi else "The official application steps mention: "
            tail = " पूरी सूची आधिकारिक पेज पर देख लीजिए।" if hi else " Please check the official page for the complete list."
            return lead + joined + "." + tail
    return None


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


def _present(profile, candidates, lang, turn, question_key, records=None) -> str:
    hi = lang == "hi-IN"
    records = records or {}
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
    rec = records.get(first.get("slug") or "")
    if rec:
        short = rec.get("short_title") or name
        benefit = " ".join(_clip_words(x, 30) for x in _bullets(rec.get("benefits_md") or "", 1, hi))
        who = " ".join(_clip_words(x, 26) for x in _bullets(rec.get("eligibility_md") or "", 1, hi))
        how = _apply_phrase(rec, hi)
        if hi:
            parts.append(f"{short} से आपको मदद मिल सकती है।")
            if benefit: parts.append(f"फ़ायदा: {benefit}")
            if who: parts.append(f"किसके लिए: {who}")
        else:
            parts.append(f"{short} may help.")
            if benefit: parts.append(f"What you get: {benefit}")
            if who: parts.append(f"Who it is for: {who}")
        if how: parts.append(how)
    else:
        desc = _first_sentence(first.get("description_hi") if hi else first.get("description"))
        if hi:
            parts.append(f"{name} से आपको मदद मिल सकती है। {desc}।" if desc else f"{name} आपके काम की हो सकती है।")
        else:
            parts.append(f"{name} may help. {desc}." if desc else f"{name} looks relevant for you.")

    if len(top) > 1:
        second = top[1]
        n2 = (second.get("name_hi") or second.get("name")) if hi else second.get("name")
        parts.append(f"{n2} भी देखने लायक है।" if hi else f"{n2} is also worth a look.")

    parts.append(_SHOW_STEPS_HI if (hi and rec) else _SHOW_STEPS_EN if rec else _pick(CLOSE_HI if hi else CLOSE_EN, turn))
    q = question_text(question_key, lang)
    if q:
        parts.append(q)

    text = " ".join(parts)
    # Keep it speakable: drop the second scheme, then the "who it is for" line, if it runs long.
    for marker in ("also worth a look", "भी देखने लायक", "Who it is for", "किसके लिए"):
        if len(text.split()) <= 85:
            break
        parts = [p for p in parts if marker not in p]
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
    records: dict | None = None,
    has_presented: bool = False,
) -> str:
    """Build the spoken reply for one turn. `language` is already normalised."""
    hi, en = language == "hi-IN", language == "en-IN"
    rich = hi or en

    if mode == "chat":
        if intent == "ack" and rich:
            return _pick((ACK_NEXT_HI if hi else ACK_NEXT_EN) if has_presented else (ASK_HI if hi else ASK_EN), turn)
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

    if mode == "unknown":
        return (UNKNOWN_HI if hi else UNKNOWN_EN) if rich else L.NO_MATCH[language]

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
        first_rec = (records or {}).get(((candidates or [{}])[0]).get("slug") or "")
        if en:
            from app.services.supplement import get_supplement

            sup_answer = _supplement_answer(topic, get_supplement(((candidates or [{}])[0]).get("slug")))
            if sup_answer:
                return sup_answer
        concrete = _details_answer(topic, first_rec, hi)
        if concrete:
            return concrete
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
    return _present(profile, candidates, language, turn, question_key, records)
