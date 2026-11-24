"""routers/kanji.py — Kanji browse and detail endpoints."""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from database.db import get_session
from models.kanji import Kanji, KanjiPage, KanjiResponse
from models.vocab import JLPTLevel

router = APIRouter(prefix="/api/kanji", tags=["kanji"])

PAGE_SIZE = 50

# Maps JLPT level to sort order (N5=5, N4=4, ..., N1=1)
JLPT_LEVEL_ORDER = case(
    (Kanji.jlpt_level == "N5", 5),
    (Kanji.jlpt_level == "N4", 4),
    (Kanji.jlpt_level == "N3", 3),
    (Kanji.jlpt_level == "N2", 2),
    (Kanji.jlpt_level == "N1", 1),
    else_=0,
)


@router.get("", response_model=KanjiPage)
async def list_kanji(
    level: Optional[JLPTLevel] = Query(None),
    search: Optional[str] = Query(None, description="Search in character, readings, or meaning"),
    page: int = Query(1, ge=1),
    limit: int = Query(PAGE_SIZE, ge=1, le=200),
    db: AsyncSession = Depends(get_session),
) -> KanjiPage:
    stmt = select(Kanji)
    if level:
        stmt = stmt.where(Kanji.jlpt_level == level)
    if search:
        like = f"%{search}%"
        stmt = stmt.where(
            Kanji.character.ilike(like) | Kanji.example_word.ilike(like)
        )

    count_stmt = select(func.count()).select_from(stmt.subquery())
    total: int = (await db.execute(count_stmt)).scalar_one()

    stmt = stmt.order_by(JLPT_LEVEL_ORDER.desc(), Kanji.freq_rank.asc().nullslast(), Kanji.id)
    stmt = stmt.offset((page - 1) * limit).limit(limit)
    rows = (await db.execute(stmt)).scalars().all()

    items = [_to_response(k) for k in rows]
    return KanjiPage(items=items, total=total, page=page, page_size=limit)


@router.get("/{character}", response_model=KanjiResponse)
async def get_kanji_by_character(
    character: str,
    db: AsyncSession = Depends(get_session),
) -> KanjiResponse:
    if len(character) != 1:
        raise HTTPException(
            status_code=400,
            detail="'character' must be a single kanji character (e.g. 日).",
        )
    result = await db.execute(select(Kanji).where(Kanji.character == character))
    kanji = result.scalar_one_or_none()
    if kanji is None:
        raise HTTPException(status_code=404, detail=f"Kanji '{character}' not found.")
    return _to_response(kanji)


def _to_response(k: Kanji) -> KanjiResponse:
    return KanjiResponse(
        id=k.id,
        character=k.character,
        on_yomi=k.on_yomi or [],
        kun_yomi=k.kun_yomi or [],
        meaning=k.meaning or [],
        stroke_count=k.stroke_count,
        jlpt_level=k.jlpt_level,
        freq_rank=k.freq_rank,
        example_word=k.example_word,
        example_sentence=k.example_sentence,
    )
