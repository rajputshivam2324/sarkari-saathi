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
STALE_TTL = 60 * 60 * 24 * 7   # last good copy, served only when myScheme is down or slow
DETAIL_KEY = "ss:scheme:detail:v6:{slug}:{lang}"
STALE_KEY = "ss:scheme:stale:v6:{slug}:{lang}"
SUPPORTED_LANGS = {"en", "hi"}  # myScheme serves more, but these are the ones we verified end to end
PAGE_URL = "https://www.myscheme.gov.in/schemes/{slug}"

_client: tuple[Any, httpx.AsyncClient] | None = None
_inflight: dict[str, "asyncio.Task[dict[str, Any] | None]"] = {}


def _http() -> httpx.AsyncClient:
    """Pooled client. myScheme answers in about 100 ms on a warm connection, so a slow call is a failing call."""
    global _client
    loop = asyncio.get_running_loop()
    if _client is None or _client[0] is not loop:
        _client = (loop, httpx.AsyncClient(timeout=httpx.Timeout(5.0, connect=3.0)))
    return _client[1]


# --------------------------------------------------------------------------------------
# text cleaning
# --------------------------------------------------------------------------------------
_TAG = re.compile(r"<[^>]+>")
_BR = re.compile(r"<br\s*/?>", re.IGNORECASE)
_LINK = re.compile(r"\[([^\]]+)\]\(([^)\s]+)[^)]*\)")


# Defects measured across 50 real myScheme records (English and Hindi), fixed here once so the
# screen and the AI both read clean text.
_HIDDEN_ENTITY = re.compile(r"&\s*#\s*(\d+)\s*;?")                 # "& #39;"  (Hindi translation broke the entity)
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
    t = _HIDDEN_ENTITY.sub(lambda m: html.unescape(f"&#{m.group(1)};") if m.group(1) in {"39", "34", "38", "8217", "8216", "8220", "8221"} else "", t)
    t = _BR.sub("\n", t)
    t = _TAG.sub("", t)
    t = html.unescape(t)
    t = _LINK_SPACE.sub(r"](\1)", t)
    t = re.sub(r"(?<=[.।!?])[ \t]+>[ \t]*", "\n> ", t)                  # a ">" note glued to the end of a sentence
    t = _STAR_RUN.sub("**", t)
    t = re.sub(r"(?<=\S)[ \t]*#{2,6}[ \t]*(?=\S)", "\n", t)             # "text ####more" -> new line
    t = re.sub(r"^#{1,6}[ \t]*", "", t, flags=re.MULTILINE)                  # headings at line start
    t = re.sub(r"\n{2,}", "\n", t) if False else t
    t = re.sub(r"(?<=[.।!?])[ \t]+(?=\d{1,2}[.)][ \t]+\S)", "\n", t)       # "...ends. 1. next" -> new item
    t = re.sub(r"^((?:प्रक्रिया|process|विकल्प|option)[ \t]*\d+[ \t]*[:：])[ \t]*", r"\1\n", t, flags=re.MULTILINE | re.IGNORECASE)
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
        "open_date": (basic.get("schemeOpenDate") or None) if isinstance(basic.get("schemeOpenDate"), str) else None,
        "scheme_type": ((basic.get("schemeType") or {}).get("label") if isinstance(basic.get("schemeType"), dict) else None),
        "dbt": bool(basic.get("dbtScheme")) if basic.get("dbtScheme") is not None else None,
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
    if details is None:
        # myScheme is down or slow: the last good copy is better than nothing.
        stale = await cache.get_json(STALE_KEY.format(slug=slug, lang=lang))
        if isinstance(stale, dict) and stale.get("slug") == slug:
            logger.info("serving stale scheme record for %s (%s)", slug, lang)
            return stale
    if details is None and lang != "en":
        return await get_details(slug, "en")          # no Hindi record: use English rather than nothing
    if details:
        await cache.set_json(key, details, DETAIL_TTL)
        await cache.set_json(STALE_KEY.format(slug=slug, lang=lang), details, STALE_TTL)
    return details


async def refresh(slug: str, lang: str = "en") -> bool:
    """Re-fetch one record now, bypassing the fresh cache (used by the background refresh)."""
    slug = (slug or "").strip()
    if not re.fullmatch(r"[A-Za-z0-9._-]{1,80}", slug) or lang not in SUPPORTED_LANGS:
        return False
    details = await _fetch(slug, lang)
    if not details:
        return False
    cache = get_cache()
    await cache.set_json(DETAIL_KEY.format(slug=slug, lang=lang), details, DETAIL_TTL)
    await cache.set_json(STALE_KEY.format(slug=slug, lang=lang), details, STALE_TTL)
    return True


async def prefetch(slugs: list[str], langs: tuple[str, ...] = ("en", "hi"), *, force: bool = False, concurrency: int = 4) -> dict[str, int]:
    """Load records for frequently asked schemes so their questions never wait on myScheme.

    Runs in the background at startup and then on a timer. Failures are counted, never raised.
    """
    sem = asyncio.Semaphore(concurrency)
    stats = {"ok": 0, "failed": 0}

    async def one(slug: str, lang: str) -> None:
        async with sem:
            try:
                good = await refresh(slug, lang) if force else bool(await get_details(slug, lang))
            except Exception as exc:  # pragma: no cover - defensive
                logger.warning("prefetch %s/%s failed: %s", slug, lang, exc)
                good = False
            stats["ok" if good else "failed"] += 1

    await asyncio.gather(*[one(s, l) for s in dict.fromkeys(x for x in slugs if x) for l in langs])
    return stats


async def get_many(slugs: list[str | None], lang: str = "en") -> dict[str, dict[str, Any]]:
    uniq = [s for s in dict.fromkeys(slugs) if s]
    results = await asyncio.gather(*[get_details(s, lang) for s in uniq], return_exceptions=True)
    return {s: r for s, r in zip(uniq, results) if isinstance(r, dict)}



# --------------------------------------------------------------------------------------
# facts for the model
# --------------------------------------------------------------------------------------
# Which sections a kind of question needs in full. Every other section is kept short.
TOPIC_SECTIONS: dict[str, set[str]] = {
    "basics": {"identity", "about", "benefits", "eligibility"},
    "eligibility": {"eligibility", "exclusions", "definitions", "identity"},
    "benefits": {"benefits", "identity"},
    "docs": {"apply", "eligibility", "supplement"},
    "apply": {"apply", "links", "supplement"},
    "status": {"apply", "supplement", "links"},
    "help": {"apply", "links", "supplement", "identity"},
    "active": {"identity", "apply", "supplement"},
    "compare": {"identity", "about", "benefits", "eligibility", "exclusions", "apply"},
}
FOCUS_BUDGET = 3600     # characters per section when the question is about that section
SHORT_BUDGET = 380      # characters per section otherwise
BROAD_BUDGET = 1200     # characters per section when we do not know the topic but the scheme is the subject

_QUERY_STOP = {
    "the", "and", "for", "can", "how", "what", "who", "this", "that", "with", "are", "was", "does", "will", "any",
    "scheme", "yojana", "apply", "get", "have", "from", "which", "when", "where", "there", "about", "tell", "please",
}


def _query_words(question: str) -> set[str]:
    return {w for w in re.findall(r"[a-z0-9]{3,}", (question or "").lower()) if w not in _QUERY_STOP}


def _select(text: str, budget: int, query: set[str]) -> str:
    """Fit `text` into `budget` characters, keeping the paragraphs most relevant to the question.

    The old behaviour cut every section at its start, so an answer that sat further down never reached
    the model. Here the first paragraph is always kept, then the paragraphs that share the most words
    with the question, and the result is put back in reading order.
    """
    text = (text or "").strip()
    if len(text) <= budget:
        return text
    blocks = [b.strip() for b in re.split(r"\n+", text) if b.strip()]
    if len(blocks) <= 1:
        return _clip(text, budget)
    ranked = sorted(
        range(1, len(blocks)),
        key=lambda i: (-len(query & set(re.findall(r"[a-z0-9]{3,}", blocks[i].lower()))), i),
    )
    chosen: set[int] = set()
    used = 0
    for i in [0, *ranked]:
        n = len(blocks[i]) + 1
        if used + n > budget:
            if not chosen:
                chosen.add(i)
                blocks[i] = _clip(blocks[i], budget)
                used = budget
            continue
        chosen.add(i)
        used += n
    return "\n".join(blocks[i] for i in sorted(chosen))


def _clip(text: str, limit: int) -> str:
    text = text.strip()
    if len(text) <= limit:
        return text
    cut = text[:limit].rsplit("\n", 1)[0] if "\n" in text[:limit] else text[:limit].rsplit(" ", 1)[0]
    return cut.rstrip(" ,;:-") + " …"


def _pretty_date(value: str | None) -> str | None:
    if not value:
        return None
    m = re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})", value.strip())
    if not m:
        return value.strip()
    months = "January February March April May June July August September October November December".split()
    y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
    return f"{d} {months[mo - 1]} {y}" if 1 <= mo <= 12 else value


def facts_text(
    d: dict[str, Any],
    *,
    full: bool = False,
    topic: str | None = None,
    question: str = "",
    supplement: dict[str, Any] | None = None,
) -> str:
    """Everything the model may state about this scheme, as labelled plain text.

    full=False  short version, for suggesting a scheme (benefit, who it is for, how to apply).
    full=True   the scheme being discussed. Sections the question is about are given in full (and, if
                they are very long, trimmed to the paragraphs that match the question); the rest stay short.
                `topic` is one of TOPIC_SECTIONS; None means "the scheme in general".
    `supplement` is the verified extra data (documents, helpline, ...) for schemes where myScheme has none.
    """
    sup = supplement or {}
    query = _query_words(question)
    wanted = TOPIC_SECTIONS.get(topic or "", set())

    def budget(section: str) -> int:
        if not full:
            return {"benefits": 360, "eligibility": 420}.get(section, 0)
        if section in wanted:
            return FOCUS_BUDGET
        return SHORT_BUDGET if wanted else BROAD_BUDGET

    def part(section: str, md: str | None) -> str:
        b = budget(section)
        return _select(md_to_text(md), b, query) if (md and b) else ""

    lines: list[str] = [f"Official name: {d.get('name')}"]

    # --- identity -------------------------------------------------------------------
    meta: list[str] = []
    if d.get("level"):
        meta.append(f"Level: {d['level']} government scheme" if d["level"] in ("Central", "State") else f"Level: {d['level']}")
    if d.get("scheme_type"):
        meta.append(f"Type: {d['scheme_type']}")
    if d.get("ministry"):
        meta.append(f"Ministry: {d['ministry']}")
    if d.get("department"):
        meta.append(f"Department: {d['department']}")
    if d.get("dbt") is True:
        meta.append("Benefit is paid by Direct Benefit Transfer (DBT) to the bank account")
    if full or d.get("level"):
        lines.extend(meta[:2] if not full else meta)
    open_date = _pretty_date(d.get("open_date"))
    if full and open_date:
        lines.append(f"Open date listed on myScheme: {open_date} (not a closing date; the record has no closing date)")
    if d.get("beneficiaries"):
        lines.append("Meant for: " + ", ".join(d["beneficiaries"]) + (f" ({', '.join(d['categories'][:2])})" if d.get("categories") and full else (f" ({d['categories'][0]})" if d.get("categories") else "")))
    if full and d.get("tags"):
        lines.append("Tags: " + ", ".join(d["tags"]))

    # --- about ----------------------------------------------------------------------
    if d.get("brief"):
        lines.append("About: " + _clip(md_to_text(d["brief"]), 300))
    if full and (not wanted or "about" in wanted) and d.get("description_md"):
        lines.append("Description:\n" + _select(md_to_text(d["description_md"]), FOCUS_BUDGET if "about" in wanted else 900, query))

    # --- the rest of the record -----------------------------------------------------
    if (t := part("benefits", d.get("benefits_md"))):
        lines.append("Benefits:\n" + t)
    if (t := part("eligibility", d.get("eligibility_md"))):
        lines.append("Who is eligible:\n" + t)
    if full and (t := part("exclusions", d.get("exclusions_md"))):
        lines.append("Not eligible / excluded:\n" + t)

    modes = [a["mode"] for a in d.get("apply") or [] if a.get("mode")]
    if modes:
        lines.append("How to apply (ways): " + ", ".join(modes))
    if full:
        per_mode = FOCUS_BUDGET // max(1, min(len(d.get("apply") or []), 3)) if "apply" in wanted else 450
        for a in (d.get("apply") or [])[:3]:
            body = _select(md_to_text(a.get("steps_md")), per_mode, query)
            if body or a.get("url"):
                lines.append(f"Apply - {a.get('mode') or 'process'}" + (f" (portal: {a['url']})" if a.get("url") else "") + ":\n" + body)
        refs = d.get("references") or []
        if refs and ("links" in wanted or not wanted):
            lines.append("Official documents and links: " + "; ".join(f"{r['title'] or 'Link'} ({r['url']})" for r in refs[:6]))
        if (not wanted or "definitions" in wanted) and d.get("definitions"):
            defs = [f"{x['name']}: {_clip(x['text'], 320)}" for x in d["definitions"][:4] if x.get("text")]
            if defs:
                lines.append("Definitions used by the scheme:\n" + "\n".join(defs))

    # --- verified extra facts -------------------------------------------------------
    if full:
        sup_lines = _supplement_lines(sup)
        if sup_lines:
            lines.append("Verified extra information (from the scheme's official pages):\n" + "\n".join(sup_lines))
        gaps = _gaps(d, sup)
        if gaps:
            lines.append(
                "NOT AVAILABLE in our records (if asked, say honestly that you do not have it and point to the official portal or a Common Service Centre; never guess): "
                + "; ".join(gaps)
            )
    return "\n".join(lines)


_SUPPLEMENT_LABELS = [
    ("documents", "Documents required"),
    ("documents_note", "Documents note"),
    ("fee", "Application fee"),
    ("last_date", "Last date / open period"),
    ("approval_time", "Approval time"),
    ("status_check", "How to check application status"),
    ("payment", "Payment details"),
    ("helpline", "Helpline"),
    ("grievance", "Complaints and appeal"),
    ("notes", "Other"),
]


def _supplement_lines(sup: dict[str, Any]) -> list[str]:
    out: list[str] = []
    for key, label in _SUPPLEMENT_LABELS:
        v = sup.get(key)
        if not v:
            continue
        out.append(f"- {label}: " + ("; ".join(v) if isinstance(v, list) else str(v)))
    return out


def _gaps(d: dict[str, Any], sup: dict[str, Any]) -> list[str]:
    """What a person may ask that neither the myScheme record nor the verified supplement answers."""
    text = " ".join(
        str(d.get(k) or "") for k in ("benefits_md", "eligibility_md", "exclusions_md", "description_md")
    ) + " " + " ".join(a.get("steps_md") or "" for a in d.get("apply") or [])
    gaps: list[str] = []
    if not sup.get("documents"):
        gaps.append("a complete list of required documents (only documents named in the steps above are known)")
    if not sup.get("fee") and not re.search(r"\bfee\b|free of cost|no charge|charges", text, re.IGNORECASE):
        gaps.append("whether there is an application fee")
    if not sup.get("last_date"):
        gaps.append("the last date to apply and whether applications are open today")
    if not sup.get("approval_time"):
        gaps.append("how many days approval takes")
    if not sup.get("status_check") and not re.search(r"status", text, re.IGNORECASE):
        gaps.append("how to check application status")
    if not sup.get("payment"):
        gaps.append("exact payment dates and what to do if a payment is missing")
    if not sup.get("helpline"):
        gaps.append("a helpline number")
    if not sup.get("grievance"):
        gaps.append("the complaint, grievance and appeal process")
    gaps.append("the nearest application centre")
    return gaps
