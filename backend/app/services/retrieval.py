"""Pick the schemes worth talking about.

1. The curated catalogue (schemes_data.py) is scored against the structured profile. These
   have real descriptions and eligibility keywords, so they are high precision.
2. The live myScheme catalogue (3,000+ schemes, names only) adds breadth for needs the
   curated list does not cover (disability, women/child, ...). Results must match at least
   two distinct query words, so a single generic word like "assistance" cannot pull in noise.
"""

from __future__ import annotations

import logging
import re
from typing import Any

from app.services import matcher
from app.services.lexicon import NEED_QUERY
from app.services.myscheme import search_schemes

logger = logging.getLogger(__name__)

MAX_SCORE = 12.0  # a strong curated match (category + keywords + occupation) lands around here

_STOP = {
    "i", "me", "my", "we", "our", "you", "your", "is", "am", "are", "was", "be", "the", "a", "an", "and", "or",
    "to", "of", "for", "in", "on", "at", "with", "from", "that", "this", "it", "do", "does", "have", "has",
    "need", "want", "get", "can", "will", "please", "help", "scheme", "schemes", "yojana", "money", "support",
    "assistance", "any", "some", "about", "tell", "know", "what", "which", "who", "how", "there", "no", "not",
    "mother", "father", "family", "old", "years", "year", "also", "like", "looking", "something",
}

MIN_CONFIDENCE = 0.3     # below this a result is filler, not a recommendation
RELATIVE_FLOOR = 0.35    # ...and must be at least this fraction of the best score
ENTRY_AGE_40 = {"atal-pension", "pm-kisan-maandhan"}
CATALOGUE_ONLY_NEEDS = {"disability", "women"}  # no curated schemes for these

_PUBLIC_FIELDS = ("id", "name", "name_hi", "category", "description", "description_hi", "official_url")


def _public(scheme: dict[str, Any], *, score: float, source: str) -> dict[str, Any]:
    item = {k: scheme.get(k) for k in _PUBLIC_FIELDS}
    item["category"] = item.get("category") or ""
    item["description"] = item.get("description") or ""
    item["description_hi"] = item.get("description_hi") or item["description"]
    item["name_hi"] = item.get("name_hi") or item.get("name")
    item["score"] = round(max(0.0, min(1.0, score / MAX_SCORE)), 2)
    item["source"] = source
    return item


def _english_tokens(turns: list[str]) -> list[str]:
    text = " ".join(turns).lower()
    words = re.findall(r"[a-z][a-z\-]{2,}", text)
    seen: list[str] = []
    for w in words:
        if w not in _STOP and w not in seen:
            seen.append(w)
    return seen[:8]


async def retrieve(
    signals: dict[str, Any],
    user_turns: list[str],
    *,
    limit: int = 3,
) -> list[dict[str, Any]]:
    """Return up to `limit` public scheme dicts, best first. Never raises."""
    results: list[dict[str, Any]] = []
    seen: set[str] = set()

    try:
        curated = matcher.score_schemes(signals, limit=limit)
    except Exception:  # pragma: no cover - defensive
        logger.exception("curated scoring failed")
        curated = []
    age = signals.get("age")
    top = float(curated[0].get("score") or 0) if curated else 0.0
    for i, s in enumerate(curated):
        sid = s["id"]
        raw = float(s.get("score") or 0)
        # Entry-age rules: Atal Pension Yojana and PM Kisan Maandhan only accept people aged 18-40.
        if isinstance(age, int) and age > 40 and sid in ENTRY_AGE_40:
            continue
        # Always keep the best match; keep others only if they are a real match, not filler.
        if i > 0 and (raw / MAX_SCORE < MIN_CONFIDENCE or raw < top * RELATIVE_FLOOR):
            continue
        results.append(_public(s, score=raw, source="curated"))
        seen.add(sid)

    # Catalogue extras: only for needs the curated list does not cover, or when it found nothing.
    needs = signals.get("needs") or []
    if (not results and needs) or any(n in CATALOGUE_ONLY_NEEDS for n in needs):
        words = [w for n in needs for w in NEED_QUERY.get(n, "").split()] + _english_tokens(user_turns)
        query = " ".join(dict.fromkeys(words))  # de-duplicated, order kept
        if query:
            try:
                hits = await search_schemes(query, limit=8)
            except Exception as exc:
                logger.warning("catalogue search failed: %s", exc)
                hits = []
            added = 0
            for h in hits:
                hid = h.get("id")
                # score = 2-3 points per matched query word: require two distinct words.
                if not hid or hid in seen or float(h.get("score") or 0) < 4:
                    continue
                results.append(_public(h, score=float(h.get("score") or 0), source="myscheme.gov.in"))
                seen.add(hid)
                added += 1
                if added >= 2 or len(results) >= limit:
                    break

    return results[:limit]
