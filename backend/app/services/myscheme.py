"""Live myScheme.gov.in catalogue + Redis search cache + eager warm."""

from __future__ import annotations

import logging
import re
from typing import Any

import httpx

from app.config import get_settings
from app.services.redis_cache import get_cache

logger = logging.getLogger(__name__)

CATALOG_KEY = "ss:schemes:catalog:v4"
SEARCH_KEY = "ss:schemes:search:{q}"
CATALOG_TTL = 60 * 60 * 12  # 12h
SEARCH_TTL = 60 * 30  # 30m

EAGER_QUERIES = [
    "farmer",
    "kisan",
    "health",
    "ayushman",
    "housing",
    "pmay",
    "education",
    "scholarship",
    "pension",
    "ujjwala",
    "employment",
    "mgnrega",
    "women",
    "student",
    "disability",
    "ration",
    "labour",
    "startup",
]


def _headers() -> dict[str, str]:
    settings = get_settings()
    return {
        "x-api-key": settings.myscheme_api_key,
        "Origin": "https://www.myscheme.gov.in",
        "Referer": "https://www.myscheme.gov.in/",
        "Accept": "application/json",
    }


def normalize_scheme(raw: dict[str, Any]) -> dict[str, Any]:
    en = raw.get("en") or {}
    basic = en.get("basicDetails") or {}
    name = (basic.get("schemeName") or "").strip()
    short = (basic.get("schemeShortTitle") or "").strip()
    slug = (raw.get("slug") or "").strip()
    return {
        "id": slug or raw.get("_id") or name.lower().replace(" ", "-"),
        "name": name or short or slug,
        "name_hi": name,
        "short_title": short,
        "slug": slug,
        "official_url": f"https://www.myscheme.gov.in/schemes/{slug}" if slug else "https://www.myscheme.gov.in/",
        "source": "myscheme.gov.in",
        "category": "",
        "description": short or name,
        "description_hi": short or name,
    }


async def fetch_catalog_live() -> list[dict[str, Any]]:
    settings = get_settings()
    url = f"{settings.myscheme_api_base.rstrip('/')}/schemes/v4/public/schemes"
    async with httpx.AsyncClient(timeout=60.0) as client:
        res = await client.get(
            url,
            headers=_headers(),
            params={"lang": "en", "from": 0, "limit": 20},
        )
    if res.status_code >= 400:
        raise RuntimeError(f"myScheme HTTP {res.status_code}: {res.text[:200]}")
    body = res.json()
    if body.get("status") not in ("Success", "success") and body.get("statusCode") != 200:
        raise RuntimeError(f"myScheme failed: {body}")
    raw_list = body.get("data") or []
    if not isinstance(raw_list, list):
        raise RuntimeError("myScheme data is not a list")
    return [normalize_scheme(x) for x in raw_list if isinstance(x, dict)]


async def get_catalog(*, force: bool = False) -> list[dict[str, Any]]:
    cache = get_cache()
    if not force:
        cached = await cache.get_json(CATALOG_KEY)
        if isinstance(cached, list) and cached:
            return cached
    schemes = await fetch_catalog_live()
    await cache.set_json(CATALOG_KEY, schemes, CATALOG_TTL)
    logger.info("Cached %s live myScheme schemes", len(schemes))
    return schemes


def _tokens(q: str) -> list[str]:
    return [t for t in re.split(r"[^\w\u0900-\u097F]+", q.lower()) if len(t) >= 2]


def score_scheme(scheme: dict[str, Any], tokens: list[str]) -> int:
    hay = f"{scheme.get('name','')} {scheme.get('short_title','')} {scheme.get('slug','')}".lower()
    score = 0
    for t in tokens:
        if t in hay:
            score += 3 if t in (scheme.get("slug") or "").lower() else 2
            if hay.startswith(t):
                score += 1
    return score


async def search_schemes(query: str, *, limit: int = 5) -> list[dict[str, Any]]:
    q = (query or "").strip()
    if not q:
        return []
    cache = get_cache()
    key = SEARCH_KEY.format(q=q.lower()[:120])
    cached = await cache.get_json(key)
    if isinstance(cached, list) and cached:
        return cached[:limit]

    catalog = await get_catalog()
    tokens = _tokens(q)
    ranked: list[tuple[int, dict[str, Any]]] = []
    for s in catalog:
        sc = score_scheme(s, tokens)
        if sc > 0:
            ranked.append((sc, s))
    ranked.sort(key=lambda x: x[0], reverse=True)
    results = [{**s, "score": sc} for sc, s in ranked[: max(limit, 8)]]
    await cache.set_json(key, results, SEARCH_TTL)
    return results[:limit]


async def eager_warm() -> dict[str, Any]:
    """Pull live catalogue once, then pre-cache frequent searches."""
    catalog = await get_catalog(force=True)
    warmed = 0
    for q in EAGER_QUERIES:
        hits = await search_schemes(q, limit=8)
        if hits:
            warmed += 1
    return {"catalog": len(catalog), "warmed_queries": warmed, "queries": EAGER_QUERIES}
