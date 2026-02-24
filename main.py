"""
main.py — FastAPI application entry point.

Startup sequence (lifespan):
  1. Verify PostgreSQL is reachable
  2. Run `alembic upgrade head`  (schema always at latest migration)
  3. Warn if Ollama / Piper are unavailable (non-fatal)
  4. Register all routers
  5. Serve Vue 3 SPA at /

Run:
  uvicorn main:app --reload --host 127.0.0.1 --port 8000
"""
import logging
import subprocess
import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from config import settings
from database.db import engine
from routers import cards, health, kanji, progress, settings as settings_router, tts, tutor, vocab

logging.basicConfig(
    level=settings.log_level.upper(),
    format="%(levelname)-8s %(name)s — %(message)s",
)
log = logging.getLogger("app")


# ─── Lifespan (startup / shutdown) ───────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    # 1. Test DB connection
    log.info("Checking PostgreSQL connection…")
    try:
        async with engine.connect() as conn:
            await conn.execute(__import__("sqlalchemy").text("SELECT 1"))
        log.info("PostgreSQL OK")
    except Exception as exc:
        log.critical(
            "Cannot connect to PostgreSQL: %s\n"
            "Make sure PostgreSQL is running and DATABASE_URL in .env is correct.",
            exc,
        )
        sys.exit(1)

    # 2. Run Alembic migrations
    log.info("Running Alembic migrations…")
    try:
        result = subprocess.run(
            [sys.executable, "-m", "alembic", "upgrade", "head"],
            capture_output=True,
            text=True,
            check=True,
        )
        for line in result.stdout.splitlines():
            if line.strip():
                log.info("alembic: %s", line)
    except subprocess.CalledProcessError as exc:
        log.critical("Alembic migration failed:\n%s", exc.stderr)
        sys.exit(1)

    # 3. Warn about optional AI dependencies
    from core.tutor import check_ollama_health
    from core.tts_piper import check_piper_available

    if not await check_ollama_health():
        log.warning(
            "Ollama is not running or model '%s' is not pulled. "
            "The AI Tutor tab will be unavailable until Ollama is started.",
            settings.ollama_model,
        )
    else:
        log.info("Ollama OK — model: %s", settings.ollama_model)

    if not check_piper_available():
        log.warning(
            "Piper TTS binary or model not found. "
            "Audio pronunciation will be unavailable. "
            "Run: python tools/setup.py"
        )
    else:
        log.info("Piper TTS OK")

    log.info("Ready — serving at http://%s:%d", settings.app_host, settings.app_port)
    yield  # ─── application running ───

    # Shutdown: close any open study sessions
    log.info("Shutting down — closing open study sessions…")
    from sqlalchemy import text
    async with engine.begin() as conn:
        await conn.execute(
            text(
                "UPDATE study_sessions SET ended_at = NOW() "
                "WHERE ended_at IS NULL"
            )
        )
    await engine.dispose()
    log.info("Clean shutdown complete.")


# ─── FastAPI app ──────────────────────────────────────────────────────────────

app = FastAPI(
    title="Offline AI Japanese Language Trainer",
    description=(
        "JLPT-ordered spaced-repetition tutor with LLaMA3.1 70B AI tutor "
        "and Piper offline TTS. Fully local — no internet required during use."
    ),
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# Allow the Vue devserver to call the API during development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8000", "http://127.0.0.1:8000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── Routers ──────────────────────────────────────────────────────────────────
app.include_router(health.router)
app.include_router(cards.router)
app.include_router(vocab.router)
app.include_router(kanji.router)
app.include_router(tutor.router)
app.include_router(tts.router)
app.include_router(progress.router)
app.include_router(settings_router.router)

# ─── Static files & SPA ───────────────────────────────────────────────────────
app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/", include_in_schema=False)
@app.get("/{path:path}", include_in_schema=False)
async def serve_spa(path: str = "") -> FileResponse:
    """Serve the Vue 3 SPA shell for all non-API routes (client-side routing)."""
    return FileResponse("templates/index.html")
