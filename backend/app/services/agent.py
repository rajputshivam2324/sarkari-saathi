"""Live conversation turn.

    what they said ─► understand (profile from all turns, intent, language they are using)
                   ─► decide the mode: chat | ask | present | answer | followup
                   ─► pick schemes (new search, or the ones already on screen for a follow-up)
                   ─► load each scheme's official record (benefits, eligibility, how to apply)
                   ─► Groq writes the reply from those facts   (strong prompt + trusted CONTEXT)
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
    is_yes,
    public_profile,
)
from app.services.prompt_cache import get_system_prompt
from app.services.retrieval import retrieve

logger = logging.getLogger(__name__)

DETAIL_COUNT = 2   # how many schemes get their full official record in a turn (keeps prompts small and fast)


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
    schemes: list[dict[str, Any]], lang: str, *, full: bool
) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]]]:
    """Copies of the schemes carrying `facts` text from each one's official record.

    The first DETAIL_COUNT get a record; with full=True that is the long form (every application
    mode, exclusions). Schemes with no record keep their short curated description.
    """
    detail_lang = "hi" if lang == "hi-IN" else "en"
    top = schemes[:DETAIL_COUNT]
    records = await SD.get_many([s.get("slug") for s in top], detail_lang)
    out: list[dict[str, Any]] = []
    for i, s in enumerate(schemes[:3]):
        item = dict(s)
        rec = records.get(s.get("slug") or "") if i < DETAIL_COUNT else None
        if rec:
            item["facts"] = SD.facts_text(rec, full=full and i == 0)   # long form only for the scheme being discussed
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
    prev_profile = build_profile(turns[:-1]) if len(turns) > 1 else {"needs": []}
    intent = classify_intent(text)

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

    if intent in ("thanks", "bye", "ack") or (intent == "greeting" and not profile.get("needs")):
        mode = "chat"
        if intent == "ack" and already_presented:
            candidates = presented          # lets the model offer a concrete next step about what was shown
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
        mode = "answer" if last_question and not followup_topic(text) else "followup"
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
    topic = followup_topic(text) if mode == "followup" else None
    with_facts: list[dict[str, Any]] = candidates
    records: dict[str, dict[str, Any]] = {}
    if candidates and mode in ("present", "followup", "answer", "chat"):
        with_facts, records = await _with_facts(candidates, lang, full=mode in ("followup", "answer"))

    # ---- reply --------------------------------------------------------------------------
    reply = ""
    source = "fallback"
    if llm.llm_configured():
        context = P.build_context(
            mode=mode,
            language=lang,
            profile=public_profile(profile),
            candidates=with_facts,
            question_to_ask=question_intent,
            turn=turn_no,
            they_just_answered=last_question,
        )
        messages = P.build_messages(context=context, history=history, user_text=text)
        result = await llm.chat(messages)
        if result.ok:
            allowed = P.build_facts(with_facts) + "\n" + " ".join(turns)
            verdict = guardrails.sanitize(
                result.text,
                language=lang,
                candidates=with_facts,
                allowed_text=allowed,
                allow_question=bool(question_intent),
                mode=mode,
            )
            if verdict.ok:
                reply, source = verdict.text, "llm"
            else:
                logger.warning("LLM reply rejected (%s); using fallback", verdict.reason)
        else:
            logger.warning("LLM unavailable (%s); using fallback", result.error)

    if not reply:
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
    schemes = candidates if mode == "present" else []

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
