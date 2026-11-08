"""Persist + Redis-mirror chat history per user session."""

from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.models import ChatMessage
from app.services.redis_cache import get_cache

logger = logging.getLogger(__name__)

HISTORY_KEY = "ss:chat:{user_id}:{session_id}"
HISTORY_TTL = 60 * 60 * 24 * 7
HISTORY_LIMIT = 80


async def load_history(
    db: Session, user_id: uuid.UUID, session_id: str
) -> list[dict[str, Any]]:
    cache = get_cache()
    key = HISTORY_KEY.format(user_id=user_id, session_id=session_id)
    cached = await cache.get_json(key)
    if isinstance(cached, list) and cached:
        return cached[-HISTORY_LIMIT:]

    def _query() -> list[dict[str, Any]]:
        rows = (
            db.query(ChatMessage)
            .filter(ChatMessage.user_id == user_id, ChatMessage.session_id == session_id)
            .order_by(ChatMessage.created_at.asc())
            .limit(HISTORY_LIMIT)
            .all()
        )
        return [
            {
                "id": str(r.id),
                "role": r.role,
                "text": r.text,
                "language": r.language,
                "schemes": r.schemes,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in rows
        ]

    history = await asyncio.to_thread(_query)
    if history:
        await cache.set_json(key, history, HISTORY_TTL)
    return history


async def append_message(
    db: Session,
    *,
    user_id: uuid.UUID,
    session_id: str,
    role: str,
    text: str,
    language: str | None = None,
    schemes: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    row = ChatMessage(
        user_id=user_id,
        session_id=session_id,
        role=role,
        text=text,
        language=language,
        schemes=schemes,
    )
    db.add(row)
    db.commit()
    db.refresh(row)

    msg = {
        "id": str(row.id),
        "role": row.role,
        "text": row.text,
        "language": row.language,
        "schemes": row.schemes,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }

    cache = get_cache()
    key = HISTORY_KEY.format(user_id=user_id, session_id=session_id)
    history = await cache.get_json(key)
    if not isinstance(history, list):
        history = await load_history(db, user_id, session_id)
        # load_history already includes this message if just committed — avoid double
        if history and history[-1].get("id") == msg["id"]:
            return msg
    history = list(history or [])
    history.append(msg)
    await cache.set_json(key, history[-HISTORY_LIMIT:], HISTORY_TTL)
    return msg


async def clear_session(db: Session, user_id: uuid.UUID, session_id: str) -> None:
    db.query(ChatMessage).filter(
        ChatMessage.user_id == user_id, ChatMessage.session_id == session_id
    ).delete()
    db.commit()
    cache = get_cache()
    await cache.set(
        HISTORY_KEY.format(user_id=user_id, session_id=session_id), "[]", HISTORY_TTL
    )


# --------------------------------------------------------------------------------------
# Off-the-critical-path persistence for the live conversation.
#
# A turn used to wait on ~8 sequential round trips to the remote database (about 5 s with
# Neon) *on the event loop*, which also froze the speech streams of every other caller.
# Now a message is built in-process, shown to the person immediately, and saved in the
# background in order. flush() makes sure nothing is lost on disconnect.
# --------------------------------------------------------------------------------------
def make_message(
    role: str,
    text: str,
    language: str | None = None,
    schemes: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    return {
        "id": str(uuid.uuid4()),
        "role": role,
        "text": text,
        "language": language,
        "schemes": schemes,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }


def _insert_sync(user_id: uuid.UUID, session_id: str, msg: dict[str, Any]) -> None:
    with SessionLocal() as db:
        db.add(
            ChatMessage(
                id=uuid.UUID(msg["id"]),
                user_id=user_id,
                session_id=session_id,
                role=msg["role"],
                text=msg["text"],
                language=msg.get("language"),
                schemes=msg.get("schemes"),
                created_at=datetime.fromisoformat(msg["created_at"]),
            )
        )
        db.commit()


async def _mirror(user_id: uuid.UUID, session_id: str, msg: dict[str, Any]) -> None:
    """Append to the cached history, but only if one already exists (never start a partial one)."""
    cache = get_cache()
    key = HISTORY_KEY.format(user_id=user_id, session_id=session_id)
    cached = await cache.get_json(key)
    if isinstance(cached, list):
        await cache.set_json(key, [*cached, msg][-HISTORY_LIMIT:], HISTORY_TTL)


class HistoryWriter:
    """Saves one connection's messages in order, in the background."""

    def __init__(self) -> None:
        self._tail: asyncio.Task[None] | None = None

    def save(self, user_id: uuid.UUID, session_id: str, msg: dict[str, Any]) -> None:
        previous = self._tail

        async def run() -> None:
            if previous is not None:
                await asyncio.shield(previous)  # keep insert order; a failed predecessor is already logged
            for attempt in (1, 2):
                try:
                    await asyncio.to_thread(_insert_sync, user_id, session_id, msg)
                    await _mirror(user_id, session_id, msg)
                    return
                except Exception:
                    if attempt == 2:
                        logger.exception("could not save chat message %s", msg.get("id"))
                    else:
                        await asyncio.sleep(0.5)

        self._tail = asyncio.create_task(run())

    async def flush(self, timeout: float = 20.0) -> None:
        tail = self._tail
        if tail is None or tail.done():
            return
        try:
            await asyncio.wait_for(asyncio.shield(tail), timeout)
        except (asyncio.TimeoutError, asyncio.CancelledError):
            logger.warning("chat history flush timed out; messages may be saved late")
