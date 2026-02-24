"""models/kanji.py — Kanji table backed by KANJIDIC2."""
from typing import Any, Optional

from sqlalchemy import Column
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, SQLModel

from .vocab import JLPTLevel, SRSCardSummary


class Kanji(SQLModel, table=True):
    """One Jōyō kanji entry sourced from KANJIDIC2."""

    __tablename__ = "kanji"

    id: Optional[int] = Field(default=None, primary_key=True)
    character: str = Field(unique=True, index=True)   # Single kanji, e.g. 日

    # JSONB columns — store multi-value arrays natively in PostgreSQL
    on_yomi: list[Any] = Field(
        default_factory=list,
        sa_column=Column(JSONB, nullable=False, server_default="[]"),
    )
    kun_yomi: list[Any] = Field(
        default_factory=list,
        sa_column=Column(JSONB, nullable=False, server_default="[]"),
    )
    meaning: list[Any] = Field(
        default_factory=list,
        sa_column=Column(JSONB, nullable=False, server_default="[]"),
    )

    stroke_count: int = Field(default=0)
    jlpt_level: Optional[JLPTLevel] = Field(default=None, index=True)
    freq_rank: Optional[int] = None      # Newspaper frequency rank

    example_word: Optional[str] = None          # e.g. 日本語
    example_sentence: Optional[str] = None      # Full example sentence


# ─── Response models ───────────────────────────────────────────────────────────

class KanjiResponse(SQLModel):
    id: int
    character: str
    on_yomi: list[str]
    kun_yomi: list[str]
    meaning: list[str]
    stroke_count: int
    jlpt_level: Optional[str]
    freq_rank: Optional[int]
    example_word: Optional[str]
    example_sentence: Optional[str]
    srs_state: Optional[SRSCardSummary] = None


class KanjiPage(SQLModel):
    items: list[KanjiResponse]
    total: int
    page: int
    page_size: int
