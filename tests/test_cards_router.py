"""tests/test_cards_router.py — Integration tests for the /api/cards endpoints."""
import pytest
from sqlmodel import select

from models.srs import ReviewLog, SRSCard
from models.vocab import Vocab

# ── Helpers ────────────────────────────────────────────────────────────────────

async def _create_vocab(session) -> Vocab:
    """Insert one minimal vocab row (flushed, not committed, so the test rollback removes it)."""
    v = Vocab(
        word="食べる",
        reading="たべる",
        meaning="to eat",
        part_of_speech="verb",
        jlpt_level="N5",
    )
    session.add(v)
    await session.flush()
    return v


# ── Tests ──────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_due_empty(client):
    """Due list should be empty for a fresh DB with no SRS cards."""
    res = await client.get("/api/cards/due")
    assert res.status_code == 200
    assert isinstance(res.json(), list)


@pytest.mark.asyncio
async def test_get_new_returns_vocab(client, session):
    """New-cards endpoint should surface unseeded vocab items."""
    await _create_vocab(session)
    res = await client.get("/api/cards/new")
    assert res.status_code == 200
    data = res.json()
    assert isinstance(data, list)
    # vocab row should appear as a new card candidate
    assert any(c["item_type"] == "vocab" for c in data)


@pytest.mark.asyncio
async def test_start_session(client):
    """Starting a session should return an integer session id."""
    res = await client.post("/api/cards/sessions")
    assert res.status_code == 200
    data = res.json()
    assert isinstance(data["session_id"], int)


@pytest.mark.asyncio
async def test_submit_review_updates_card(client, session):
    """Introducing a word creates its SRS card; grading it 'good' updates the card and logs the review."""
    vocab = await _create_vocab(session)
    new_cards = (await client.get("/api/cards/new")).json()
    card_id = next(c["card_id"] for c in new_cards if c["item_id"] == vocab.id)

    res = await client.post("/api/cards/review", json={"card_id": card_id, "grade": 3})
    assert res.status_code == 200
    data = res.json()
    assert data["card_id"] == card_id
    assert data["reps"] == 1
    assert data["interval_days"] == 1

    card = (await session.execute(select(SRSCard).where(SRSCard.id == card_id))).scalar_one()
    assert card.reps == 1
    logs = (await session.execute(select(ReviewLog).where(ReviewLog.card_id == card_id))).scalars().all()
    assert len(logs) == 1


@pytest.mark.asyncio
async def test_submit_review_unknown_card_is_404(client):
    """Reviewing a card id that does not exist returns 404."""
    res = await client.post("/api/cards/review", json={"card_id": 999999, "grade": 3})
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_end_session(client):
    """PATCHing a session should return 200 and set ended_at."""
    start_res = await client.post("/api/cards/sessions")
    sid = start_res.json()["session_id"]
    end_res = await client.patch(f"/api/cards/sessions/{sid}")
    assert end_res.status_code == 200
    data = end_res.json()
    assert data["ended_at"] is not None


@pytest.mark.asyncio
async def test_health_endpoint(client):
    """Health check should always return 200 with a db key."""
    res = await client.get("/api/health")
    assert res.status_code == 200
    assert "db" in res.json()
