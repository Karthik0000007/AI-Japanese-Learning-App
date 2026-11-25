"""Unique (word, reading) on vocab so seeding is idempotent.

Before this migration, re-running tools/seed.py inserted every word again,
because vocab had no unique key for ON CONFLICT DO NOTHING to act on.

Upgrade:
  1. For each (word, reading) keep the row with the lowest id.
  2. Re-point SRS cards from duplicate rows to the kept row. If that would give
     one word two cards, keep a single card (the one already on the kept row,
     otherwise the oldest) and delete the others with their review logs.
  3. Delete the duplicate vocab rows and add the unique constraint.

Revision ID: 0005
Revises: 0004
Create Date: 2026-11-24
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0005"
down_revision: Union[str, None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # dup_id -> keep_id for every duplicate vocab row
    op.execute(
        """
        CREATE TEMP TABLE vocab_dupes AS
        SELECT id AS dup_id, keep_id
        FROM (
            SELECT id, MIN(id) OVER (PARTITION BY word, reading) AS keep_id
            FROM vocab
        ) t
        WHERE id <> keep_id
        """
    )

    # Vocab cards that would collide once re-pointed: all but one per target word
    op.execute(
        """
        CREATE TEMP TABLE losing_cards AS
        SELECT card_id FROM (
            SELECT c.id AS card_id,
                   ROW_NUMBER() OVER (
                       PARTITION BY COALESCE(d.keep_id, c.item_id)
                       ORDER BY (d.dup_id IS NULL) DESC, c.id
                   ) AS rn
            FROM srs_cards c
            LEFT JOIN vocab_dupes d ON d.dup_id = c.item_id
            WHERE c.item_type = 'vocab'
              AND COALESCE(d.keep_id, c.item_id) IN (SELECT keep_id FROM vocab_dupes)
        ) ranked
        WHERE rn > 1
        """
    )
    op.execute("DELETE FROM review_log WHERE card_id IN (SELECT card_id FROM losing_cards)")
    op.execute("DELETE FROM srs_cards WHERE id IN (SELECT card_id FROM losing_cards)")

    op.execute(
        """
        UPDATE srs_cards c SET item_id = d.keep_id
        FROM vocab_dupes d
        WHERE c.item_type = 'vocab' AND c.item_id = d.dup_id
        """
    )
    op.execute("DELETE FROM vocab v USING vocab_dupes d WHERE v.id = d.dup_id")
    op.execute("DROP TABLE losing_cards")
    op.execute("DROP TABLE vocab_dupes")

    op.create_unique_constraint("uq_vocab_word_reading", "vocab", ["word", "reading"])


def downgrade() -> None:
    op.drop_constraint("uq_vocab_word_reading", "vocab", type_="unique")
