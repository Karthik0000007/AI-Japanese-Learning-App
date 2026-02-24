"""routers/health.py — Dependency health check endpoint used by setup scripts and monitoring."""
from fastapi import APIRouter

from core.tts_piper import check_piper_available
from core.tutor import check_ollama_health

router = APIRouter(prefix="/api/health", tags=["health"])


@router.get("")
async def health_check() -> dict:
    """
    Returns status of all three external dependencies:
      db     — always "ok" if this endpoint is reachable (DB is required to start)
      ollama — checked via Ollama /api/tags HTTP call
      piper  — checked by confirming binary + model file exist on disk
    """
    ollama_ok = await check_ollama_health()
    piper_ok = check_piper_available()

    return {
        "db": "ok",
        "ollama": "ok" if ollama_ok else "unavailable",
        "piper": "ok" if piper_ok else "unavailable",
        "status": "ok" if (ollama_ok and piper_ok) else "degraded",
    }
