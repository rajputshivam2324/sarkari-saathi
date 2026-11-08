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


@asynccontextmanager
async def lifespan(_app: FastAPI):
    try:
        Base.metadata.create_all(bind=engine, checkfirst=True)
    except SQLAlchemyError as exc:
        logger.warning("create_all skipped/failed: %s", exc)

    # Eager warm myScheme + prompt cache (runs even with in-memory Redis)
    try:
        from app.services.myscheme import eager_warm
        from app.services.prompt_cache import get_system_prompt

        await get_system_prompt()
        stats = await eager_warm()
        logger.info("Eager cache warm: %s", stats)
    except Exception as exc:
        logger.warning("Eager warm failed (will retry on demand): %s", exc)

    yield


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
