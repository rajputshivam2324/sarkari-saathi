from fastapi import APIRouter, Query

from app.services.myscheme import (
    _tokens,
    eager_warm,
    get_catalog,
    score_scheme,
    search_schemes,
)

router = APIRouter(prefix="/schemes", tags=["schemes"])


@router.get("")
async def list_schemes(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    q: str | None = Query(None, max_length=120),
) -> dict:
    """
    Paginated catalogue.

    `count` is the total number of matching schemes (kept for backward
    compatibility); `total` is the same value. `schemes` is the requested page.
    When `q` is given, results are filtered by name/slug and ranked by relevance.
    """
    catalog = await get_catalog()

    query = (q or "").strip()
    if query:
        tokens = _tokens(query)
        ranked = []
        for s in catalog:
            score = score_scheme(s, tokens) if tokens else 0
            if score > 0:
                ranked.append((score, s))
        ranked.sort(key=lambda item: item[0], reverse=True)
        matching = [s for _, s in ranked]
    else:
        matching = catalog

    total = len(matching)
    return {
        "count": total,
        "total": total,
        "offset": offset,
        "limit": limit,
        "query": query or None,
        "source": "myscheme.gov.in",
        "schemes": matching[offset : offset + limit],
    }


@router.get("/search")
async def search(q: str = Query(..., min_length=1), limit: int = Query(8, ge=1, le=20)) -> dict:
    hits = await search_schemes(q, limit=limit)
    return {"query": q, "count": len(hits), "source": "myscheme.gov.in", "schemes": hits}


@router.post("/warm")
async def warm() -> dict:
    return await eager_warm()
