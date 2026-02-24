"""
routers/cards.py — SRS flashcard endpoints.

Endpoints:
  GET  /api/cards/due           — cards due for review today
  GET  /api/cards/new           — unseen items ready to be introduced
  POST /api/cards/review        — submit a review grade
  POST /api/cards/sessions      — open a new study session
  PATCH /api/cards/sessions/{id} — close a study session
"""
from datetime import datetime
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

import core.srs as srs_engine
from database.db import get_session
from models.kanji import Kanji, KanjiResponse
from models.srs import (
    ItemType,
    ReviewRequest,
    ReviewResponse,
    SessionStartResponse,
    StudySession,
)
from models.vocab import JLPTLevel, Vocab, VocabResponse

router = APIRouter(prefix="/api/cards", tags=["cards"])


# ─── GET due cards ────────────────────────────────────────────────────────────

@router.get("/due")
async def get_due_cards(
    level: JLPTLevel = Query(JLPTLevel.N5),
    type: ItemType = Query(ItemType.vocab),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_session),
) -> list[dict]:
    cards = await srs_engine.get_due_cards(db, level, type, limit)
    return [_card_with_item(c) for c in cards]


# ─── GET new items ────────────────────────────────────────────────────────────

@router.get("/new")
async def get_new_cards(
    level: JLPTLevel = Query(JLPTLevel.N5),
    type: ItemType = Query(ItemType.vocab),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_session),
) -> list[dict]:
    items = await srs_engine.get_new_items(db, level, type, limit)
    result = []
    for item in items:
        card = await srs_engine.create_card(db, type, item.id)
        result.append(_item_with_card(item, card, type))
    return result


# ─── POST review ──────────────────────────────────────────────────────────────

@router.post("/review", response_model=ReviewResponse)
async def submit_review(
    payload: ReviewRequest,
    session_id: Optional[int] = Query(None),
    db: AsyncSession = Depends(get_session),
) -> ReviewResponse:
    card = await srs_engine.get_card(db, payload.card_id)
    if card is None:
        raise HTTPException(status_code=404, detail="Card not found.")

    updated_card = srs_engine.sm2_review(card, payload.grade)
    db.add(updated_card)

    await srs_engine.write_review_log(db, payload.card_id, payload.grade, session_id)

    # Update study session counters if session_id provided
    if session_id is not None:
        from sqlmodel import select
        res = await db.execute(
            select(StudySession).where(StudySession.id == session_id)
        )
        ss = res.scalar_one_or_none()
        if ss:
            ss.cards_reviewed += 1
            if payload.grade >= 3:
                ss.correct += 1
            else:
                ss.incorrect += 1

    return ReviewResponse(
        card_id=payload.card_id,
        ease_factor=updated_card.ease_factor,
        interval_days=updated_card.interval_days,
        reps=updated_card.reps,
        next_due=updated_card.due_date.isoformat(),
        session_correct=0,   # Will be read from session endpoint
        session_incorrect=0,
    )


# ─── Study session management ─────────────────────────────────────────────────

@router.post("/sessions", response_model=SessionStartResponse)
async def start_session(
    db: AsyncSession = Depends(get_session),
) -> SessionStartResponse:
    ss = await srs_engine.open_session(db)
    return SessionStartResponse(
        session_id=ss.id,
        started_at=ss.started_at.isoformat(),
    )


@router.patch("/sessions/{session_id}")
async def end_session(
    session_id: int,
    db: AsyncSession = Depends(get_session),
) -> dict:
    await srs_engine.close_session(db, session_id)
    return {"ok": True, "ended_at": datetime.utcnow().isoformat()}


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _card_with_item(card) -> dict:
    return {
        "card_id": card.id,
        "item_type": card.item_type,
        "item_id": card.item_id,
        "ease_factor": card.ease_factor,
        "interval_days": card.interval_days,
        "reps": card.reps,
        "due_date": card.due_date.isoformat(),
    }


def _item_with_card(item, card, item_type: ItemType) -> dict:
    base = _card_with_item(card)
    if item_type == ItemType.vocab:
        base["word"] = item.word
        base["reading"] = item.reading
        base["meaning"] = item.meaning
        base["part_of_speech"] = item.part_of_speech
        base["jlpt_level"] = item.jlpt_level
        base["example_jp"] = item.example_jp
        base["example_en"] = item.example_en
    else:
        base["character"] = item.character
        base["on_yomi"] = item.on_yomi
        base["kun_yomi"] = item.kun_yomi
        base["meaning"] = item.meaning
        base["stroke_count"] = item.stroke_count
        base["jlpt_level"] = item.jlpt_level
        base["example_word"] = item.example_word
        base["example_sentence"] = item.example_sentence
    return base
