"""Gnani Prisma STT, Timbre TTS, and optional Evon LLM client."""

from __future__ import annotations

import json
import logging
from typing import Any

import httpx

from app.config import Settings, get_settings
from app.schemes_data import scheme_keyterms

logger = logging.getLogger(__name__)

STT_TOPIC = (
    "User is describing eligibility for Indian government welfare schemes "
    "such as farmer support, housing, health insurance, pensions, scholarships, "
    "employment, LPG, and small business loans. Speech may be Hindi, English, or Hinglish."
)


class GnaniError(RuntimeError):
    pass


def _api_headers(settings: Settings) -> dict[str, str]:
    return {"X-API-Key-ID": settings.gnani_api_key}


async def transcribe_audio(
    audio_bytes: bytes,
    filename: str = "audio.wav",
    content_type: str = "audio/wav",
    *,
    previous_text: str | None = None,
    settings: Settings | None = None,
) -> dict[str, Any]:
    """Call Prisma v3.0 STT. Returns transcript + metadata; raises on failure."""
    settings = settings or get_settings()
    if not settings.gnani_api_key:
        raise GnaniError("GNANI_API_KEY is not configured")

    data: dict[str, str] = {
        "model": settings.gnani_stt_model,
        # indic-auto: Hindi, English + all regional languages on the key
        "language_code": settings.gnani_stt_language or "indic-auto",
        "format": "transcribe",
        "topic": STT_TOPIC[:1600],
        "keyterms": json.dumps(scheme_keyterms(), ensure_ascii=False),
    }
    if previous_text:
        data["previous_text"] = previous_text[-600:]

    files = {
        "audio_file": (filename or "audio.wav", audio_bytes, content_type or "audio/wav"),
    }

    async with httpx.AsyncClient(timeout=90.0) as client:
        response = await client.post(
            settings.gnani_stt_url,
            headers=_api_headers(settings),
            data=data,
            files=files,
        )

    try:
        body = response.json()
    except Exception as exc:
        raise GnaniError(
            f"STT returned non-JSON (HTTP {response.status_code}): {response.text[:300]}"
        ) from exc

    if response.status_code >= 400 or not body.get("success"):
        err = body.get("error") or {}
        message = err.get("message") or body.get("message") or response.text[:300]
        raise GnaniError(f"STT failed (HTTP {response.status_code}): {message}")

    transcript = (body.get("transcript") or "").strip()
    if not transcript:
        raise GnaniError("STT returned an empty transcript")

    return {
        "transcript": transcript,
        "model": body.get("model") or settings.gnani_stt_model,
        "detected_language_code": body.get("detected_language_code"),
        "request_id": body.get("request_id"),
    }


async def synthesize_speech(
    text: str,
    *,
    language: str | None = None,
    settings: Settings | None = None,
) -> bytes:
    """Call Timbre v3.0 TTS; returns WAV bytes. Language: any Gnani Indic code."""
    settings = settings or get_settings()
    if not settings.gnani_api_key:
        raise GnaniError("GNANI_API_KEY is not configured")

    text = (text or "").strip()
    if not text:
        raise GnaniError("TTS text is empty")

    from app.services.languages import normalize_lang

    lang = normalize_lang(language or settings.gnani_tts_language)

    payload = {
        "text": text,
        "voice": settings.gnani_tts_voice,
        "model": settings.gnani_tts_model,
        "language": lang,
        "speed": 1.0,
        "audio_config": {
            "sample_rate": 24000,
            "num_channels": 1,
            "sample_width": 2,
            "encoding": "linear_pcm",
            "container": "wav",
        },
    }

    async with httpx.AsyncClient(timeout=90.0) as client:
        response = await client.post(
            settings.gnani_tts_url,
            headers={**_api_headers(settings), "Content-Type": "application/json"},
            json=payload,
        )

    content_type = response.headers.get("content-type", "")
    if response.status_code >= 400:
        try:
            err_body = response.json()
            message = (
                (err_body.get("error") or {}).get("message")
                or err_body.get("message")
                or response.text[:300]
            )
        except Exception:
            message = response.text[:300]
        raise GnaniError(f"TTS failed (HTTP {response.status_code}): {message}")

    if "audio" not in content_type and not response.content.startswith(b"RIFF"):
        # Some gateways still return wav without audio/* content-type
        if not response.content:
            raise GnaniError("TTS returned empty audio")

    return response.content


async def run_evon(
    messages: list[dict[str, str]],
    *,
    settings: Settings | None = None,
) -> dict[str, Any]:
    """
    Optional Evon LLM call (OpenAI-compatible chat completions).

    Only runs when GNANI_EVON_ENABLED is true AND GNANI_EVON_URL is set.
    Never reports success when Evon did not actually run or failed.
    """
    settings = settings or get_settings()

    if not settings.gnani_evon_enabled:
        return {"ran": False, "skipped": True, "reason": "GNANI_EVON_ENABLED is false"}

    url = (settings.gnani_evon_url or "").strip()
    if not url:
        return {
            "ran": False,
            "skipped": True,
            "reason": "GNANI_EVON_URL is empty while Evon is enabled",
        }

    endpoint = url.rstrip("/")
    if not endpoint.endswith("/chat/completions"):
        endpoint = f"{endpoint}/v1/chat/completions"

    headers: dict[str, str] = {"Content-Type": "application/json"}
    if settings.gnani_api_key:
        headers["X-API-Key-ID"] = settings.gnani_api_key
        headers["Authorization"] = f"Bearer {settings.gnani_api_key}"

    payload = {
        "model": "model",
        "messages": messages,
        "temperature": 0.4,
        "max_tokens": 1024,
    }

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(endpoint, headers=headers, json=payload)
    except httpx.HTTPError as exc:
        logger.warning("Evon request failed: %s", exc)
        return {"ran": False, "error": str(exc)}

    if response.status_code >= 400:
        return {
            "ran": False,
            "error": f"HTTP {response.status_code}: {response.text[:400]}",
        }

    try:
        body = response.json()
    except Exception:
        return {"ran": False, "error": "Evon returned non-JSON response"}

    choices = body.get("choices") or []
    if not choices:
        return {"ran": False, "error": "Evon response had no choices"}

    content = (
        ((choices[0].get("message") or {}).get("content"))
        or choices[0].get("text")
        or ""
    )
    content = str(content).strip()
    if not content:
        return {"ran": False, "error": "Evon returned empty content"}

    return {"ran": True, "content": content, "raw": body}
