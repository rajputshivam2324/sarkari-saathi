"""Prompt template cache (Upstash) for system + reply scaffolds."""

from __future__ import annotations

from typing import Any

from app.services.redis_cache import get_cache

SYSTEM_PROMPT_KEY = "ss:prompt:system:{version}"
REPLY_PROMPT_KEY = "ss:prompt:reply:{sig}"
PROMPT_TTL = 60 * 60 * 24 * 7


async def get_system_prompt() -> str:
    """The live system prompt. Cached under a content hash, so changing the prompt takes effect
    immediately (the old fixed key served a stale prompt for up to 7 days)."""
    from app.services.dialogue_prompt import PROMPT_VERSION, SYSTEM_PROMPT

    cache = get_cache()
    key = SYSTEM_PROMPT_KEY.format(version=PROMPT_VERSION)
    cached = await cache.get(key)
    if cached:
        return cached
    await cache.set(key, SYSTEM_PROMPT, PROMPT_TTL)
    return SYSTEM_PROMPT


async def build_reply(
    *,
    user_text: str,
    schemes: list[dict[str, Any]],
    follow_up: str | None = None,
    forced_text: str | None = None,
    language: str = "hi-IN",
) -> str:
    cache = get_cache()
    text = forced_text or follow_up
    if not text:
        from app.services.languages import match_reply

        text = match_reply(schemes, language)

    sig = "|".join(
        [
            language,
            (follow_up or "")[:40],
            ",".join(s.get("id", "") for s in schemes[:3]),
            user_text.lower()[:60],
        ]
    )
    key = REPLY_PROMPT_KEY.format(sig=abs(hash(sig)) % (10**12))
    cached = await cache.get(key)
    if cached:
        return cached

    await cache.set(key, text, PROMPT_TTL)
    await get_system_prompt()
    return text
