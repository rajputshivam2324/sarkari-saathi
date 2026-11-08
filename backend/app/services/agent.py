"""Live conversation turn.

    what they said ─► understand (profile from all turns, intent)
                   ─► decide the mode: chat | ask | present | followup
                   ─► retrieve verified schemes
                   ─► Groq writes the reply  (strong prompt + trusted CONTEXT)
                   ─► guardrails check it           (else rule-based dialogue speaks instead)

The model chooses the words. The app controls the substance: which schemes exist, whether a
question may be asked, and whether the reply is safe to say out loud.
"""

from __future__ import annotations

import logging
from typing import Any

from app.services import dialogue_prompt as P
from app.services import fallback as F
from app.services import guardrails, llm
from app.services.languages import normalize_lang
from app.services.lexicon import build_profile, classify_intent, followup_topic, is_no, is_yes, public_profile
from app.services.prompt_cache import get_system_prompt
from app.services.retrieval import retrieve

logger = logging.getLogger(__name__)


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


async def handle_utterance(
    text: str,
    *,
    history: list[dict[str, Any]] | None = None,
    language: str | None = None,
) -> dict[str, Any]:
    history = history or []
    lang = normalize_lang(language)
    text = (text or "").strip()

    turns = _user_turns(history, text)
    profile = build_profile(turns)
    prev_profile = build_profile(turns[:-1]) if len(turns) > 1 else {"needs": []}
    intent = classify_intent(text)

    assistant_msgs = [m for m in history if m.get("role") == "assistant"]
    already_presented = any(m.get("schemes") for m in assistant_msgs)
    needs_changed = set(profile.get("needs") or []) != set(prev_profile.get("needs") or [])
    turn_no = len(turns)

    # ---- decide the mode ----------------------------------------------------------------
    candidates: list[dict[str, Any]] = []
    unclear = False
    last_question = ""
    new_needs = sorted(set(profile.get("needs") or []) - set(prev_profile.get("needs") or []))

    if intent in ("thanks", "bye") or (intent == "greeting" and not profile.get("needs")):
        mode = "chat"
    elif not profile.get("needs"):
        mode = "ask"
        unclear = _looks_unclear(text)
    else:
        if already_presented and new_needs and prev_profile.get("needs"):
            # They added a different need ("also I need a house"): search for that need first,
            # otherwise the earlier need would drown it out.
            # Score only the new utterance and drop the earlier occupation boost, but keep who
            # they are: a farmer asking for a house is almost certainly rural.
            rural_hint = profile.get("location_type") or ("rural" if profile.get("occupation") == "farmer" else None)
            focus = {
                **profile,
                "needs": new_needs,
                "occupation": None,
                "location_type": rural_hint,
                "utterances": [turns[-1]],
            }
            candidates = await retrieve(focus, turns[-1:], limit=3)
            mode = "present"
        else:
            candidates = await retrieve(profile, turns, limit=3)
            last_question = _answers_last_question(assistant_msgs, text) if already_presented and not new_needs else ""
            if last_question:
                mode = "answer"
            elif already_presented and not new_needs:
                mode = "followup"
            else:
                mode = "present"

    # ---- the single question the app allows --------------------------------------------
    question_key = ""
    if mode == "present" and not already_presented:
        question_key = F.choose_question(profile, candidates)
    question_intent = F.question_intent(question_key)
    # Retrieval for a "focus" turn changes which need leads the reply.
    reply_profile = {**profile, "needs": new_needs, "relation": None} if (mode == "present" and already_presented and new_needs and prev_profile.get("needs")) else profile
    if mode == "ask" and not unclear:
        question_intent = "Ask, in an open and friendly way, what kind of help they are looking for (they have not said yet)."

    # ---- reply --------------------------------------------------------------------------
    reply = ""
    source = "fallback"
    if llm.llm_configured():
        context = P.build_context(
            mode=mode,
            language=lang,
            profile=public_profile(profile),
            candidates=candidates,
            question_to_ask=question_intent,
            turn=turn_no,
            they_just_answered=last_question,
        )
        messages = P.build_messages(context=context, history=history, user_text=text)
        result = await llm.chat(messages)
        if result.ok:
            allowed = P.build_facts(candidates) + "\n" + " ".join(turns)
            verdict = guardrails.sanitize(
                result.text,
                language=lang,
                candidates=candidates,
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
            topic=followup_topic(text) if mode == "followup" else None,
            answered_key=F.question_key_from_text(last_question),
            answer_yes=True if is_yes(text) else False if is_no(text) else None,
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
