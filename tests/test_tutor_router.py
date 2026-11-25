"""tests/test_tutor_router.py — The tutor fails fast and clearly when Ollama is not available."""
import time

import pytest
from httpx import ASGITransport, AsyncClient

from config import settings
from core.tutor import check_ollama_health
from database.db import get_session
from main import app


async def _no_db_session():
    """The 503 path must return before touching the database."""
    yield None


@pytest.mark.asyncio
async def test_tutor_returns_503_when_ollama_is_down(monkeypatch):
    """With Ollama unavailable, /api/tutor/chat answers 503 JSON instead of a 500 or a hang."""

    async def ollama_down():
        return False

    monkeypatch.setattr("routers.tutor.check_ollama_health", ollama_down)
    app.dependency_overrides[get_session] = _no_db_session
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            res = await c.post("/api/tutor/chat", json={"message": "こんにちは"})
    finally:
        app.dependency_overrides.clear()

    assert res.status_code == 503
    assert res.headers["content-type"].startswith("application/json")
    assert settings.ollama_model in res.json()["detail"]


@pytest.mark.asyncio
async def test_ollama_health_check_is_fast_when_nothing_listens(monkeypatch):
    """The health check returns False within its timeout when Ollama is not running."""
    monkeypatch.setattr(settings, "ollama_base_url", "http://127.0.0.1:9")  # nothing listens here

    start = time.monotonic()
    ok = await check_ollama_health()

    assert ok is False
    assert time.monotonic() - start < 6
