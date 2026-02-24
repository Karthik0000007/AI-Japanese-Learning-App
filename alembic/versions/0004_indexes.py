"""Performance indexes and GIN indexes for kanji reading search.

Revision ID: 0004
Revises: 0003
Create Date: 2026-02-24
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # SRS scheduling hot paths
    op.create_index("ix_srs_cards_ease_factor", "srs_cards", ["ease_factor"])

    # GIN indexes on kanji JSONB columns — enables fast containment queries
    op.create_index(
        "ix_kanji_on_yomi_gin",
        "kanji",
        ["on_yomi"],
        postgresql_using="gin",
    )
    op.create_index(
        "ix_kanji_kun_yomi_gin",
        "kanji",
        ["kun_yomi"],
        postgresql_using="gin",
    )

    # Full-text search support on vocab (future use)
    op.execute(
        """
        CREATE INDEX ix_vocab_word_trgm
        ON vocab USING gin (word gin_trgm_ops)
        """
        if False  # Skip: requires pg_trgm extension — enable manually if needed
        else "SELECT 1"
    )


def downgrade() -> None:
    op.drop_index("ix_srs_cards_ease_factor", table_name="srs_cards")
    op.drop_index("ix_kanji_on_yomi_gin", table_name="kanji")
    op.drop_index("ix_kanji_kun_yomi_gin", table_name="kanji")
