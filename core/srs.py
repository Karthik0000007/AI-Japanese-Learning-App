"""
core/srs.py — SM-2 Spaced-Repetition algorithm.

This module is intentionally free of HTTP or router dependencies so it can
be tested in complete isolation (see tests/test_srs.py).

SM-2 reference:
  Wozniak P.A. (1990) "Optimization of learning" — SuperMemo 2 algorithm.
  https://www.supermemo.com/en/blog/application-of-a-computer-to-improve-the-results-obtained-in-working-with-the-supermemo-method

Grade scale used by this app (UI shows Again / Hard / Good / Easy):
  0 = again / blackout     — complete failure
  2 = hard                 — recalled with great effort
  3 = good  (default)      — recalled normally
  5 = easy                 — recalled instantly
"""
from __future__ import annotations

import json
import math
from datetime import date, datetime, timedelta
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from models.srs import ItemType, ReviewLog, SRSCard, StudySession
from models.vocab import JLPTLevel

EASE_FLOOR: float = 1.3
MATURE_THRESHOLD: int = 21  # interval_days >= this → "mature"


# ─── Public API ───────────────────────────────────────────────────────────────

def sm2_review(card: SRSCard, grade: int) -> SRSCard:
    """
    Apply one SM-2 review cycle to *card* in-place and return it.

    The caller is responsible for persisting the mutated card to the DB.

    Args:
        card:  The SRSCard object (already loaded from the DB).
        grade: Integer 0–5 per the SM-2 scale.

    Returns:
        The same SRSCard object with updated ease_factor, interval_days,
        reps, due_date, and last_reviewed.
    """
    assert 0 <= grade <= 5, f"grade must be 0–5, got {grade}"

    # 1. Update ease factor
    delta = 0.1 - (5 - grade) * (0.08 + (5 - grade) * 0.02)
    new_ease = max(EASE_FLOOR, card.ease_factor + delta)

    # 2. Determine new interval
    if grade < 3:
        # Failure — reset to learning
        new_interval = 1
        new_reps = 0
    elif card.reps == 0:
        new_interval = 1
        new_reps = 1
    elif card.reps == 1:
        new_interval = 6
        new_reps = 2
    else:
        new_interval = max(1, math.ceil(card.interval_days * new_ease))
        new_reps = card.reps + 1

    # 3. Mutate card
    card.ease_factor = round(new_ease, 4)
    card.interval_days = new_interval
    card.reps = new_reps
    card.due_date = date.today() + timedelta(days=new_interval)
    card.last_reviewed = datetime.utcnow()

    return card


async def get_due_cards(
    session: AsyncSession,
    level: JLPTLevel,
    item_type: ItemType,
    limit: int = 20,
) -> list[SRSCard]:
    """Return cards due today (or overdue) for the given JLPT level and type."""
    if item_type == ItemType.vocab:
        from models.vocab import Vocab  # local import avoids circular
        stmt = (
            select(SRSCard)
            .join(Vocab, (SRSCard.item_id == Vocab.id))
            .where(SRSCard.item_type == ItemType.vocab)
            .where(Vocab.jlpt_level == level)
            .where(SRSCard.due_date <= date.today())
            .order_by(SRSCard.due_date.asc())
            .limit(limit)
        )
    else:
        from models.kanji import Kanji
        stmt = (
            select(SRSCard)
            .join(Kanji, (SRSCard.item_id == Kanji.id))
            .where(SRSCard.item_type == ItemType.kanji)
            .where(Kanji.jlpt_level == level)
            .where(SRSCard.due_date <= date.today())
            .order_by(SRSCard.due_date.asc())
            .limit(limit)
        )

    result = await session.execute(stmt)
    return list(result.scalars().all())


async def get_new_items(
    session: AsyncSession,
    level: JLPTLevel,
    item_type: ItemType,
    limit: int = 20,
) -> list:
    """
    Return vocab/kanji items that have no SRSCard row yet.
    Respects the new_cards_per_day cap stored in the meta table.
    """
    from models.meta import Meta

    # Read the daily cap
    meta_result = await session.execute(
        select(Meta).where(Meta.key == "new_cards_per_day")
    )
    meta_row = meta_result.scalar_one_or_none()
    cap = int(meta_row.value) if meta_row else 20

    # Count cards already introduced today
    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    count_result = await session.execute(
        select(func.count()).select_from(SRSCard).where(
            SRSCard.created_at >= today_start
        )
    )
    created_today = count_result.scalar_one()
    effective_limit = min(limit, max(0, cap - created_today))

    if effective_limit == 0:
        return []

    if item_type == ItemType.vocab:
        from models.vocab import Vocab
        from sqlalchemy import exists

        stmt = (
            select(Vocab)
            .where(Vocab.jlpt_level == level)
            .where(
                ~exists().where(
                    (SRSCard.item_id == Vocab.id) & (SRSCard.item_type == "vocab")
                )
            )
            .order_by(Vocab.id.asc())
            .limit(effective_limit)
        )
    else:
        from models.kanji import Kanji
        from sqlalchemy import exists

        stmt = (
            select(Kanji)
            .where(Kanji.jlpt_level == level)
            .where(
                ~exists().where(
                    (SRSCard.item_id == Kanji.id) & (SRSCard.item_type == "kanji")
                )
            )
            .order_by(Kanji.id.asc())
            .limit(effective_limit)
        )

    result = await session.execute(stmt)
    return list(result.scalars().all())


async def create_card(
    session: AsyncSession,
    item_type: ItemType,
    item_id: int,
) -> SRSCard:
    """Create (but do not flush) an SRSCard for an unseen item."""
    card = SRSCard(
        item_type=item_type,
        item_id=item_id,
        ease_factor=2.5,
        interval_days=1,
        reps=0,
        due_date=date.today(),
    )
    session.add(card)
    await session.flush()  # Populate card.id without committing
    return card


async def get_card(
    session: AsyncSession,
    card_id: int,
) -> Optional[SRSCard]:
    result = await session.execute(
        select(SRSCard).where(SRSCard.id == card_id)
    )
    return result.scalar_one_or_none()


async def write_review_log(
    session: AsyncSession,
    card_id: int,
    grade: int,
    session_id: Optional[int] = None,
) -> ReviewLog:
    log = ReviewLog(card_id=card_id, grade=grade, session_id=session_id)
    session.add(log)
    await session.flush()
    return log


async def open_session(db: AsyncSession) -> StudySession:
    ss = StudySession()
    db.add(ss)
    await db.flush()
    return ss


async def close_session(db: AsyncSession, session_id: int) -> None:
    result = await db.execute(
        select(StudySession).where(StudySession.id == session_id)
    )
    ss = result.scalar_one_or_none()
    if ss and ss.ended_at is None:
        ss.ended_at = datetime.utcnow()


async def get_level_stats(
    db: AsyncSession,
    level: JLPTLevel,
) -> dict:
    """
    Return a dict with new / young / mature / due_today / total counts
    for a given JLPT level across both vocab and kanji.
    """
    from models.vocab import Vocab
    from models.kanji import Kanji
    from sqlalchemy import and_, or_

    # Total vocab + kanji at this level
    vocab_total = (await db.execute(
        select(func.count()).select_from(Vocab).where(Vocab.jlpt_level == level)
    )).scalar_one()
    kanji_total = (await db.execute(
        select(func.count()).select_from(Kanji).where(Kanji.jlpt_level == level)
    )).scalar_one()
    total = vocab_total + kanji_total

    # Cards that exist for this level
    vocab_cards = (await db.execute(
        select(func.count()).select_from(SRSCard)
        .join(Vocab, and_(SRSCard.item_id == Vocab.id, SRSCard.item_type == "vocab"))
        .where(Vocab.jlpt_level == level)
    )).scalar_one()

    kanji_cards = (await db.execute(
        select(func.count()).select_from(SRSCard)
        .join(Kanji, and_(SRSCard.item_id == Kanji.id, SRSCard.item_type == "kanji"))
        .where(Kanji.jlpt_level == level)
    )).scalar_one()

    seen = vocab_cards + kanji_cards
    new_count = total - seen

    # Young / mature breakdown
    young = (await db.execute(
        select(func.count()).select_from(SRSCard)
        .join(Vocab, and_(SRSCard.item_id == Vocab.id, SRSCard.item_type == "vocab"), isouter=True)
        .join(Kanji, and_(SRSCard.item_id == Kanji.id, SRSCard.item_type == "kanji"), isouter=True)
        .where(or_(Vocab.jlpt_level == level, Kanji.jlpt_level == level))
        .where(SRSCard.interval_days < MATURE_THRESHOLD)
    )).scalar_one()

    mature = seen - young

    due = (await db.execute(
        select(func.count()).select_from(SRSCard)
        .join(Vocab, and_(SRSCard.item_id == Vocab.id, SRSCard.item_type == "vocab"), isouter=True)
        .join(Kanji, and_(SRSCard.item_id == Kanji.id, SRSCard.item_type == "kanji"), isouter=True)
        .where(or_(Vocab.jlpt_level == level, Kanji.jlpt_level == level))
        .where(SRSCard.due_date <= date.today())
    )).scalar_one()

    return {
        "level": level.value if isinstance(level, JLPTLevel) else str(level),
        "new": new_count,
        "young": young,
        "mature": mature,
        "due_today": due,
        "total": total,
    }
