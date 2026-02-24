"""models/meta.py — Flat key-value store for user configuration / app state."""
from sqlmodel import Field, SQLModel


class Meta(SQLModel, table=True):
    """
    Generic key-value table.  Values are stored as JSON-serialized strings.
    The seed script inserts sensible defaults; the /api/settings endpoints
    read and write this table at runtime.
    """

    __tablename__ = "meta"

    key: str = Field(primary_key=True)
    value: str  # JSON-encoded; parse in application layer


# Default meta rows written by tools/seed.py (and migration 0003)
META_DEFAULTS: dict[str, str] = {
    "jlpt_focus": '"N5"',
    "new_cards_per_day": "20",
    "db_version": '"jlpt-db-v1.0.0"',
}
