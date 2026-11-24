"""
tools/seed.py — Insert vocab and kanji into PostgreSQL.

Two data sources:
  --sample   data/sample_n5.json: ~170 N5 words and 80 N5 kanji, committed to
             the repo, so the app is usable with no downloads.
  (default)  data/jmdict_parsed.json + data/kanjidic_parsed.json, the full
             dictionaries produced by tools/fetch_jmdict.py / fetch_kanjidic.py.

Idempotent: running it again inserts nothing new.
  • vocab is unique on (word, reading) and kanji on character, and every
    insert uses ON CONFLICT DO NOTHING.
  • meta defaults are only inserted when missing, so settings the user has
    changed are never overwritten.

Run: python -m tools.seed --sample
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path
from typing import Any

# Allow `python tools/seed.py` as well as `python -m tools.seed`
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy.dialects.postgresql import insert as pg_insert

from config import settings
from database.db import engine
from models.kanji import Kanji
from models.meta import META_DEFAULTS, Meta
from models.vocab import Vocab

DATA_DIR = Path(__file__).parent.parent / "data"
JMDICT_JSON = DATA_DIR / "jmdict_parsed.json"
KANJIDIC_JSON = DATA_DIR / "kanjidic_parsed.json"
SAMPLE_JSON = DATA_DIR / "sample_n5.json"

BATCH_SIZE = 500  # Rows per INSERT statement


def load_json(path: Path, hint: str) -> list[dict[str, Any]] | None:
    if not path.exists():
        print(f"[seed] {path} not found — {hint}")
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def load_sample() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    with open(SAMPLE_JSON, encoding="utf-8") as f:
        sample = json.load(f)
    return sample["vocab"], sample["kanji"]


async def seed_vocab(conn, entries: list[dict[str, Any]]) -> int:
    print(f"[seed] Inserting {len(entries)} vocab entries...")
    inserted = 0
    for i in range(0, len(entries), BATCH_SIZE):
        stmt = (
            pg_insert(Vocab)
            .values(entries[i : i + BATCH_SIZE])
            .on_conflict_do_nothing(index_elements=["word", "reading"])
        )
        result = await conn.execute(stmt)
        inserted += result.rowcount
    print(f"[seed] Vocab: {inserted} new rows inserted.")
    return inserted


async def seed_kanji(conn, entries: list[dict[str, Any]]) -> int:
    print(f"[seed] Inserting {len(entries)} kanji entries...")
    inserted = 0
    for i in range(0, len(entries), BATCH_SIZE):
        stmt = (
            pg_insert(Kanji)
            .values(entries[i : i + BATCH_SIZE])
            .on_conflict_do_nothing(index_elements=["character"])
        )
        result = await conn.execute(stmt)
        inserted += result.rowcount
    print(f"[seed] Kanji: {inserted} new rows inserted.")
    return inserted


async def seed_meta(conn) -> None:
    """Insert default settings that are missing; never overwrite the user's values."""
    for key, value in META_DEFAULTS.items():
        stmt = pg_insert(Meta).values(key=key, value=value).on_conflict_do_nothing(index_elements=["key"])
        await conn.execute(stmt)
    print(f"[seed] Meta: {len(META_DEFAULTS)} defaults ensured.")


async def main(sample: bool = False) -> None:
    print(f"[seed] Connecting to {settings.database_url.split('@')[-1]}...")
    if sample:
        print(f"[seed] Using bundled sample {SAMPLE_JSON.name}")
        vocab, kanji = load_sample()
    else:
        vocab = load_json(JMDICT_JSON, "run tools/fetch_jmdict.py first, or use --sample.")
        kanji = load_json(KANJIDIC_JSON, "run tools/fetch_kanjidic.py first, or use --sample.")

    async with engine.begin() as conn:
        if vocab:
            await seed_vocab(conn, vocab)
        if kanji:
            await seed_kanji(conn, kanji)
        await seed_meta(conn)
    await engine.dispose()
    print("[seed] Done!")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Seed the database with vocab and kanji.")
    parser.add_argument(
        "--sample",
        action="store_true",
        help="load the bundled N5 sample (data/sample_n5.json) instead of the full dictionaries",
    )
    asyncio.run(main(sample=parser.parse_args().sample))
