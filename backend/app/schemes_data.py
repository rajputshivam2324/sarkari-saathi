"""Curated catalogue of real Indian central welfare / livelihood schemes."""

from typing import Any

SCHEMES: list[dict[str, Any]] = [
    {
        "id": "pm-kisan",
        "name": "PM-KISAN",
        "name_hi": "प्रधानमंत्री किसान सम्मान निधि",
        "category": "agriculture",
        "eligibility_keywords": [
            "farmer",
            "kisan",
            "agriculture",
            "farm",
            "किसान",
            "खेती",
            "landholder",
            "small farmer",
            "marginal farmer",
        ],
        "description": (
            "Income support of ₹6,000 per year in three instalments for eligible "
            "landholding farmer families across India."
        ),
        "description_hi": (
            "पात्र भूमिधारक किसान परिवारों को प्रति वर्ष ₹6,000 की आय सहायता तीन किस्तों में।"
        ),
        "official_url": "https://pmkisan.gov.in/",
    },
    {
        "id": "ayushman-bharat",
        "name": "Ayushman Bharat – PM-JAY",
        "name_hi": "आयुष्मान भारत – प्रधानमंत्री जन आरोग्य योजना",
        "category": "health",
        "eligibility_keywords": [
            "health",
            "hospital",
            "insurance",
            "medical",
            "treatment",
            "बीमा",
            "अस्पताल",
            "इलाज",
            "स्वास्थ्य",
            "poor",
            "secc",
        ],
        "description": (
            "Health cover of up to ₹5 lakh per family per year for secondary and "
            "tertiary care hospitalisation for eligible poor and vulnerable families."
        ),
        "description_hi": (
            "पात्र गरीब परिवारों के लिए प्रति वर्ष ₹5 लाख तक का स्वास्थ्य बीमा कवर।"
        ),
        "official_url": "https://pmjay.gov.in/",
    },
    {
        "id": "pmay-u",
        "name": "Pradhan Mantri Awas Yojana – Urban",
        "name_hi": "प्रधानमंत्री आवास योजना – शहरी",
        "category": "housing",
        "eligibility_keywords": [
            "house",
            "housing",
            "home",
            "awas",
            "flat",
            "urban",
            "city",
            "घर",
            "आवास",
            "मकान",
            "शहर",
        ],
        "description": (
            "Affordable housing assistance for eligible urban households through "
            "subsidy, credit-linked subsidy, and beneficiary-led construction."
        ),
        "description_hi": (
            "शहरी पात्र परिवारों के लिए सब्सिडी और ऋण सहायता के ज़रिए किफायती आवास।"
        ),
        "official_url": "https://pmaymis.gov.in/",
    },
    {
        "id": "pmay-g",
        "name": "Pradhan Mantri Awas Yojana – Gramin",
        "name_hi": "प्रधानमंत्री आवास योजना – ग्रामीण",
        "category": "housing",
        "eligibility_keywords": [
            "house",
            "housing",
            "rural",
            "village",
            "awas",
            "घर",
            "आवास",
            "गाँव",
            "ग्रामीण",
            "kutcha",
        ],
        "description": (
            "Financial assistance to build pucca houses for eligible rural households "
            "living in kutcha or dilapidated dwellings."
        ),
        "description_hi": (
            "ग्रामीण पात्र परिवारों को पक्का घर बनाने हेतु वित्तीय सहायता।"
        ),
        "official_url": "https://pmayg.nic.in/",
    },
    {
        "id": "ujjwala",
        "name": "Pradhan Mantri Ujjwala Yojana",
        "name_hi": "प्रधानमंत्री उज्ज्वला योजना",
        "category": "energy",
        "eligibility_keywords": [
            "lpg",
            "gas",
            "cylinder",
            "cooking",
            "kitchen",
            "ujjwala",
            "गैस",
            "रसोई",
            "सिलेंडर",
            "महिला",
            "woman",
            "bpl",
        ],
        "description": (
            "LPG connections for women from eligible households to promote clean "
            "cooking fuel and reduce indoor smoke."
        ),
        "description_hi": (
            "पात्र परिवारों की महिलाओं को स्वच्छ खाना पकाने हेतु एलपीजी कनेक्शन।"
        ),
        "official_url": "https://www.pmuy.gov.in/",
    },
    {
        "id": "mgnrega",
        "name": "MGNREGA",
        "name_hi": "महात्मा गांधी राष्ट्रीय ग्रामीण रोजगार गारंटी योजना",
        "category": "employment",
        "eligibility_keywords": [
            "job",
            "employment",
            "wage",
            "work",
            "labour",
            "labor",
            "unemployed",
            "rural",
            "नौकरी",
            "रोजगार",
            "मजदूरी",
            "काम",
            "बेरोजगार",
            "गाँव",
        ],
        "description": (
            "Legal guarantee of at least 100 days of wage employment in a financial "
            "year to every rural household whose adult members volunteer for unskilled work."
        ),
        "description_hi": (
            "ग्रामीण परिवारों को प्रति वित्तीय वर्ष कम से कम 100 दिन का मजदूरी रोजगार।"
        ),
        "official_url": "https://nrega.nic.in/",
    },
    {
        "id": "pmjdy",
        "name": "Pradhan Mantri Jan Dhan Yojana",
        "name_hi": "प्रधानमंत्री जन धन योजना",
        "category": "finance",
        "eligibility_keywords": [
            "bank",
            "account",
            "savings",
            "jan dhan",
            "zero balance",
            "बैंक",
            "खाता",
            "बचत",
            "जन धन",
            "rupee debit",
        ],
        "description": (
            "Basic savings bank accounts with RuPay debit card, overdraft facility "
            "eligibility, and access to insurance and pension products."
        ),
        "description_hi": (
            "बेसिक बचत खाता, रुपे डेबिट कार्ड और बीमा/पेंशन उत्पादों तक पहुँच।"
        ),
        "official_url": "https://pmjdy.gov.in/",
    },
    {
        "id": "atal-pension",
        "name": "Atal Pension Yojana",
        "name_hi": "अटल पेंशन योजना",
        "category": "pension",
        "eligibility_keywords": [
            "pension",
            "retirement",
            "old age",
            "senior",
            "unorganised",
            "पेंशन",
            "बुजुर्ग",
            "रिटायर",
            "अटल",
            "worker",
        ],
        "description": (
            "Guaranteed pension scheme for citizens aged 18–40 in the unorganised "
            "sector, with monthly pension options from ₹1,000 to ₹5,000 after 60."
        ),
        "description_hi": (
            "असंगठित क्षेत्र के 18–40 वर्ष आयु वर्ग के लिए गारंटीड पेंशन योजना।"
        ),
        "official_url": "https://www.npscra.nsdl.co.in/scheme-details.php",
    },
    {
        "id": "pm-fasal-bima",
        "name": "Pradhan Mantri Fasal Bima Yojana",
        "name_hi": "प्रधानमंत्री फसल बीमा योजना",
        "category": "agriculture",
        "eligibility_keywords": [
            "crop",
            "insurance",
            "farm",
            "farmer",
            "fasal",
            "drought",
            "flood",
            "फसल",
            "बीमा",
            "किसान",
            "सूखा",
            "बाढ़",
        ],
        "description": (
            "Crop insurance for notified crops against yield losses from natural "
            "calamities, pests, and diseases, with low premium for farmers."
        ),
        "description_hi": (
            "प्राकृतिक आपदाओं से फसल नुकसान हेतु कम प्रीमियम पर फसल बीमा।"
        ),
        "official_url": "https://pmfby.gov.in/",
    },
    {
        "id": "mudra",
        "name": "Pradhan Mantri MUDRA Yojana",
        "name_hi": "प्रधानमंत्री मुद्रा योजना",
        "category": "livelihood",
        "eligibility_keywords": [
            "loan",
            "business",
            "shop",
            "msme",
            "startup",
            "mudra",
            "self employed",
            "ऋण",
            "लोन",
            "व्यवसाय",
            "दुकान",
            "उद्यम",
            "मुद्रा",
        ],
        "description": (
            "Collateral-free loans up to ₹20 lakh for non-corporate, non-farm micro "
            "enterprises under Shishu, Kishor, Tarun and Tarun Plus categories."
        ),
        "description_hi": (
            "सूक्ष्म उद्यमों के लिए बिना गिरवी के ₹20 लाख तक का ऋण।"
        ),
        "official_url": "https://www.mudra.org.in/",
    },
    {
        "id": "standup-india",
        "name": "Stand-Up India",
        "name_hi": "स्टैंड-अप इंडिया",
        "category": "livelihood",
        "eligibility_keywords": [
            "loan",
            "business",
            "sc",
            "st",
            "woman",
            "women",
            "entrepreneur",
            "startup",
            "महिला",
            "उद्यमी",
            "ऋण",
            "दलित",
            "आदिवासी",
        ],
        "description": (
            "Bank loans between ₹10 lakh and ₹1 crore for SC/ST and women entrepreneurs "
            "setting up a greenfield enterprise."
        ),
        "description_hi": (
            "एससी/एसटी और महिला उद्यमियों के लिए ₹10 लाख से ₹1 करोड़ तक का बैंक ऋण।"
        ),
        "official_url": "https://www.standupmitra.in/",
    },
    {
        "id": "pm-svanidhi",
        "name": "PM SVANidhi",
        "name_hi": "पीएम स्वनिधि",
        "category": "livelihood",
        "eligibility_keywords": [
            "street vendor",
            "vendor",
            "hawker",
            "thela",
            "cart",
            "loan",
            "रेहड़ी",
            "ठेला",
            "विक्रेता",
            "स्ट्रीट",
            "फुटपाथ",
        ],
        "description": (
            "Affordable working-capital loans for street vendors, with interest "
            "subsidy and digital-payment incentives on timely repayment."
        ),
        "description_hi": (
            "स्ट्रीट वेंडर्स के लिए सस्ता कार्यशील पूँजी ऋण और डिजिटल भुगतान प्रोत्साहन।"
        ),
        "official_url": "https://pmsvanidhi.mohua.gov.in/",
    },
    {
        "id": "nsp-scholarship",
        "name": "National Scholarship Portal schemes",
        "name_hi": "राष्ट्रीय छात्रवृत्ति पोर्टल योजनाएँ",
        "category": "education",
        "eligibility_keywords": [
            "student",
            "scholarship",
            "school",
            "college",
            "education",
            "fees",
            "छात्र",
            "छात्रवृत्ति",
            "स्कॉलरशिप",
            "पढ़ाई",
            "कॉलेज",
            "स्कूल",
        ],
        "description": (
            "Central and state scholarships for school and higher-education students "
            "from eligible categories, applied via the National Scholarship Portal."
        ),
        "description_hi": (
            "पात्र छात्रों के लिए केंद्रीय/राज्य छात्रवृत्ति — आवेदन राष्ट्रीय छात्रवृत्ति पोर्टल पर।"
        ),
        "official_url": "https://scholarships.gov.in/",
    },
    {
        "id": "eshram",
        "name": "e-Shram",
        "name_hi": "ई-श्रम",
        "category": "labour",
        "eligibility_keywords": [
            "worker",
            "labour",
            "labor",
            "unorganised",
            "gig",
            "construction",
            "मजदूर",
            "श्रमिक",
            "असंगठित",
            "निर्माण",
            "कामगार",
        ],
        "description": (
            "National database for unorganised workers with a Universal Account "
            "Number (UAN), enabling access to social security and welfare schemes."
        ),
        "description_hi": (
            "असंगठित श्रमिकों का राष्ट्रीय डेटाबेस और यूएएन — सामाजिक सुरक्षा योजनाओं तक पहुँच।"
        ),
        "official_url": "https://eshram.gov.in/",
    },
    {
        "id": "pm-kisan-maandhan",
        "name": "PM Kisan Maandhan Yojana",
        "name_hi": "पीएम किसान मानधन योजना",
        "category": "pension",
        "eligibility_keywords": [
            "farmer",
            "pension",
            "kisan",
            "old age",
            "small farmer",
            "किसान",
            "पेंशन",
            "मानधन",
            "छोटा किसान",
        ],
        "description": (
            "Voluntary contributory pension for small and marginal farmers aged "
            "18–40, providing ₹3,000 monthly pension after age 60."
        ),
        "description_hi": (
            "18–40 वर्ष के छोटे/सीमांत किसानों के लिए अंशदायी पेंशन — 60 वर्ष के बाद ₹3,000 प्रति माह।"
        ),
        "official_url": "https://maandhan.in/",
    },
    {
        "id": "pm-vishwakarma",
        "name": "PM Vishwakarma",
        "name_hi": "पीएम विश्वकर्मा",
        "category": "livelihood",
        "eligibility_keywords": [
            "artisan",
            "craftsman",
            "carpenter",
            "blacksmith",
            "potter",
            "tailor",
            "skill",
            "कारीगर",
            "शिल्पकार",
            "बढ़ई",
            "लुहार",
            "कुम्हार",
            "दर्जी",
            "हुनर",
        ],
        "description": (
            "Support for traditional artisans and craftspeople with skill training, "
            "toolkit incentive, credit support, and marketing assistance."
        ),
        "description_hi": (
            "पारंपरिक कारीगरों के लिए कौशल प्रशिक्षण, टूलकिट प्रोत्साहन, ऋण और विपणन सहायता।"
        ),
        "official_url": "https://pmvishwakarma.gov.in/",
    },
    {
        "id": "nsap-ignoaps",
        "name": "Indira Gandhi National Old Age Pension Scheme",
        "name_hi": "इंदिरा गांधी राष्ट्रीय वृद्धावस्था पेंशन योजना",
        "category": "pension",
        "eligibility_keywords": [
            "senior",
            "old age",
            "elderly",
            "pension",
            "widow",
            "disability",
            "बुजुर्ग",
            "वृद्ध",
            "पेंशन",
            "विधवा",
            "दिव्यांग",
            "nsap",
        ],
        "description": (
            "Monthly pension under NSAP for below-poverty-line elderly (and related "
            "widow / disability pensions) administered with state top-ups."
        ),
        "description_hi": (
            "बीपीएल वृद्धजनों के लिए राष्ट्रीय सामाजिक सहायता कार्यक्रम के तहत मासिक पेंशन।"
        ),
        "official_url": "https://nsap.nic.in/",
    },
    {
        "id": "nrlm",
        "name": "Deendayal Antyodaya Yojana – NRLM",
        "name_hi": "दीनदयाल अंत्योदय योजना – राष्ट्रीय ग्रामीण आजीविका मिशन",
        "category": "livelihood",
        "eligibility_keywords": [
            "shg",
            "women",
            "self help",
            "livelihood",
            "rural",
            "lakhpati",
            "group",
            "महिला",
            "स्वयं सहायता",
            "समूह",
            "आजीविका",
            "ग्रामीण",
            "लखपति",
        ],
        "description": (
            "Organises rural poor women into Self Help Groups and provides credit, "
            "livelihood support, and market linkages toward sustainable incomes."
        ),
        "description_hi": (
            "ग्रामीण महिलाओं को स्वयं सहायता समूहों में संगठित कर ऋण और आजीविका सहायता।"
        ),
        "official_url": "https://aajeevika.gov.in/",
    },
]


def get_all_schemes() -> list[dict[str, Any]]:
    return [dict(s) for s in SCHEMES]


def get_scheme_by_id(scheme_id: str) -> dict[str, Any] | None:
    for scheme in SCHEMES:
        if scheme["id"] == scheme_id:
            return dict(scheme)
    return None


def scheme_keyterms() -> list[str]:
    """Short terms for Prisma STT keyterms boosting."""
    terms = [
        "योजना",
        "किसान",
        "आवास",
        "पेंशन",
        "छात्रवृत्ति",
        "रोजगार",
        "बीमा",
        "सरकारी",
        "scheme",
        "farmer",
        "pension",
        "housing",
        "scholarship",
        "MUDRA",
        "Ujjwala",
        "Ayushman",
    ]
    return terms
