"""
tools/seed.py — Insert parsed JMdict and KANJIDIC2 data into PostgreSQL.

Idempotent: uses ON CONFLICT DO NOTHING for vocab/kanji rows.
Meta rows are upserted so re-running is always safe.

Run: python tools/seed.py
"""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

# Allow importing project modules from the repo root
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import text
from sqlalchemy.dialects.postgresql import insert as pg_insert

from config import settings
from database.db import engine
from models.kanji import Kanji
from models.meta import META_DEFAULTS, Meta
from models.vocab import Vocab

DATA_DIR = Path(__file__).parent.parent / "data"
JMDICT_JSON = DATA_DIR / "jmdict_parsed.json"
KANJIDIC_JSON = DATA_DIR / "kanjidic_parsed.json"

BATCH_SIZE = 500  # Rows per INSERT statement


async def seed_vocab(conn) -> int:
    if not JMDICT_JSON.exists():
        print(f"[seed] {JMDICT_JSON} not found — run tools/fetch_jmdict.py first.")
        return 0

    with open(JMDICT_JSON, encoding="utf-8") as f:
        entries = json.load(f)

    print(f"[seed] Inserting {len(entries)} vocab entries…")
    inserted = 0
    for i in range(0, len(entries), BATCH_SIZE):
        batch = entries[i : i + BATCH_SIZE]
        stmt = (
            pg_insert(Vocab)
            .values(batch)
            .on_conflict_do_nothing()
        )
        result = await conn.execute(stmt)
        inserted += result.rowcount

    print(f"[seed] Vocab: {inserted} new rows inserted.")
    return inserted


async def seed_kanji(conn) -> int:
    if not KANJIDIC_JSON.exists():
        print(f"[seed] {KANJIDIC_JSON} not found — run tools/fetch_kanjidic.py first.")
        return 0

    with open(KANJIDIC_JSON, encoding="utf-8") as f:
        entries = json.load(f)

    print(f"[seed] Inserting {len(entries)} kanji entries…")
    inserted = 0
    for i in range(0, len(entries), BATCH_SIZE):
        batch = entries[i : i + BATCH_SIZE]
        stmt = (
            pg_insert(Kanji)
            .values(batch)
            .on_conflict_do_nothing(index_elements=["character"])
        )
        result = await conn.execute(stmt)
        inserted += result.rowcount

    print(f"[seed] Kanji: {inserted} new rows inserted.")
    return inserted


async def seed_meta(conn) -> None:
    for key, value in META_DEFAULTS.items():
        stmt = (
            pg_insert(Meta)
            .values(key=key, value=value)
            .on_conflict_do_update(
                index_elements=["key"],
                set_={"value": value},
            )
        )
        await conn.execute(stmt)
    print(f"[seed] Meta: {len(META_DEFAULTS)} default rows upserted.")


async def main() -> None:
    print(f"[seed] Connecting to {settings.database_url.split('@')[-1]}…")
    async with engine.begin() as conn:
        await seed_vocab(conn)
        await seed_kanji(conn)
        await seed_meta(conn)
    await engine.dispose()
    print("[seed] Done!")


if __name__ == "__main__":
    asyncio.run(main())
