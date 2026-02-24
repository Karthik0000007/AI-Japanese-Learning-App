"""Initial schema — vocab and kanji tables.

Revision ID: 0001
Revises: —
Create Date: 2026-02-24
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "vocab",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("word", sa.String(), nullable=False),
        sa.Column("reading", sa.String(), nullable=False),
        sa.Column("meaning", sa.String(), nullable=False),
        sa.Column("part_of_speech", sa.String(), nullable=False, server_default=""),
        sa.Column(
            "jlpt_level",
            sa.Enum("N5", "N4", "N3", "N2", "N1", name="jlptlevel"),
            nullable=False,
        ),
        sa.Column("example_jp", sa.Text(), nullable=True),
        sa.Column("example_en", sa.Text(), nullable=True),
    )
    op.create_index("ix_vocab_word", "vocab", ["word"])
    op.create_index("ix_vocab_jlpt_level", "vocab", ["jlpt_level"])

    op.create_table(
        "kanji",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("character", sa.String(4), nullable=False, unique=True),
        sa.Column("on_yomi", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("kun_yomi", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("meaning", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("stroke_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "jlpt_level",
            sa.Enum("N5", "N4", "N3", "N2", "N1", name="jlptlevel"),
            nullable=True,
        ),
        sa.Column("freq_rank", sa.Integer(), nullable=True),
        sa.Column("example_word", sa.String(), nullable=True),
        sa.Column("example_sentence", sa.Text(), nullable=True),
    )
    op.create_index("ix_kanji_character", "kanji", ["character"], unique=True)
    op.create_index("ix_kanji_jlpt_level", "kanji", ["jlpt_level"])


def downgrade() -> None:
    op.drop_table("kanji")
    op.drop_table("vocab")
    op.execute("DROP TYPE IF EXISTS jlptlevel")
