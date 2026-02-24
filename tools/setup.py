"""
tools/setup.py — First-run orchestrator.

Checks all dependencies, runs Alembic migrations, downloads Piper voice model,
fetches and seeds JLPT data.

Run: python tools/setup.py
"""
from __future__ import annotations

import asyncio
import os
import shutil
import subprocess
import sys
import urllib.request
from pathlib import Path

# Allow importing from the repo root
sys.path.insert(0, str(Path(__file__).parent.parent))

PIPER_MODEL_DIR = Path("static/piper")
PIPER_MODEL_URL_BASE = (
    "https://huggingface.co/rhasspy/piper-voices/resolve/main/ja/ja_JP/kokoro/medium"
)
ONNX_FILENAME = "ja_JP-kokoro-medium.onnx"
JSON_FILENAME = "ja_JP-kokoro-medium.onnx.json"

SECTION = "=" * 60


def banner(title: str) -> None:
    print(f"\n{SECTION}\n  {title}\n{SECTION}")


# ─── Step 1: PostgreSQL ────────────────────────────────────────────────────────

async def check_postgres() -> None:
    banner("Step 1/5 — Check PostgreSQL")
    from config import settings
    from database.db import engine
    from sqlalchemy import text

    print(f"  URL: {settings.database_url.split('@')[-1]}")
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        print("  ✓ PostgreSQL connection OK")
    except Exception as exc:
        print(f"  ✗ Cannot connect: {exc}")
        print("\n  Fix: Start PostgreSQL and set DATABASE_URL in .env")
        print("  Quickstart with Docker:")
        print(
            "    docker run -d --name jlpt-postgres \\n"
            "      -e POSTGRES_PASSWORD=postgres -e POSTGRES_DB=jlpt_trainer \\n"
            "      -p 5432:5432 postgres:16"
        )
        sys.exit(1)
    finally:
        await engine.dispose()


# ─── Step 2: Alembic ──────────────────────────────────────────────────────────

def run_migrations() -> None:
    banner("Step 2/5 — Run Alembic migrations")
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        capture_output=False,
    )
    if result.returncode != 0:
        print("  ✗ Alembic migration failed.")
        sys.exit(1)
    print("  ✓ Schema at head")


# ─── Step 3: Ollama ───────────────────────────────────────────────────────────

async def check_ollama() -> None:
    banner("Step 3/5 — Check Ollama")
    from core.tutor import check_ollama_health
    from config import settings

    ok = await check_ollama_health()
    if ok:
        print(f"  ✓ Ollama running — model '{settings.ollama_model}' available")
    else:
        print(f"  ⚠ Ollama not running or model '{settings.ollama_model}' not pulled")
        print("  The AI Tutor will be unavailable until you run:")
        print("    ollama serve")
        print(f"    ollama pull {settings.ollama_model}")
        print("  (continuing setup — this is non-fatal)")


# ─── Step 4: Piper voice model ────────────────────────────────────────────────

def download_piper_model() -> None:
    banner("Step 4/5 — Download Piper voice model")
    PIPER_MODEL_DIR.mkdir(parents=True, exist_ok=True)

    onnx_path = PIPER_MODEL_DIR / ONNX_FILENAME
    json_path = PIPER_MODEL_DIR / JSON_FILENAME

    if onnx_path.exists() and json_path.exists():
        print(f"  ✓ Model already present: {onnx_path}")
        return

    for filename, path in [(ONNX_FILENAME, onnx_path), (JSON_FILENAME, json_path)]:
        if path.exists():
            print(f"  ✓ {filename} already present")
            continue
        url = f"{PIPER_MODEL_URL_BASE}/{filename}"
        print(f"  ↓ Downloading {filename} …")
        try:
            urllib.request.urlretrieve(url, path)
            size_mb = path.stat().st_size / 1e6
            print(f"  ✓ {filename} ({size_mb:.1f} MB)")
        except Exception as exc:
            print(f"  ✗ Failed to download {filename}: {exc}")
            print(f"  Manual download: {url}")
            print(f"  Save to: {path.absolute()}")

    # Check piper binary is available
    piper_bin = shutil.which("piper")
    if piper_bin:
        print(f"  ✓ Piper binary found: {piper_bin}")
    else:
        print("  ⚠ Piper binary not found in PATH.")
        print("  Download from: https://github.com/rhasspy/piper/releases")
        print("  Or set PIPER_BINARY in .env to the absolute path.")


# ─── Step 5: Seed database ────────────────────────────────────────────────────

async def seed_database() -> None:
    banner("Step 5/5 — Seed JLPT database")

    from pathlib import Path as P
    data_dir = P("data")

    # Fetch JMdict if not already parsed
    jmdict_json = data_dir / "jmdict_parsed.json"
    if not jmdict_json.exists():
        print("  Fetching and parsing JMdict (one-time, ~30 seconds)…")
        from tools.fetch_jmdict import run as fetch_jmdict
        fetch_jmdict()
    else:
        print(f"  ✓ JMdict parsed data exists: {jmdict_json}")

    # Fetch KANJIDIC2 if not already parsed
    kanjidic_json = data_dir / "kanjidic_parsed.json"
    if not kanjidic_json.exists():
        print("  Fetching and parsing KANJIDIC2 (one-time)…")
        from tools.fetch_kanjidic import run as fetch_kanjidic
        fetch_kanjidic()
    else:
        print(f"  ✓ KANJIDIC2 parsed data exists: {kanjidic_json}")

    # Run seeder
    print("  Seeding database (idempotent)…")
    from tools.seed import main as seed_main
    await seed_main()


# ─── Main ─────────────────────────────────────────────────────────────────────

async def async_main() -> None:
    print("\n╔══════════════════════════════════════════════════════════╗")
    print("║   Offline AI Japanese Language Trainer — First-Run Setup  ║")
    print("╚══════════════════════════════════════════════════════════╝\n")

    # Create .env if missing
    if not Path(".env").exists() and Path(".env.example").exists():
        shutil.copy(".env.example", ".env")
        print("  Created .env from .env.example — edit it to customise settings.\n")

    await check_postgres()
    run_migrations()
    await check_ollama()
    download_piper_model()
    await seed_database()

    print(f"\n{SECTION}")
    print("  Setup complete! Start the app with:")
    print()
    print("    uvicorn main:app --reload")
    print()
    print("  Then open: http://localhost:8000")
    print(f"{SECTION}\n")


if __name__ == "__main__":
    asyncio.run(async_main())
