"""tests/test_optional_deps.py — The app must work when speech/TTS packages are not installed."""
import json
import subprocess
import sys
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from main import app

REPO_ROOT = Path(__file__).resolve().parent.parent

# Runs in a fresh interpreter. Setting sys.modules[name] = None makes
# `import name` raise ImportError and find_spec(name) return None, which is
# exactly what Python does when a package is not installed.
_NO_SPEECH_SCRIPT = """
import asyncio, json, sys
for name in ("whisper", "torch", "pyopenjtalk", "numpy", "scipy"):
    sys.modules[name] = None

import main  # must not crash
import routers.health

async def fake_ollama():
    return False
routers.health.check_ollama_health = fake_ollama  # keep the test offline and fast

from httpx import ASGITransport, AsyncClient

async def run():
    transport = ASGITransport(app=main.app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        res = await c.get("/api/health")
        print(json.dumps({"status_code": res.status_code, "body": res.json()}))

asyncio.run(run())
"""


def test_app_imports_and_health_works_without_speech_packages():
    """With whisper, torch and the TTS packages missing, main imports and /api/health still answers."""
    proc = subprocess.run(
        [sys.executable, "-c", _NO_SPEECH_SCRIPT],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert proc.returncode == 0, proc.stderr

    result = json.loads(proc.stdout.strip().splitlines()[-1])
    assert result["status_code"] == 200
    assert result["body"]["whisper"] == "unavailable"
    assert result["body"]["piper"] == "unavailable"
    assert result["body"]["status"] == "degraded"


@pytest.mark.asyncio
async def test_speech_endpoint_returns_503_when_whisper_missing(monkeypatch):
    """Speech-to-text answers 503 with an install hint instead of crashing."""
    monkeypatch.setattr("routers.speech.check_whisper_available", lambda: False)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        res = await c.post(
            "/api/speech-to-text",
            files={"audio": ("clip.wav", b"RIFF0000", "audio/wav")},
        )

    assert res.status_code == 503
    assert "requirements-speech.txt" in res.json()["detail"]


@pytest.mark.asyncio
async def test_tts_endpoint_returns_503_when_tts_missing(monkeypatch):
    """Text-to-speech answers 503 with an install hint instead of crashing."""
    monkeypatch.setattr("routers.tts.check_tts_installed", lambda: False)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        res = await c.post("/api/tts", json={"text": "こんにちは"})

    assert res.status_code == 503
    assert "requirements-speech.txt" in res.json()["detail"]
