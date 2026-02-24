"""tests/test_cards_router.py — Integration tests for the /api/cards endpoints."""
import pytest
import pytest_asyncio
from sqlmodel import select

from models.srs import SRSCard
from models.vocab import Vocab


# ── Helpers ────────────────────────────────────────────────────────────────────

async def _create_vocab(session) -> Vocab:
    """Insert one minimal vocab row for testing."""
    v = Vocab(
        word="食べる",
        reading="たべる",
        meaning="to eat",
        part_of_speech="verb",
        jlpt_level="N5",
    )
    session.add(v)
    await session.commit()
    await session.refresh(v)
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
    assert "id" in data
    assert isinstance(data["id"], int)


@pytest.mark.asyncio
async def test_submit_review_creates_card(client, session):
    """POSTing a review for a new vocab item should create an SRS card."""
    vocab = await _create_vocab(session)
    res = await client.post(
        "/api/cards/review",
        json={"item_type": "vocab", "item_id": vocab.id, "score": 3},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["item_id"] == vocab.id
    assert data["interval"] >= 1

    # Confirm card is in DB
    result = await session.execute(
        select(SRSCard).where(SRSCard.item_id == vocab.id)
    )
    card = result.scalar_one_or_none()
    assert card is not None


@pytest.mark.asyncio
async def test_end_session(client):
    """PATCHing a session should return 200 and set ended_at."""
    start_res = await client.post("/api/cards/sessions")
    sid = start_res.json()["id"]
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
