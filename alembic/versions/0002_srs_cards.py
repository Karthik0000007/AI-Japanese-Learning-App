"""SRS cards table.

Revision ID: 0002
Revises: 0001
Create Date: 2026-02-24
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "srs_cards",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "item_type",
            sa.Enum("vocab", "kanji", name="itemtype"),
            nullable=False,
        ),
        sa.Column("item_id", sa.Integer(), nullable=False),
        sa.Column("ease_factor", sa.Float(), nullable=False, server_default="2.5"),
        sa.Column("interval_days", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("reps", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("due_date", sa.Date(), nullable=False),
        sa.Column("last_reviewed", sa.DateTime(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    # Enforce one card per item — guaranteed by the schema
    op.create_unique_constraint(
        "uq_srs_cards_item", "srs_cards", ["item_type", "item_id"]
    )
    op.create_index("ix_srs_cards_item_id", "srs_cards", ["item_id"])
    op.create_index("ix_srs_cards_due_date", "srs_cards", ["due_date"])


def downgrade() -> None:
    op.drop_table("srs_cards")
    op.execute("DROP TYPE IF EXISTS itemtype")
