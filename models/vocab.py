"""models/vocab.py — Vocabulary table and JLPT level enum."""
from enum import Enum
from typing import Optional

from sqlmodel import Field, SQLModel


class JLPTLevel(str, Enum):
    N5 = "N5"
    N4 = "N4"
    N3 = "N3"
    N2 = "N2"
    N1 = "N1"


class Vocab(SQLModel, table=True):
    """One Japanese vocabulary item seeded from JMdict."""

    __tablename__ = "vocab"

    id: Optional[int] = Field(default=None, primary_key=True)
    word: str = Field(index=True)           # Surface form, e.g. 食べる
    reading: str                             # Hiragana/katakana, e.g. たべる
    meaning: str                             # Primary English gloss
    part_of_speech: str = Field(default="") # verb / noun / adjective / adverb / etc.
    jlpt_level: JLPTLevel = Field(index=True)
    example_jp: Optional[str] = None        # Example sentence (Japanese)
    example_en: Optional[str] = None        # Example sentence (English)


# ─── Response / request Pydantic models ────────────────────────────────────────

class SRSCardSummary(SQLModel):
    ease_factor: float
    interval_days: int
    reps: int
    due_date: str  # ISO date string


class VocabResponse(SQLModel):
    id: int
    word: str
    reading: str
    meaning: str
    part_of_speech: str
    jlpt_level: str
    example_jp: Optional[str]
    example_en: Optional[str]
    srs_state: Optional[SRSCardSummary] = None


class VocabPage(SQLModel):
    items: list[VocabResponse]
    total: int
    page: int
    page_size: int
