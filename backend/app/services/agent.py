"""Live conversation turn.

    what they said ─► understand (profile from all turns, intent, language they are using)
                   ─► decide the mode: chat | ask | present | answer | followup
                   ─► pick schemes (new search, or the ones already on screen for a follow-up)
                   ─► load each scheme's official record (benefits, eligibility, how to apply)
                   ─► the LLM writes the reply from those facts (strong prompt + trusted CONTEXT)
                   ─► guardrails check it                      (else the rule-based dialogue speaks)

The model chooses the words. The app controls the substance: which schemes exist, what is true
about them, whether a question may be asked, and whether the reply is safe to say out loud.
"""

from __future__ import annotations

import logging
import re
from typing import Any

from app.services import dialogue_prompt as P
from app.services import fallback as F
from app.services import guardrails, llm
from app.services import scheme_details as SD
from app.services.languages import normalize_lang
from app.services.lexicon import (
    build_profile,
    classify_intent,
    followup_topic,
    infer_reply_language,
    is_no,
    mentions_a_scheme_name,
    is_yes,
    public_profile,
    wants_other_schemes,
)
from app.services.prompt_cache import get_system_prompt
from app.services.retrieval import retrieve
from app.services.scheme_lookup import find_named_schemes
from app.services.supplement import get_supplement

logger = logging.getLogger(__name__)

DETAIL_COUNT = 3   # how many schemes get their official record in a turn (records are cached, so this costs little)
RICH_TOPICS = {"basics", "eligibility", "benefits", "docs", "apply", "status", "help", "active", "compare"}

_QUESTION_CUE = re.compile(
    r"\?|？|\b(can|could|is|are|am|do|does|did|will|would|what|which|who|whom|where|when|how|why|should|kya|kaise|kab|kahan|kitna|kitni|kaun)\b"
    r"|क्या|कौन|कैसे|कब|कहाँ|कहां|कितन|क्यों|कहाँ|चाहिए",
    re.IGNORECASE,
)


def _question_like(text: str) -> bool:
    return bool(_QUESTION_CUE.search(text or ""))


def _user_turns(history: list[dict[str, Any]], text: str) -> list[str]:
    """All user utterances including the current one, without double-counting it."""
    turns = [m["text"].strip() for m in history if m.get("role") == "user" and (m.get("text") or "").strip()]
    if not turns or turns[-1] != text.strip():
        turns.append(text.strip())
    return turns


def _answers_last_question(assistant_msgs: list[dict[str, Any]], text: str) -> str:
    """If the user is replying to a question Saathi just asked, return that question's text."""
    if not assistant_msgs or "?" in text or "？" in text or len(text.split()) > 12:
        return ""
    last = (assistant_msgs[-1].get("text") or "").strip()
    return last if last.endswith(("?", "？")) else ""


def _looks_unclear(text: str) -> bool:
    """Very short or symbol-only input: most likely a speech-recognition fragment."""
    letters = sum(c.isalpha() for c in text)
    return letters < 3 or len(text.split()) < 2 and letters < 5


def _last_presented(assistant_msgs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    for m in reversed(assistant_msgs):
        if m.get("schemes"):
            return list(m["schemes"])
    return []


def _focus_first(schemes: list[dict[str, Any]], text: str) -> list[dict[str, Any]]:
    """Put the scheme the person is talking about first, if they name one ("how do I apply for PM-KISAN")."""
    words = {w for w in re.findall(r"[a-z0-9\u0900-\u097F][a-z0-9\u0900-\u097F\-]{2,}", text.lower())}
    if not words:
        return schemes

    def score(s: dict[str, Any]) -> int:
        blob = f"{s.get('name', '')} {s.get('name_hi', '')} {s.get('slug', '') or ''} {s.get('id', '')}".lower()
        tokens = {t for t in re.findall(r"[a-z0-9\u0900-\u097F][a-z0-9\u0900-\u097F\-]{2,}", blob)}
        generic = {"yojana", "yojna", "scheme", "pradhan", "mantri", "national", "for", "the", "and", "योजना", "प्रधानमंत्री"}
        return len((words & tokens) - generic)

    scored = [(score(s), i, s) for i, s in enumerate(schemes)]
    if max((x[0] for x in scored), default=0) == 0:
        return schemes
    return [s for _, _, s in sorted(scored, key=lambda x: (-x[0], x[1]))]


async def _with_facts(
    schemes: list[dict[str, Any]],
    *,
    full: bool,
    topic: str | None = None,
    question: str = "",
) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]]]:
    """Copies of the schemes carrying `facts` text from each one's official record.

    Records are read in English (the cleanest text for the model, which then speaks in the person's
    language). The scheme being discussed gets the long form for the kind of question asked; for a
    comparison, the first two do. Schemes with no record keep their short curated description.
    """
    top = schemes[:DETAIL_COUNT]
    records = await SD.get_many([s.get("slug") for s in top], "en")
    long_form = 2 if topic == "compare" else 1
    out: list[dict[str, Any]] = []
    for i, s in enumerate(schemes[:3]):
        item = dict(s)
        rec = records.get(s.get("slug") or "") if i < DETAIL_COUNT else None
        if rec:
            item["facts"] = SD.facts_text(
                rec,
                full=full and i < long_form,
                topic=topic if full and i < long_form else None,
                question=question,
                supplement=get_supplement(s.get("slug")),
            )
        out.append(item)
    return out, records


async def handle_utterance(
    text: str,
    *,
    history: list[dict[str, Any]] | None = None,
    language: str | None = None,
) -> dict[str, Any]:
    history = history or []
    text = (text or "").strip()
    lang = infer_reply_language(text, normalize_lang(language))

    turns = _user_turns(history, text)
    profile = build_profile(turns)
    named = await find_named_schemes(text)          # "tell me about Ujjwala yojana"
    if named:
        # Their need follows from the scheme they asked about, so the rest of the flow just works.
        cats = {s.get("category") for s in named if s.get("category")}
        profile["needs"] = sorted(set(profile.get("needs") or []) | cats)
    prev_profile = build_profile(turns[:-1]) if len(turns) > 1 else {"needs": []}
    intent = classify_intent(text)
    topic_now = followup_topic(text)

    assistant_msgs = [m for m in history if m.get("role") == "assistant"]
    presented = _last_presented(assistant_msgs)
    already_presented = bool(presented)
    new_needs = sorted(set(profile.get("needs") or []) - set(prev_profile.get("needs") or []))
    turn_no = len(turns)

    # ---- decide the mode and the schemes ------------------------------------------------
    candidates: list[dict[str, Any]] = []
    unclear = False
    last_question = ""
    refocus = False
    present_cards = False        # show scheme cards even when the answer is a "followup"
    unknown_scheme = False

    already_named = named and {s.get("id") for s in named} <= {s.get("id") for s in presented}

    if named and not already_named:
        # They asked about a specific scheme: show it (not a generic search) and talk about it.
        candidates = named
        refocus = False
        # "How do I apply for Ujjwala?" names a scheme AND asks something specific: answer that with
        # the full record. A bare "tell me about Ujjwala" gets the short introduction instead.
        mode = "followup" if topic_now else "present"
        present_cards = True
    elif intent in ("thanks", "bye", "ack") or (intent == "greeting" and not profile.get("needs")):
        mode = "chat"
        if intent == "ack" and already_presented:
            candidates = presented          # lets the model offer a concrete next step about what was shown
    elif named and already_named:
        # They are asking more about a scheme that is already on screen.
        candidates = _focus_first(presented, text)
        mode = "followup"
    elif already_presented and topic_now in RICH_TOPICS and _question_like(text) and (topic_now == "compare" or not wants_other_schemes(text)):
        # "Is Aadhaar mandatory?", "what is the helpline?", "can women apply?" about the scheme on screen.
        # Handled before the need-based branches so a word like "women" or "income" is not read as a new search.
        candidates = _focus_first(presented, text)
        mode = "followup"
    elif already_presented and profile.get("needs") and wants_other_schemes(text) and not named:
        # "Which schemes are there for my category / age / income?": a new search, not the schemes on screen.
        candidates = await retrieve(profile, turns, limit=3)
        mode = "present"
        if not candidates:
            candidates, mode = presented, "followup"
    elif not named and mentions_a_scheme_name(text) and not already_presented:
        # They named a scheme we could not find. Say so honestly; do NOT search by need and show unrelated cards.
        mode, unknown_scheme = "unknown", True
    elif not profile.get("needs"):
        mode = "ask"
        unclear = _looks_unclear(text)
    elif already_presented and new_needs and prev_profile.get("needs"):
        # They added a different need ("also I need a house"): search for that need first,
        # otherwise the earlier need would drown it out.
        rural_hint = profile.get("location_type") or ("rural" if profile.get("occupation") == "farmer" else None)
        focus = {**profile, "needs": new_needs, "occupation": None, "location_type": rural_hint, "utterances": [turns[-1]]}
        candidates = await retrieve(focus, turns[-1:], limit=3)
        mode, refocus = "present", True
    elif already_presented:
        # Same topic: they are asking about the schemes already on screen, not searching again.
        candidates = _focus_first(presented, text)
        last_question = _answers_last_question(assistant_msgs, text)
        mode = "answer" if last_question and not topic_now else "followup"
    else:
        candidates = await retrieve(profile, turns, limit=3)
        mode = "present"

    # ---- the single question the app allows --------------------------------------------
    question_key = ""
    if mode == "present" and not already_presented:
        question_key = F.choose_question(profile, candidates)
    question_intent = F.question_intent(question_key)
    if mode == "ask" and not unclear:
        question_intent = "Ask, in an open and friendly way, what kind of help they are looking for (they have not said yet)."
    reply_profile = {**profile, "needs": new_needs, "relation": None} if refocus else profile

    # ---- official facts for the schemes we will talk about -------------------------------
    topic = topic_now if mode == "followup" else None
    with_facts: list[dict[str, Any]] = candidates
    records: dict[str, dict[str, Any]] = {}
    if candidates and mode in ("present", "followup", "answer", "chat"):
        with_facts, records = await _with_facts(
            candidates, full=mode in ("followup", "answer"), topic=topic, question=text
        )

    # ---- reply --------------------------------------------------------------------------
    reply = ""
    source = "fallback"
    detailed = topic in RICH_TOPICS            # a question about one detail needs room for a complete answer
    if llm.llm_configured():
        context = P.build_context(
            mode=mode,
            language=lang,
            profile=public_profile(profile),
            candidates=with_facts,
            question_to_ask=question_intent,
            turn=turn_no,
            they_just_answered=last_question,
            topic=topic,
        )
        messages = P.build_messages(
            context=context, history=history, user_text=text, language_name=P.LANGUAGE_NAMES.get(lang)
        )
        result = await llm.chat(messages, max_tokens=1200 if detailed else None)
        if result.ok:
            allowed = P.build_facts(with_facts) + "\n" + " ".join(turns)
            verdict = guardrails.sanitize(
                result.text,
                language=lang,
                candidates=with_facts,
                allowed_text=allowed,
                allow_question=bool(question_intent),
                mode=mode,
                max_words=guardrails.DETAIL_MAX_WORDS if detailed else guardrails.MAX_WORDS,
            )
            if verdict.ok:
                reply, source = verdict.text, "llm"
            else:
                logger.warning("LLM reply rejected (%s); using fallback", verdict.reason)
        else:
            logger.warning("LLM unavailable (%s); using fallback", result.error)

    if not reply:
        if lang == "hi-IN" and candidates and mode in ("present", "followup"):
            # The rule-based dialogue reads Hindi records; the model reads English ones.
            records = await SD.get_many([s.get("slug") for s in candidates[:DETAIL_COUNT]], "hi") or records
        ask_count = sum(1 for m in assistant_msgs if not m.get("schemes"))
        reply = F.compose(
            mode=mode,
            intent=intent,
            language=lang,
            profile=reply_profile,
            candidates=candidates,
            question_key=question_key,
            turn=turn_no,
            ask_count=ask_count,
            unclear=unclear,
            topic=topic,
            answered_key=F.question_key_from_text(last_question),
            answer_yes=True if is_yes(text) else False if is_no(text) else None,
            records=records,
            has_presented=already_presented,
        )

    # Cards are shown when we present schemes. Follow-up answers keep the cards already on screen.
    schemes = candidates if (mode == "present" or present_cards) else []

    return {
        "reply_text": reply,
        "schemes": schemes,
        "follow_up": reply if mode == "ask" else None,
        "system_prompt": await get_system_prompt(),
        "language": lang,
        "ready": bool(schemes),
        "mode": mode,
        "source": source,
        "profile": public_profile(profile),
    }
