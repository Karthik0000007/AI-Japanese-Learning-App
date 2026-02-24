"""routers/progress.py — Study statistics and review forecast."""
from datetime import date, timedelta

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from database.db import get_session
from models.srs import (
    ForecastDay,
    LevelStats,
    ProgressResponse,
    ReviewLog,
    SRSCard,
    StudySession,
)
from models.vocab import JLPTLevel

import core.srs as srs_engine

router = APIRouter(prefix="/api/progress", tags=["progress"])


@router.get("", response_model=ProgressResponse)
async def get_progress(db: AsyncSession = Depends(get_session)) -> ProgressResponse:
    # ── Per-level stats ───────────────────────────────────────────────────────
    level_stats: list[LevelStats] = []
    for level in JLPTLevel:
        d = await srs_engine.get_level_stats(db, level)
        level_stats.append(LevelStats(**d))

    # ── All-time accuracy ─────────────────────────────────────────────────────
    total_result = await db.execute(select(func.count()).select_from(ReviewLog))
    total_reviews: int = total_result.scalar_one()

    correct_result = await db.execute(
        select(func.count()).select_from(ReviewLog).where(ReviewLog.grade >= 3)
    )
    correct_reviews: int = correct_result.scalar_one()
    accuracy = correct_reviews / total_reviews if total_reviews > 0 else 0.0

    # ── 7-day forecast ────────────────────────────────────────────────────────
    forecast: list[ForecastDay] = []
    today = date.today()
    for i in range(7):
        day = today + timedelta(days=i)
        cnt_result = await db.execute(
            select(func.count()).select_from(SRSCard).where(SRSCard.due_date == day)
        )
        cnt: int = cnt_result.scalar_one()
        forecast.append(ForecastDay(date=day.isoformat(), count=cnt))

    # ── Streak ────────────────────────────────────────────────────────────────
    streak = await _calc_streak(db)

    return ProgressResponse(
        streak_days=streak,
        level_stats=level_stats,
        weekly_forecast=forecast,
        all_time_accuracy=round(accuracy, 4),
        total_reviews=total_reviews,
    )


async def _calc_streak(db: AsyncSession) -> int:
    """Count consecutive calendar days (ending today) with at least one review."""
    result = await db.execute(
        select(func.date(ReviewLog.reviewed_at).label("day"))
        .group_by(func.date(ReviewLog.reviewed_at))
        .order_by(func.date(ReviewLog.reviewed_at).desc())
    )
    review_days = {row[0] for row in result.all()}

    streak = 0
    current = date.today()
    while current in review_days:
        streak += 1
        current -= timedelta(days=1)
    return streak
