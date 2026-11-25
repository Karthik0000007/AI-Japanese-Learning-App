"""tests/test_seed.py — The bundled sample is valid and seeding is idempotent."""
import pytest
from sqlalchemy import func, select, update

from models.kanji import Kanji
from models.meta import Meta
from models.vocab import Vocab
from tools.seed import load_sample, seed_kanji, seed_meta, seed_vocab


async def _count(conn, model) -> int:
    return (await conn.execute(select(func.count()).select_from(model))).scalar_one()


def test_sample_file_has_n5_vocab_and_kanji():
    """The bundled sample holds about 150 N5 words and 80 N5 kanji, with no duplicates."""
    vocab, kanji = load_sample()

    assert 140 <= len(vocab) <= 200
    assert len(kanji) == 80
    assert {v["jlpt_level"] for v in vocab} == {"N5"}
    assert {k["jlpt_level"] for k in kanji} == {"N5"}
    assert len({(v["word"], v["reading"]) for v in vocab}) == len(vocab)
    assert len({k["character"] for k in kanji}) == len(kanji)
    assert all(v["meaning"] for v in vocab)
    assert all(k["meaning"] and (k["on_yomi"] or k["kun_yomi"]) for k in kanji)


@pytest.mark.asyncio
async def test_seeding_twice_creates_no_duplicates(db_conn):
    """Seeding the sample a second time inserts zero rows and leaves the counts unchanged."""
    vocab, kanji = load_sample()

    assert await seed_vocab(db_conn, vocab) == len(vocab)
    assert await seed_kanji(db_conn, kanji) == len(kanji)
    await seed_meta(db_conn)
    counts = [await _count(db_conn, m) for m in (Vocab, Kanji, Meta)]

    assert await seed_vocab(db_conn, vocab) == 0
    assert await seed_kanji(db_conn, kanji) == 0
    await seed_meta(db_conn)
    assert [await _count(db_conn, m) for m in (Vocab, Kanji, Meta)] == counts


@pytest.mark.asyncio
async def test_seeding_keeps_user_settings(db_conn):
    """Re-seeding never overwrites a setting the user has changed."""
    await seed_meta(db_conn)
    await db_conn.execute(update(Meta).where(Meta.key == "new_cards_per_day").values(value="5"))

    await seed_meta(db_conn)

    value = (await db_conn.execute(select(Meta.value).where(Meta.key == "new_cards_per_day"))).scalar_one()
    assert value == "5"
