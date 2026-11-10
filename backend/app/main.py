import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.exc import SQLAlchemyError

from app.auth import router as auth_router
from app.config import GNANI_LANGUAGES, get_settings
from app.db import Base, engine
from app.models import ChatMessage, User  # noqa: F401
from app.routers.history import router as history_router
from app.routers.live import router as live_router
from app.routers.schemes import router as schemes_router
from app.routers.voice import router as voice_router

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
settings = get_settings()


REFRESH_EVERY_S = 12 * 60 * 60


async def _keep_popular_schemes_warm() -> None:
    """Load the full official record of the frequently asked schemes, then refresh it twice a day.

    Questions about these schemes never wait on myScheme. Any other scheme is fetched live on its first
    question (about 0.1 to 0.5 s) and cached for a day. Failures are logged and retried next round.
    """
    from app.schemes_data import SCHEMES
    from app.services import scheme_details as SD
    from app.services.supplement import supplemented_slugs

    slugs = list(dict.fromkeys([s["myscheme_slug"] for s in SCHEMES if s.get("myscheme_slug")] + supplemented_slugs()))
    first = True
    while True:
        try:
            stats = await SD.prefetch(slugs, force=not first)
            logger.info("Scheme records %s: %s for %d schemes", "loaded" if first else "refreshed", stats, len(slugs))
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.warning("Scheme record prefetch failed (will retry): %s", exc)
        first = False
        await asyncio.sleep(REFRESH_EVERY_S)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    try:
        Base.metadata.create_all(bind=engine, checkfirst=True)
    except SQLAlchemyError as exc:
        logger.warning("create_all skipped/failed: %s", exc)

    warm_task = asyncio.create_task(_keep_popular_schemes_warm())   # in the background: never delays startup

    # Eager warm myScheme + prompt cache (runs even with in-memory Redis)
    try:
        from app.services.myscheme import eager_warm
        from app.services.prompt_cache import get_system_prompt

        await get_system_prompt()
        stats = await eager_warm()
        logger.info("Eager cache warm: %s", stats)
    except Exception as exc:
        logger.warning("Eager warm failed (will retry on demand): %s", exc)

    try:
        yield
    finally:
        warm_task.cancel()
        try:
            await warm_task
        except asyncio.CancelledError:
            pass


app = FastAPI(
    title=settings.app_name,
    version="2.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        settings.frontend_origin,
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(voice_router)
app.include_router(schemes_router)
app.include_router(history_router)
app.include_router(live_router)


@app.get("/health")
async def health() -> dict:
    from app.services.redis_cache import get_cache

    cache = get_cache()
    redis_ok = await cache.ping() if cache.enabled else False
    return {
        "status": "ok",
        "app": settings.app_name,
        "environment": settings.environment,
        "evon_enabled": settings.gnani_evon_enabled,
        "redis": {"configured": cache.enabled, "ping": redis_ok},
        "languages": GNANI_LANGUAGES,
        "stt_language": settings.gnani_stt_language,
    }
