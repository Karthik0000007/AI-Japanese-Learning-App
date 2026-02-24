"""Study sessions, review log, and meta tables.

Revision ID: 0003
Revises: 0002
Create Date: 2026-02-24
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_META_DEFAULTS = [
    ("jlpt_focus", '"N5"'),
    ("new_cards_per_day", "20"),
    ("db_version", '"jlpt-db-v1.0.0"'),
]


def upgrade() -> None:
    op.create_table(
        "study_sessions",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "started_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("ended_at", sa.DateTime(), nullable=True),
        sa.Column("cards_reviewed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("correct", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("incorrect", sa.Integer(), nullable=False, server_default="0"),
    )

    op.create_table(
        "review_log",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "session_id",
            sa.Integer(),
            sa.ForeignKey("study_sessions.id"),
            nullable=True,
        ),
        sa.Column(
            "card_id",
            sa.Integer(),
            sa.ForeignKey("srs_cards.id"),
            nullable=False,
        ),
        sa.Column("grade", sa.Integer(), nullable=False),
        sa.Column(
            "reviewed_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("ix_review_log_card_id", "review_log", ["card_id"])
    op.create_index("ix_review_log_reviewed_at", "review_log", ["reviewed_at"])

    op.create_table(
        "meta",
        sa.Column("key", sa.String(), primary_key=True),
        sa.Column("value", sa.Text(), nullable=False),
    )

    # Insert default configuration rows
    meta_table = sa.table(
        "meta",
        sa.column("key", sa.String),
        sa.column("value", sa.Text),
    )
    op.bulk_insert(meta_table, [{"key": k, "value": v} for k, v in _META_DEFAULTS])


def downgrade() -> None:
    op.drop_table("meta")
    op.drop_table("review_log")
    op.drop_table("study_sessions")
