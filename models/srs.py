"""models/srs.py — SRSCard, ReviewLog, and StudySession tables."""
from datetime import date, datetime
from enum import Enum
from typing import Optional

from sqlmodel import Field, SQLModel


class ItemType(str, Enum):
    vocab = "vocab"
    kanji = "kanji"


class SRSCard(SQLModel, table=True):
    """
    Per-item memory record.  One row per (item_type, item_id) pair.
    Created the first time a learner is introduced to an item.
    """

    __tablename__ = "srs_cards"

    id: Optional[int] = Field(default=None, primary_key=True)
    item_type: ItemType
    item_id: int = Field(index=True)

    ease_factor: float = Field(default=2.5)    # Floor: 1.3
    interval_days: int = Field(default=1)
    reps: int = Field(default=0)               # 0 = brand-new card
    due_date: date = Field(index=True)
    last_reviewed: Optional[datetime] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


class ReviewLog(SQLModel, table=True):
    """
    Append-only audit log.  Every single review action is recorded here.
    Never updated after creation.
    """

    __tablename__ = "review_log"

    id: Optional[int] = Field(default=None, primary_key=True)
    session_id: Optional[int] = Field(default=None, foreign_key="study_sessions.id")
    card_id: int = Field(foreign_key="srs_cards.id", index=True)
    grade: int                                  # 0–5 (SM-2 grade scale)
    reviewed_at: datetime = Field(default_factory=datetime.utcnow, index=True)


class StudySession(SQLModel, table=True):
    """A contiguous block of card reviews opened/closed by the frontend."""

    __tablename__ = "study_sessions"

    id: Optional[int] = Field(default=None, primary_key=True)
    started_at: datetime = Field(default_factory=datetime.utcnow)
    ended_at: Optional[datetime] = None
    cards_reviewed: int = Field(default=0)
    correct: int = Field(default=0)     # grade >= 3
    incorrect: int = Field(default=0)   # grade <= 2


# ─── Request / response Pydantic shapes ────────────────────────────────────────

class ReviewRequest(SQLModel):
    card_id: int
    grade: int = Field(ge=0, le=5)


class ReviewResponse(SQLModel):
    card_id: int
    ease_factor: float
    interval_days: int
    reps: int
    next_due: str           # ISO date
    session_correct: int
    session_incorrect: int


class SessionStartResponse(SQLModel):
    session_id: int
    started_at: str


class LevelStats(SQLModel):
    level: str
    new: int        # No srs_cards row yet
    young: int      # interval_days < 21
    mature: int     # interval_days >= 21
    due_today: int
    total: int


class ForecastDay(SQLModel):
    date: str
    count: int


class ProgressResponse(SQLModel):
    streak_days: int
    level_stats: list[LevelStats]
    weekly_forecast: list[ForecastDay]
    all_time_accuracy: float
    total_reviews: int
