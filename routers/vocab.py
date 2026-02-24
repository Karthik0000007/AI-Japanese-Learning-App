"""routers/vocab.py — Vocabulary browse and search endpoints."""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from database.db import get_session
from models.vocab import JLPTLevel, Vocab, VocabPage, VocabResponse

router = APIRouter(prefix="/api/vocab", tags=["vocab"])

PAGE_SIZE = 50


@router.get("", response_model=VocabPage)
async def list_vocab(
    level: Optional[JLPTLevel] = Query(None),
    q: Optional[str] = Query(None, description="Search in word, reading, or meaning"),
    page: int = Query(1, ge=1),
    db: AsyncSession = Depends(get_session),
) -> VocabPage:
    stmt = select(Vocab)
    if level:
        stmt = stmt.where(Vocab.jlpt_level == level)
    if q:
        like = f"%{q}%"
        stmt = stmt.where(
            Vocab.word.ilike(like) | Vocab.reading.ilike(like) | Vocab.meaning.ilike(like)
        )

    # Count total before pagination
    count_stmt = select(func.count()).select_from(stmt.subquery())
    total: int = (await db.execute(count_stmt)).scalar_one()

    stmt = stmt.order_by(Vocab.jlpt_level, Vocab.id)
    stmt = stmt.offset((page - 1) * PAGE_SIZE).limit(PAGE_SIZE)
    rows = (await db.execute(stmt)).scalars().all()

    items = [
        VocabResponse(
            id=v.id,
            word=v.word,
            reading=v.reading,
            meaning=v.meaning,
            part_of_speech=v.part_of_speech,
            jlpt_level=v.jlpt_level,
            example_jp=v.example_jp,
            example_en=v.example_en,
        )
        for v in rows
    ]
    return VocabPage(items=items, total=total, page=page, page_size=PAGE_SIZE)


@router.get("/{vocab_id}", response_model=VocabResponse)
async def get_vocab_by_id(
    vocab_id: int,
    db: AsyncSession = Depends(get_session),
) -> VocabResponse:
    result = await db.execute(select(Vocab).where(Vocab.id == vocab_id))
    vocab = result.scalar_one_or_none()
    if vocab is None:
        raise HTTPException(status_code=404, detail="Vocabulary item not found.")
    return VocabResponse(
        id=vocab.id,
        word=vocab.word,
        reading=vocab.reading,
        meaning=vocab.meaning,
        part_of_speech=vocab.part_of_speech,
        jlpt_level=vocab.jlpt_level,
        example_jp=vocab.example_jp,
        example_en=vocab.example_en,
    )
