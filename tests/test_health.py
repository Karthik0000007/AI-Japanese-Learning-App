"""tests/test_health.py — /api/health reports every optional service separately."""
import pytest
from httpx import ASGITransport, AsyncClient

from config import settings
from main import app

SERVICE_KEYS = ("db", "ollama", "piper", "whisper")


async def _get_health(monkeypatch, ollama: bool, tts: bool, whisper: bool) -> dict:
    async def fake_ollama():
        return ollama

    monkeypatch.setattr("routers.health.check_ollama_health", fake_ollama)
    monkeypatch.setattr("routers.health.check_piper_available", lambda: tts)
    monkeypatch.setattr("routers.health.check_whisper_available", lambda: whisper)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        res = await c.get("/api/health")
    assert res.status_code == 200
    return res.json()


@pytest.mark.asyncio
async def test_health_response_shape(monkeypatch):
    """Health has one 'ok'/'unavailable' field per service, the tutor model name and an overall status."""
    body = await _get_health(monkeypatch, ollama=True, tts=True, whisper=True)

    assert set(body) == {*SERVICE_KEYS, "ollama_model", "status"}
    assert all(body[key] in ("ok", "unavailable") for key in SERVICE_KEYS)
    assert body["ollama_model"] == settings.ollama_model
    assert body["status"] == "ok"


@pytest.mark.asyncio
async def test_health_reports_each_missing_service_on_its_own(monkeypatch):
    """With only TTS installed, the tutor and speech show 'unavailable' and the status is 'degraded'."""
    body = await _get_health(monkeypatch, ollama=False, tts=True, whisper=False)

    assert body["db"] == "ok"
    assert body["ollama"] == "unavailable"
    assert body["piper"] == "ok"
    assert body["whisper"] == "unavailable"
    assert body["status"] == "degraded"
