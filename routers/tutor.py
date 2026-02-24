"""
routers/tutor.py — AI Tutor SSE streaming endpoint.

POST /api/tutor/chat
  Request body: { "message": str, "mode": TutorMode, "level": str }
  Response: text/event-stream — each event is data: {"token": "..."}\n\n
            Terminated by data: [DONE]\n\n
"""
import json
from typing import Optional

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import SQLModel

from core.tutor import TutorContext, TutorMode, stream_response
from database.db import get_session
from models.meta import Meta
from models.srs import ReviewLog, SRSCard
from models.vocab import Vocab

router = APIRouter(prefix="/api/tutor", tags=["tutor"])


class TutorRequest(SQLModel):
    message: str
    mode: TutorMode = TutorMode.CHAT
    level: Optional[str] = None  # If None, reads from meta table


@router.post("/chat")
async def tutor_chat(
    payload: TutorRequest,
    db: AsyncSession = Depends(get_session),
) -> StreamingResponse:
    ctx = await _build_context(db, payload.level)
    if payload.level:
        ctx.jlpt_level = payload.level

    async def event_stream():
        async for token in stream_response(payload.message, payload.mode, ctx):
            yield f"data: {json.dumps({'token': token})}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


async def _build_context(db: AsyncSession, override_level: Optional[str]) -> TutorContext:
    """Read JLPT focus, recent words, and weak cards from DB."""
    # JLPT level
    meta_res = await db.execute(select(Meta).where(Meta.key == "jlpt_focus"))
    meta_row = meta_res.scalar_one_or_none()
    level = override_level or (meta_row.value.strip('"') if meta_row else "N5")

    # 10 most recently reviewed vocab words
    recent_res = await db.execute(
        select(Vocab.word)
        .join(SRSCard, SRSCard.item_id == Vocab.id)
        .join(ReviewLog, ReviewLog.card_id == SRSCard.id)
        .where(SRSCard.item_type == "vocab")
        .order_by(ReviewLog.reviewed_at.desc())
        .limit(10)
    )
    recent_words = [row[0] for row in recent_res.all()]

    # 5 weakest cards (lowest ease factor — hardest for learner)
    weak_res = await db.execute(
        select(Vocab.word)
        .join(SRSCard, (SRSCard.item_id == Vocab.id) & (SRSCard.item_type == "vocab"))
        .order_by(SRSCard.ease_factor.asc())
        .limit(5)
    )
    weak_cards = [row[0] for row in weak_res.all()]

    return TutorContext(
        jlpt_level=level,
        recent_words=recent_words,
        weak_cards=weak_cards,
    )
