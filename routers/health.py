"""routers/health.py — Dependency health check endpoint used by setup scripts, monitoring and the UI."""
from fastapi import APIRouter

from config import settings
from core.tts_piper import check_piper_available
from core.tutor import check_ollama_health
from core.whisper import check_whisper_available

router = APIRouter(prefix="/api/health", tags=["health"])


@router.get("")
async def health_check() -> dict:
    """
    Report each dependency separately, so the UI can disable only what is missing:
      db           — always "ok" if this endpoint is reachable (DB is required to start)
      ollama       — AI tutor: Ollama reachable AND the configured model pulled
      piper        — Japanese text-to-speech (legacy name; backend is pyopenjtalk)
      whisper      — speech-to-text package installed
      ollama_model — the model the tutor expects, so the UI can say what to pull
      status       — "ok" only if every optional service is available, else "degraded"
    Each service value is "ok" or "unavailable".
    """
    ollama_ok = await check_ollama_health()
    piper_ok = check_piper_available()
    whisper_ok = check_whisper_available()

    return {
        "db": "ok",
        "ollama": "ok" if ollama_ok else "unavailable",
        "piper": "ok" if piper_ok else "unavailable",
        "whisper": "ok" if whisper_ok else "unavailable",
        "ollama_model": settings.ollama_model,
        "status": "ok" if (ollama_ok and piper_ok and whisper_ok) else "degraded",
    }
