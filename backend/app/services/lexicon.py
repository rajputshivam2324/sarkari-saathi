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
_APPLY = re.compile(r"\b(how (?:do|can|to|should) (?:i |we )?(?:apply|register|enrol|enroll|get it)|apply|application|form|register|avedan|aavedan|kaise kare|kaise karen|kaise karu)\b|आवेदन|अप्लाई|फॉर्म|रजिस्टर|कैसे (?:करें|करूं|मिलेगा|मिलेगी)", re.IGNORECASE)
_DOCS = re.compile(r"\b(documents?|papers?|proof|certificate|aadhaar|aadhar|kagaz|dastavez|dastaavez)\b|दस्तावेज़?|कागज़?|कागज|प्रमाण", re.IGNORECASE)


def is_yes(text: str) -> bool:
    return bool(_YES.search(text or "")) and not _NO.search(text or "")


def is_no(text: str) -> bool:
    return bool(_NO.search(text or ""))


_ELIGIBLE = re.compile(r"\b(eligible|eligibility|qualify|qualified|who can|can i get|am i|who is it for|criteria|patra|patrata|kaun le sakta)\b|पात्र|पात्रता|कौन ले सकता|किसे मिलेगा|मुझे मिलेगा|योग्य", re.IGNORECASE)
_BENEFIT = re.compile(r"\b(benefit|benefits|how much|amount|money|get|receive|gives?|installment|instalment|fayda|labh|kitna|kitne|kitni|paisa|paise|milega|milegi)\b|फायदा|लाभ|कितना|कितने|कितनी|रुपये|पैसे|रकम|क्या मिलेगा|क्या मिलता", re.IGNORECASE)


_I = re.IGNORECASE
# Most specific first. Each one is a kind of question people really ask about a scheme (English, romanised
# Hindi and Devanagari). The topic decides which part of the official record the model reads in full.
_HELP = re.compile(
    r"\b(helpline|help\s?line|toll[\s-]?free|customer care|contact|complain\w*|grievance|appeal|unfair\w*|officer|phone number|number to call|"
    r"who (?:do|should|can) i (?:call|contact|ask)|shikayat|sampark)\b|शिकायत|हेल्पलाइन|संपर्क|अपील|अधिकारी|टोल फ्री|कंप्लेंट|फोन नंबर",
    _I,
)
_STATUS = re.compile(
    r"\b(status|approved|approval|rejected|rejection|processing time|(?:haven'?t|have not|not|didn'?t|did not) (?:yet )?(?:received|got|come|credited)|"
    r"when will i (?:receive|get)|when (?:will|does) (?:the )?(?:money|payment|amount|installment|instalment)|payment (?:status|date|delay|kab)|"
    r"correct (?:my|the)|edit (?:my|the)|update (?:my|the) (?:application|details)|mistake in (?:my )?(?:application|form)|track|paisa kab)\b|"
    r"स्थिति|स्टेटस|मंज़ूर|मंजूर|रद्द|खारिज|भुगतान|पैसा (?:कब|नहीं)|कब (?:आएगा|आयेगा|मिलेगा|तक आएगा)|कितने दिन|ग़लती|गलती|सुधार|ट्रैक",
    _I,
)
_COMPARE = re.compile(
    r"\b(difference between|differences? (?:of|in)|compare|comparison|versus|vs\.?|better than|which (?:one )?is better|similar schemes?|farq|behtar)\b|फ़र्क|फर्क|अंतर|तुलना|बेहतर",
    _I,
)
_DOCS_EXTRA = re.compile(r"\b(domicile|passbook|ration card|income certificate|caste certificate|birth certificate|photograph|photo id|id proof|address proof|without (?:a |an )?(?:aadhaar|aadhar|ration card))\b|निवास प्रमाण|राशन कार्ड|पासबुक|पहचान पत्र", _I)
_ELIG_SPECIFIC = re.compile(
    r"\b(age limit|minimum age|maximum age|upper age|lower age|how old|income limit|income ceiling|annual income|income criteria|"
    r"students? (?:can )?apply|can (?:a |an )?(?:women|woman|girls?|men|students?|farmers?|widows?|seniors?|senior citizens?|disabled|divyang|tenant farmers?|unmarried|married)|"
    r"sc/?st|obc|ews|scheduled (?:caste|tribe)|caste|category|categories|rural and urban|rural or urban|urban|rural|"
    r"already (?:receiving|getting|have|taking|benefit)|another scheme|other scheme benefits?|two (?:government )?schemes|both schemes|simultaneously|same time|"
    r"who can benefit|who is it for|who are eligible|who is eligible|who qualifies|am i eligible|do i qualify|eligib\w+ (?:criteria|to apply|for))\b|"
    r"उम्र|आयु|आय सीमा|आमदनी|महिला|छात्र|ग्रामीण|शहरी|एक साथ|दो योजनाओं|पहले से|किसे|कौन ले सकता|कौन-कौन",
    _I,
)
_ACTIVE = re.compile(
    r"\b(still (?:active|running|open|valid|accepting|on)|currently (?:active|running|open|valid|accepting)|is (?:it|this|the scheme) (?:active|open|closed|running|valid)|"
    r"accepting applications?|applications? (?:open|closed)|last date|closing date|deadline|due date|till when|until when|open now|"
    r"in 202\d|this year|band ho|chalu)\b|अंतिम तारीख|आखिरी तारीख|अंतिम तिथि|चालू है|बंद हो|कब तक|इस साल",
    _I,
)
_BASICS = re.compile(
    r"\b(objective|purpose|aim of|main aim|why was|launched|launch date|when was (?:it|this|the)|when did (?:it|this|the)|since when|"
    r"which government|who (?:started|launched|runs|started it)|run by|ministry|department|central (?:or|government)|state (?:or|government)|"
    r"central scheme|state scheme|what is (?:this|the) (?:government )?scheme|what does (?:this|the) scheme)\b|"
    r"उद्देश्य|मकसद|किसने शुरू|कब शुरू|कब लॉन्च|मंत्रालय|केंद्र (?:सरकार|या)|राज्य सरकार की",
    _I,
)
_BENEFIT_EXTRA = re.compile(
    r"\b(monthly|yearly|annual(?:ly)?|one[\s-]?time|lump ?sum|directly (?:in|to|into)|dbt|direct benefit|additional benefits?|extra benefits?|"
    r"how long will i (?:receive|get)|for how long|how many years|duration)\b|मासिक|वार्षिक|साल में|सीधे|खाते में|कितने साल|अतिरिक्त",
    _I,
)
_OTHER_SCHEMES = re.compile(
    r"\b(which (?:government |other |more |new |central |state )?schemes?|what (?:other |more |new |government )?schemes?|other schemes?|more schemes?|"
    r"any (?:other |new |more )?schemes?|schemes? (?:for|available|that|in)|new(?:ly)? launched|new schemes?|latest schemes?|schemes? i can)\b|"
    r"कौन ?सी (?:\w+ )?योजना|कोई और योजना|और (?:कौन ?सी )?योजना|नई योजना|दूसरी योजना|कौन-कौन सी योजना",
    _I,
)

TOPICS = ("help", "status", "compare", "docs", "eligibility", "active", "basics", "apply", "benefits")


def followup_topic(text: str) -> str | None:
    """What a question about a scheme is about.

    'help' (helpline, complaints, appeal) | 'status' (application status, approval, payment) |
    'compare' | 'docs' | 'eligibility' | 'active' (open now, last date) | 'basics' (objective, launch,
    who runs it) | 'apply' | 'benefits' | None.
    """
    t = text or ""
    if _HELP.search(t):
        return "help"
    if _STATUS.search(t):
        return "status"
    if _COMPARE.search(t):
        return "compare"
    if _DOCS.search(t) or _DOCS_EXTRA.search(t):
        return "docs"
    if _ELIG_SPECIFIC.search(t):
        return "eligibility"
    if _ACTIVE.search(t):
        return "active"
    if _BASICS.search(t):
        return "basics"
    if _APPLY.search(t):
        return "apply"
    if _ELIGIBLE.search(t):
        return "eligibility"
    if _BENEFIT_EXTRA.search(t) or _BENEFIT.search(t):
        return "benefits"
    return None


def wants_other_schemes(text: str) -> bool:
    """True when the person is asking WHICH schemes exist for them, not about the scheme already on screen."""
    return bool(_OTHER_SCHEMES.search(text or ""))


_ACK = re.compile(
    r"^\W*(?:ok(?:ay)?|okk+|k|alright|all right|fine|sure|cool|great|nice|good|got it|i see|i understand|understood|makes sense|"
    r"theek hai|thik hai|accha|achha|acha|samajh gaya|samajh gayi|samajh aa gaya|ji|"
    r"ठीक है|ठीक|अच्छा|अच्छी बात|समझ गया|समझ गई|समझ गयी|समझ आ गया|जी|ओके|ओके ठीक है|बढ़िया|बहुत अच्छा)"
    r"(?:\W+(?:ok(?:ay)?|got it|thanks?|thank you|fine|sure|ji|जी|ठीक है|समझ गया|समझ गई|अच्छा|धन्यवाद|शुक्रिया))*\W*$",
    re.IGNORECASE,
)


def _hit(text: str, patterns: list[str]) -> bool:
    return any(re.search(p, text, flags=re.IGNORECASE) for p in patterns)


def classify_intent(text: str) -> str:
    """greeting | thanks | bye | ack | other. Only used for short utterances."""
    t = (text or "").strip()
    if len(t.split()) > 6:
        return "other"
    if _BYE.search(t):
        return "bye"
    if _GREETING.match(t):
        return "greeting"
    if _THANKS.search(t):
        return "thanks"
    if _ACK.match(t):
        return "ack"
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


_SCRIPT_LANG: list[tuple[int, int, str]] = [
    (0x0900, 0x097F, "hi-IN"),   # Devanagari (Hindi / Marathi)
    (0x0980, 0x09FF, "bn-IN"),
    (0x0A00, 0x0A7F, "pa-IN"),
    (0x0A80, 0x0AFF, "gu-IN"),
    (0x0B80, 0x0BFF, "ta-IN"),
    (0x0C00, 0x0C7F, "te-IN"),
    (0x0C80, 0x0CFF, "kn-IN"),
    (0x0D00, 0x0D7F, "ml-IN"),
]
_INDIC_CODES = {"hi-IN", "mr-IN", "bn-IN", "pa-IN", "gu-IN", "ta-IN", "te-IN", "kn-IN", "ml-IN"}
# Romanised Hindi ("Hinglish") markers: typing these means "answer in Hindi", not English.
# Strong: unmistakably romanised Hindi, so one is enough. Weak: short words that are also English
# ("me", "to", "main") or very short tokens, so they only count together with something else.
_HINGLISH_STRONG = set(
    "mujhe mera meri mere hamara aap aapka aapki kya kaise kaun kab kahan kyun kitna kitni kitne hain nahi nahin nhi "
    "chahiye chahie karna karni karo kare kijiye batao bataiye bataye batana madad paisa paise abhi lekin kuch koi "
    "accha theek thik haan bilkul samajh samjha dhanyavad shukriya milega milegi milta hoga hogi kisko iske uske "
    "baare baarein liye wala wali wale apna apni bahut bohot zyada thoda sirf yahan wahan ghar khet kheti naukri padhai "
    "ilaaj dawai bimari jankari jaankari sarkari".split()
)
_HINGLISH_WEAK = set("hai ho ka ke ki ko se mein me par pe aur ya bhi toh tha thi main mai hum sab".split())
# Words that belong to scheme names or are loanwords inside English sentences: never evidence.
_NAME_WORDS = {"yojana", "yojna", "kisan", "mantri", "pradhan", "samman", "nidhi", "bharat", "shram", "vishwakarma", "ujjwala", "mudra", "awas", "gramin", "pension", "bima", "fasal"}


def _looks_hinglish(words: list[str]) -> bool:
    ws = [w for w in words if w not in _NAME_WORDS]
    strong = sum(w in _HINGLISH_STRONG for w in ws)
    weak = sum(w in _HINGLISH_WEAK for w in ws)
    return strong >= 1 or weak >= 2


def infer_reply_language(text: str, selected: str) -> str:
    """Reply in the language the person is actually using, not just the dropdown.

    Native script wins. Romanised Hindi gets Hindi. A real English sentence gets English even if
    the dropdown says Hindi. A very short Latin reply ("ok", "thanks") keeps the current language.
    """
    letters = [c for c in (text or "") if c.isalpha()]
    if not letters:
        return selected
    counts: dict[str, int] = {}
    for c in letters:
        o = ord(c)
        for lo, hi, code in _SCRIPT_LANG:
            if lo <= o <= hi:
                counts[code] = counts.get(code, 0) + 1
                break
    indic = sum(counts.values())
    if indic >= max(2, len(letters) * 0.3):
        top = max(counts, key=counts.get)
        if top == "hi-IN" and selected == "mr-IN":
            return "mr-IN"          # Devanagari is shared; keep Marathi if that is what they chose
        return top
    words = re.findall(r"[a-z]+", (text or "").lower())
    if _looks_hinglish(words):
        return selected if selected in _INDIC_CODES else "hi-IN"
    if len(words) >= 3:
        return "en-IN"
    return selected


_ASKS_ABOUT_NAMED = re.compile(
    r"\b(?:[a-z][a-z'-]+\s+){0,4}(?:yojana|yojna|scheme|abhiyan|mission|programme|program)\b|(?:योजना|स्कीम|अभियान|मिशन)",
    re.IGNORECASE,
)


def mentions_a_scheme_name(text: str) -> bool:
    """True if the person seems to be asking about one particular scheme by name ("... Yojana", "... योजना").

    Used so that an unknown scheme name is reported as unknown, instead of being turned into a
    generic need-based search that returns unrelated schemes.
    """
    t = text or ""
    if not _ASKS_ABOUT_NAMED.search(t):
        return False
    # "I need a scheme for farmers" is a need, not a name: require a capitalised word or an Indic word before it
    m = re.search(r"([A-Z][A-Za-z\-']{2,}(?:\s+[A-Z][A-Za-z\-']{2,}){0,3})\s+(?:Yojana|Yojna|Scheme|Abhiyan|Mission)", t)
    if m and m.group(1).split()[0].lower() not in {"the", "a", "an", "this", "that", "any", "some", "tell", "what", "which", "how", "please", "about", "i", "my", "i'm"}:
        return True
    # Devanagari: the word right before योजना must be a name, not a generic "some/any/which/this/that/a"
    m2 = re.search(r"([\u0900-\u097F]+)\s*(?:योजना|स्कीम|अभियान|मिशन)", t)
    if not m2:
        return False
    generic = {"कोई", "कौन", "कौनसी", "कौन-सी", "कौन सी", "यह", "ये", "वह", "वो", "इस", "उस", "एक", "कुछ", "सभी", "सारी", "हर", "के", "की", "का", "में", "लिए", "बारे", "सरकारी", "भारत", "सरकार", "सब", "कोई-सी", "मदद", "अच्छी", "नई", "नयी"}
    return m2.group(1) not in generic and len(m2.group(1)) >= 3
