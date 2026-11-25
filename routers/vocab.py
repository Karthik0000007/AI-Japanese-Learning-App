"""routers/vocab.py — Vocabulary browse and search endpoints."""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from database.db import get_session
from models.vocab import JLPTLevel, Vocab, VocabPage, VocabResponse

router = APIRouter(prefix="/api/vocab", tags=["vocab"])

PAGE_SIZE = 50

# Maps JLPT level to sort order (N5=5, N4=4, ..., N1=1)
JLPT_LEVEL_ORDER = case(
    (Vocab.jlpt_level == "N5", 5),
    (Vocab.jlpt_level == "N4", 4),
    (Vocab.jlpt_level == "N3", 3),
    (Vocab.jlpt_level == "N2", 2),
    (Vocab.jlpt_level == "N1", 1),
    else_=0,
)


@router.get("", response_model=VocabPage)
async def list_vocab(
    level: Optional[JLPTLevel] = Query(None),
    search: Optional[str] = Query(None, description="Search in word, reading, or meaning"),
    page: int = Query(1, ge=1),
    limit: int = Query(PAGE_SIZE, ge=1, le=200),
    db: AsyncSession = Depends(get_session),
) -> VocabPage:
    stmt = select(Vocab)
    if level:
        stmt = stmt.where(Vocab.jlpt_level == level)
    if search:
        like = f"%{search}%"
        stmt = stmt.where(
            Vocab.word.ilike(like) | Vocab.reading.ilike(like) | Vocab.meaning.ilike(like)
        )

    # Count total before pagination
    count_stmt = select(func.count()).select_from(stmt.subquery())
    total: int = (await db.execute(count_stmt)).scalar_one()

    stmt = stmt.order_by(JLPT_LEVEL_ORDER.desc(), Vocab.id)
    stmt = stmt.offset((page - 1) * limit).limit(limit)
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
    return VocabPage(items=items, total=total, page=page, page_size=limit)


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
