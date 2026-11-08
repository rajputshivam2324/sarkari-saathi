from __future__ import annotations

import base64
import json
import logging
from typing import Annotated, Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, Field

from app.auth import get_current_user
from app.config import get_settings
from app.models import User
from app.services import gnani
from app.services.matcher import apply_evon_refinement, process_turn

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/voice", tags=["voice"])
settings = get_settings()


class SpeakRequest(BaseModel):
    text: str = Field(min_length=1, max_length=4000)


def _parse_context(raw: str | None) -> dict[str, Any]:
    if not raw or not raw.strip():
        return {}
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail="context must be valid JSON") from exc
    if not isinstance(data, dict):
        raise HTTPException(status_code=400, detail="context must be a JSON object")
    return data


def _public_schemes(schemes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for s in schemes:
        out.append(
            {
                "id": s.get("id"),
                "name": s.get("name"),
                "name_hi": s.get("name_hi"),
                "category": s.get("category"),
                "description": s.get("description"),
                "description_hi": s.get("description_hi"),
                "official_url": s.get("official_url"),
                "score": s.get("score"),
            }
        )
    return out


@router.post("/turn")
async def voice_turn(
    user: Annotated[User, Depends(get_current_user)],
    audio: UploadFile | None = File(default=None),
    text: str | None = Form(default=None),
    context: str | None = Form(default=None),
) -> dict[str, Any]:
    """
    One conversational turn: STT (optional) → match/follow-up → Timbre TTS.

    Send multipart form with either `audio` or `text` (or both; audio wins for transcript).
    Optional `context` JSON from the previous turn response keeps multi-turn state.
    """
    _ = user  # auth gate
    ctx = _parse_context(context)
    transcript = (text or "").strip()
    stt_model = None
    detected_language = None

    if audio is not None and audio.filename:
        audio_bytes = await audio.read()
        if not audio_bytes:
            raise HTTPException(status_code=400, detail="Empty audio upload")
        try:
            stt = await gnani.transcribe_audio(
                audio_bytes,
                filename=audio.filename or "audio.wav",
                content_type=audio.content_type or "audio/wav",
                previous_text=" ".join(
                    (ctx.get("signals") or {}).get("utterances") or []
                )[-600:]
                or None,
            )
        except gnani.GnaniError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc
        transcript = stt["transcript"]
        stt_model = stt.get("model")
        detected_language = stt.get("detected_language_code")

    if not transcript:
        raise HTTPException(
            status_code=400,
            detail="Provide audio or text for this turn",
        )

    match = process_turn(transcript, ctx)

    evon_ran = False
    evon_meta: dict[str, Any] = {"ran": False}
    if settings.gnani_evon_enabled and (settings.gnani_evon_url or "").strip():
        scheme_brief = [
            {
                "id": s.get("id"),
                "name": s.get("name"),
                "name_hi": s.get("name_hi"),
                "official_url": s.get("official_url"),
            }
            for s in match.get("schemes") or []
        ]
        messages = [
            {
                "role": "system",
                "content": (
                    "You are Sarkari Saathi, a voice assistant for Indian government "
                    "welfare schemes. Reply in clear spoken Hindi (Devanagari). "
                    "Do not invent schemes or URLs. If follow_up is set, only ask that "
                    "question. Otherwise briefly explain the matched schemes."
                ),
            },
            {
                "role": "user",
                "content": json.dumps(
                    {
                        "user_text": transcript,
                        "signals": (match.get("context") or {}).get("signals"),
                        "follow_up": match.get("follow_up"),
                        "schemes": scheme_brief,
                        "draft_reply": match.get("reply_text"),
                    },
                    ensure_ascii=False,
                ),
            },
        ]
        evon_meta = await gnani.run_evon(messages)
        evon_ran = bool(evon_meta.get("ran"))
        if evon_ran and evon_meta.get("content"):
            match = apply_evon_refinement(match, evon_meta["content"])

    reply_text = match["reply_text"]
    reply_audio_b64 = None
    tts_ok = False
    try:
        wav = await gnani.synthesize_speech(reply_text)
        reply_audio_b64 = base64.b64encode(wav).decode("ascii")
        tts_ok = True
    except gnani.GnaniError as exc:
        logger.warning("TTS failed for turn: %s", exc)
        # Still return text/schemes; client can call /voice/speak later
        reply_audio_b64 = None

    return {
        "transcript": transcript,
        "detected_language_code": detected_language,
        "follow_up": match.get("follow_up"),
        "reply_text": reply_text,
        "schemes": _public_schemes(match.get("schemes") or []),
        "context": match.get("context"),
        "ready": match.get("ready"),
        "models": {
            "stt": stt_model or (settings.gnani_stt_model if audio else None),
            "tts": settings.gnani_tts_model if tts_ok else None,
            "voice": settings.gnani_tts_voice if tts_ok else None,
        },
        "evon_ran": evon_ran,
        "evon": {
            "ran": evon_ran,
            "skipped": evon_meta.get("skipped"),
            "reason": evon_meta.get("reason"),
            "error": evon_meta.get("error"),
        },
        "reply_audio_b64": reply_audio_b64,
    }


@router.post("/speak")
async def voice_speak(
    body: SpeakRequest,
    user: Annotated[User, Depends(get_current_user)],
) -> Response:
    """Synthesize Hindi speech with Timbre; returns audio/wav."""
    _ = user
    try:
        wav = await gnani.synthesize_speech(body.text)
    except gnani.GnaniError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return Response(content=wav, media_type="audio/wav")
