"""Full scheme details from myScheme.gov.in (the official public record).

For one scheme this gives what a person actually needs before going to the official site:
who it is for, the benefits, eligibility, who is excluded, step-by-step how to apply (online,
offline, via a Common Service Centre), and the official links.

Two shapes come out of the same record:
- get_details():  cleaned markdown sections, rendered on screen by the app.
- facts_text():   compact plain text, the only source the language model may state facts from.
"""

from __future__ import annotations

import asyncio
import html
import logging
import re
from typing import Any

import httpx

from app.config import get_settings
from app.services.redis_cache import get_cache

logger = logging.getLogger(__name__)

DETAIL_TTL = 60 * 60 * 24      # schemes change rarely; a day is plenty
DETAIL_KEY = "ss:scheme:detail:v4:{slug}:{lang}"
SUPPORTED_LANGS = {"en", "hi"}  # myScheme serves more, but these are the ones we verified end to end
PAGE_URL = "https://www.myscheme.gov.in/schemes/{slug}"

_client: tuple[Any, httpx.AsyncClient] | None = None
_inflight: dict[str, "asyncio.Task[dict[str, Any] | None]"] = {}


def _http() -> httpx.AsyncClient:
    global _client
    loop = asyncio.get_running_loop()
    if _client is None or _client[0] is not loop:
        _client = (loop, httpx.AsyncClient(timeout=httpx.Timeout(10.0, connect=4.0)))
    return _client[1]


# --------------------------------------------------------------------------------------
# text cleaning
# --------------------------------------------------------------------------------------
_TAG = re.compile(r"<[^>]+>")
_BR = re.compile(r"<br\s*/?>", re.IGNORECASE)
_LINK = re.compile(r"\[([^\]]+)\]\(([^)\s]+)[^)]*\)")


# Defects measured across 50 real myScheme records (English and Hindi), fixed here once so the
# screen and the AI both read clean text.
_HIDDEN_ENTITY = re.compile(r"&\s*#\s*(\d+)\s*;")                 # "& #39;"  (Hindi translation broke the entity)
_LINK_SPACE = re.compile(r"\]\s+\(\s*(https?://[^\s)]+)(?:\s+#)?\s*\)")   # "[label] (url #)" -> "[label](url)"
_STAR_RUN = re.compile(r"\*{3,}")                                  # "******"
_STEP_MARK = r"(?:Step|STEP|चरण)\s*\d+\s*[:ः：]?"
_STEP_GLUE = re.compile(r"[ \t]+(?=(?:\*\*|\*\s?)?" + _STEP_MARK + r")")  # steps joined on one line
_STRAY_STAR = re.compile(r"(?<![*\w])\*(?=\s)|(?<=\s)\*(?![*\w])")     # a lone "*" used as decoration
_BULLET_GLUE = re.compile(r"(?<=[.।!?:;)])\s*-\s+(?=\*\*|[A-Zऀ-ॿ])")   # "...done.- **Next:** ..." -> new bullet
_BARE_URL_LINE = re.compile(r"^(https?://\S+)$", re.MULTILINE)


def clean_md(md: str | None) -> str:
    """Turn myScheme's messy markdown into clean markdown (entities, spacing, glued steps and bullets)."""
    t = md or ""
    for _ in range(3):                      # "&amp;#39;" needs two passes; stop when stable
        u = html.unescape(t)
        if u == t:
            break
        t = u
    t = _HIDDEN_ENTITY.sub(lambda m: html.unescape(f"&#{m.group(1)};"), t)
    t = _BR.sub("\n", t)
    t = _TAG.sub("", t)
    t = html.unescape(t)
    t = _LINK_SPACE.sub(r"](\1)", t)
    t = re.sub(r"(?<=[.।!?])[ \t]+>[ \t]*", "\n> ", t)                  # a ">" note glued to the end of a sentence
    t = _STAR_RUN.sub("**", t)
    t = _BULLET_GLUE.sub("\n- ", t)
    t = _STEP_GLUE.sub("\n", t)
    t = re.sub(r"^(\s*)[-*]\s+\*\s+", r"\1- ", t, flags=re.MULTILINE)   # "- * text" -> "- text"
    t = _STRAY_STAR.sub("", t)
    t = re.sub(r"\*\*\s*\*\*", "", t)                                  # empty bold
    # a "**" that opens and never closes on its line would swallow the rest of the line
    t = "\n".join(l.replace("**", "") if l.count("**") % 2 else l for l in t.splitlines())
    t = _BARE_URL_LINE.sub(r"[\1](\1)", t)                               # make bare URLs clickable
    # whole-line italics written as "_*note_" / "_note_": keep the words, drop the markup
    t = re.sub(r"^[ \t]*_\**[ \t]*(.+?)[ \t]*_[ \t]*$", r"\1", t, flags=re.MULTILINE)
    t = re.sub(r"[ \t]{2,}", " ", t)
    t = re.sub(r"\n{3,}", "\n\n", t)
    t = re.sub(r"[ \t]+\n", "\n", t)
    return t.strip()


def md_to_text(md: str | None) -> str:
    """Plain text for the model: no markdown syntax, links reduced to their label."""
    t = _LINK.sub(r"\1", clean_md(md))
    t = t.replace("**", "").replace("__", "").replace("`", "")
    t = re.sub(r"^>\s?", "", t, flags=re.MULTILINE)
    t = re.sub(r"^\s*\d+\.\s+", "- ", t, flags=re.MULTILINE) if t.count("\n1. ") > 3 else t
    # Markdown "1. 1. 1." auto-numbering that arrived joined on one line ("... चाहिए। 1. आवेदक ...")
    t = re.sub(r"(?<=[.।;:])\s+\d{1,2}[.)]\s+(?=\S)", "\n- ", t)
    return re.sub(r"\n{3,}", "\n\n", t).strip()


def _labels(items: Any) -> list[str]:
    out: list[str] = []
    for it in items or []:
        label = it.get("label") if isinstance(it, dict) else it
        if isinstance(label, str) and label.strip():
            out.append(html.unescape(label.strip()))
    return out


def _definition_text(nodes: Any) -> str:
    parts: list[str] = []

    def walk(n: Any) -> None:
        if isinstance(n, dict):
            if isinstance(n.get("text"), str):
                parts.append(n["text"])
            for c in n.get("children") or []:
                walk(c)
        elif isinstance(n, list):
            for c in n:
                walk(c)

    walk(nodes)
    return re.sub(r"\s+", " ", " ".join(parts)).strip()


# --------------------------------------------------------------------------------------
# fetch + normalise
# --------------------------------------------------------------------------------------
def normalize(data: dict[str, Any], slug: str, lang: str) -> dict[str, Any] | None:
    rec = data.get(lang) or data.get("en") or {}
    if not rec:
        return None
    used = lang if data.get(lang) else "en"
    basic = rec.get("basicDetails") or {}
    content = rec.get("schemeContent") or {}
    # For some languages myScheme returns eligibility at the top level instead of inside the language block.
    elig_block = rec.get("eligibilityCriteria") or data.get("eligibilityCriteria") or {}

    apply_list: list[dict[str, Any]] = []
    for a in rec.get("applicationProcess") or []:
        steps = clean_md(a.get("process_md"))
        if steps or a.get("url"):
            apply_list.append({"mode": a.get("mode") or "", "url": (a.get("url") or "").strip() or None, "steps_md": steps})

    refs = [
        {"title": html.unescape((r.get("title") or "").strip()), "url": (r.get("url") or "").strip()}
        for r in content.get("references") or []
        if isinstance(r, dict) and (r.get("url") or "").strip()
    ]
    defs = [
        {"name": d.get("name", ""), "text": _definition_text(d.get("definition"))}
        for d in rec.get("schemeDefinitions") or []
        if isinstance(d, dict) and d.get("name")
    ]

    out = {
        "slug": slug,
        "lang": used,
        "name": html.unescape(basic.get("schemeName") or "").strip(),
        "short_title": html.unescape(basic.get("schemeShortTitle") or "").strip(),
        "level": ((basic.get("level") or {}).get("label") if isinstance(basic.get("level"), dict) else None),
        "ministry": ((basic.get("nodalMinistryName") or {}).get("label") if isinstance(basic.get("nodalMinistryName"), dict) else None),
        "department": ((basic.get("nodalDepartmentName") or {}).get("label") if isinstance(basic.get("nodalDepartmentName"), dict) else None),
        "categories": _labels(basic.get("schemeCategory")),
        "beneficiaries": _labels(basic.get("targetBeneficiaries")),
        "tags": [t for t in (basic.get("tags") or []) if isinstance(t, str)][:8],
        "brief": clean_md(content.get("briefDescription")),
        "description_md": clean_md(content.get("detailedDescription_md")),
        "benefits_md": clean_md(content.get("benefits_md")),
        "eligibility_md": clean_md(elig_block.get("eligibilityDescription_md")),
        "exclusions_md": clean_md(content.get("exclusions_md")),
        "apply": apply_list,
        "references": refs[:8],
        "definitions": defs[:4],
        "page_url": PAGE_URL.format(slug=slug),
    }
    # A record with no substance is not worth showing.
    if not (out["benefits_md"] or out["eligibility_md"] or out["apply"] or out["brief"]):
        return None
    return out


async def _fetch(slug: str, lang: str) -> dict[str, Any] | None:
    s = get_settings()
    if not s.myscheme_api_key:
        return None
    url = f"{s.myscheme_api_base.rstrip('/')}/schemes/v6/public/schemes"
    headers = {
        "x-api-key": s.myscheme_api_key,
        "Origin": "https://www.myscheme.gov.in",
        "Referer": "https://www.myscheme.gov.in/",
        "Accept": "application/json",
    }
    for attempt in (1, 2):
        try:
            r = await _http().get(url, params={"slug": slug, "lang": lang}, headers=headers)
            if r.status_code == 200:
                body = (r.json() or {}).get("data")
                return normalize(body, slug, lang) if isinstance(body, dict) else None
            if r.status_code in (429, 500, 502, 503, 504) and attempt == 1:
                await asyncio.sleep(0.5)
                continue
            logger.warning("myScheme details HTTP %s for %s", r.status_code, slug)
            return None
        except (httpx.HTTPError, ValueError) as exc:
            if attempt == 2:
                logger.warning("myScheme details failed for %s: %s", slug, exc)
                return None
            await asyncio.sleep(0.3)
    return None


async def get_details(slug: str | None, lang: str = "en") -> dict[str, Any] | None:
    """Cleaned details for a scheme, cached. None if unknown or the service is unavailable."""
    slug = (slug or "").strip()
    if not slug or not re.fullmatch(r"[A-Za-z0-9._-]{1,80}", slug):   # never forward arbitrary input upstream
        return None
    lang = lang if lang in SUPPORTED_LANGS else "en"
    cache = get_cache()
    key = DETAIL_KEY.format(slug=slug, lang=lang)
    cached = await cache.get_json(key)
    if isinstance(cached, dict) and cached.get("slug") == slug:
        return cached

    # One upstream request per (slug, lang) even if several callers ask at once.
    task = _inflight.get(key)
    if task is None:
        task = asyncio.create_task(_fetch(slug, lang))
        _inflight[key] = task
        task.add_done_callback(lambda _t, k=key: _inflight.pop(k, None))
    details = await task
    if details is None and lang != "en":
        return await get_details(slug, "en")          # no Hindi record: use English rather than nothing
    if details:
        await cache.set_json(key, details, DETAIL_TTL)
    return details


async def get_many(slugs: list[str | None], lang: str = "en") -> dict[str, dict[str, Any]]:
    uniq = [s for s in dict.fromkeys(slugs) if s]
    results = await asyncio.gather(*[get_details(s, lang) for s in uniq], return_exceptions=True)
    return {s: r for s, r in zip(uniq, results) if isinstance(r, dict)}


# --------------------------------------------------------------------------------------
# compact facts for the model
# --------------------------------------------------------------------------------------
def _clip(text: str, limit: int) -> str:
    text = text.strip()
    if len(text) <= limit:
        return text
    cut = text[:limit].rsplit("\n", 1)[0] if "\n" in text[:limit] else text[:limit].rsplit(" ", 1)[0]
    return cut.rstrip(" ,;:-") + " …"


def facts_text(d: dict[str, Any], *, full: bool = False) -> str:
    """Everything the model may state about this scheme, as plain text.

    `full=False` is for suggesting schemes (benefit + who it is for + how to apply, briefly).
    `full=True` is for follow-up questions (adds exclusions, every application mode and its steps).
    """
    lim = {"benefits": 600, "elig": 750, "excl": 450, "steps": 750} if full else {"benefits": 360, "elig": 420, "excl": 0, "steps": 0}
    lines: list[str] = [f"Official name: {d.get('name')}"]
    meta = [d.get("level"), d.get("ministry")]
    if any(meta):
        lines.append("Run by: " + ", ".join(m for m in meta if m))
    if d.get("beneficiaries"):
        lines.append("Meant for: " + ", ".join(d["beneficiaries"]) + (f" ({d['categories'][0]})" if d.get("categories") else ""))
    if d.get("brief"):
        lines.append("About: " + _clip(md_to_text(d["brief"]), 260))
    if d.get("benefits_md"):
        lines.append("Benefits:\n" + _clip(md_to_text(d["benefits_md"]), lim["benefits"]))
    if d.get("eligibility_md"):
        lines.append("Who is eligible:\n" + _clip(md_to_text(d["eligibility_md"]), lim["elig"]))
    if full and d.get("exclusions_md"):
        lines.append("Not eligible / excluded:\n" + _clip(md_to_text(d["exclusions_md"]), lim["excl"]))
    modes = [a["mode"] for a in d.get("apply") or [] if a.get("mode")]
    if modes:
        lines.append("How to apply (ways): " + ", ".join(modes))
    if full:
        for a in (d.get("apply") or [])[:2]:
            body = md_to_text(a.get("steps_md"))
            if body or a.get("url"):
                lines.append(f"Apply - {a.get('mode') or 'process'}" + (f" (portal: {a['url']})" if a.get("url") else "") + ":\n" + _clip(body, lim["steps"]))
    return "\n".join(lines)
