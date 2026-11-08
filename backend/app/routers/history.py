"""Conversation history: list, open and delete a signed-in user's past chat sessions.

Every query is scoped to the authenticated user, so one user can never read or
delete another user's conversations by guessing a session id.
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import and_, case, desc, func, select
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.db import get_db
from app.models import ChatMessage, User
from app.services.chat_history import clear_session

router = APIRouter(prefix="/chat", tags=["chat"])

TITLE_MAX = 90
MESSAGES_MAX = 500


def _iso(value: Any) -> str | None:
    return value.isoformat() if value is not None else None


def _title(text: str) -> str:
    t = " ".join((text or "").split())
    return t if len(t) <= TITLE_MAX else t[: TITLE_MAX - 1].rstrip() + "…"


@router.get("/sessions")
def list_sessions(
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    limit: int = Query(10, ge=1, le=50),
    offset: int = Query(0, ge=0),
) -> dict[str, Any]:
    """
    Past conversations, newest first. A session only counts once the user has said
    something; the empty greeting-only sessions created on every visit are hidden.
    """
    user_msgs = func.sum(case((ChatMessage.role == "user", 1), else_=0))
    grouped = (
        select(
            ChatMessage.session_id.label("session_id"),
            func.min(ChatMessage.created_at).label("started_at"),
            func.max(ChatMessage.created_at).label("last_at"),
            func.count().label("message_count"),
        )
        .where(ChatMessage.user_id == user.id)
        .group_by(ChatMessage.session_id)
        .having(user_msgs > 0)
    )

    total = db.scalar(select(func.count()).select_from(grouped.subquery())) or 0
    rows = db.execute(
        grouped.order_by(desc("last_at"), ChatMessage.session_id).offset(offset).limit(limit)
    ).all()

    # The first thing the user said becomes the conversation's title.
    titles: dict[str, tuple[str, str | None]] = {}
    ids = [r.session_id for r in rows]
    if ids:
        first_at = (
            select(
                ChatMessage.session_id.label("sid"),
                func.min(ChatMessage.created_at).label("t"),
            )
            .where(
                ChatMessage.user_id == user.id,
                ChatMessage.role == "user",
                ChatMessage.session_id.in_(ids),
            )
            .group_by(ChatMessage.session_id)
            .subquery()
        )
        first_rows = db.execute(
            select(ChatMessage.session_id, ChatMessage.text, ChatMessage.language).join(
                first_at,
                and_(
                    ChatMessage.session_id == first_at.c.sid,
                    ChatMessage.created_at == first_at.c.t,
                ),
            ).where(ChatMessage.user_id == user.id, ChatMessage.role == "user")
        ).all()
        for sid, text, language in first_rows:
            titles.setdefault(sid, (_title(text), language))

    return {
        "total": total,
        "offset": offset,
        "limit": limit,
        "sessions": [
            {
                "session_id": r.session_id,
                "title": titles.get(r.session_id, ("Conversation", None))[0],
                "language": titles.get(r.session_id, ("", None))[1],
                "started_at": _iso(r.started_at),
                "last_at": _iso(r.last_at),
                "message_count": int(r.message_count),
            }
            for r in rows
        ],
    }


@router.get("/sessions/{session_id}")
def get_session(
    session_id: str,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> dict[str, Any]:
    rows = (
        db.query(ChatMessage)
        .filter(ChatMessage.user_id == user.id, ChatMessage.session_id == session_id)
        .order_by(ChatMessage.created_at.asc())
        .limit(MESSAGES_MAX)
        .all()
    )
    if not rows:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return {
        "session_id": session_id,
        "messages": [
            {
                "id": str(r.id),
                "role": r.role,
                "text": r.text,
                "language": r.language,
                "schemes": r.schemes,
                "created_at": _iso(r.created_at),
            }
            for r in rows
        ],
    }


@router.delete("/sessions/{session_id}")
async def delete_session(
    session_id: str,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> dict[str, Any]:
    count = (
        db.query(ChatMessage)
        .filter(ChatMessage.user_id == user.id, ChatMessage.session_id == session_id)
        .count()
    )
    if count == 0:
        raise HTTPException(status_code=404, detail="Conversation not found")
    await clear_session(db, user.id, session_id)
    return {"deleted": count, "session_id": session_id}
