# AGENTS.md

## Cursor Cloud specific instructions

This is a single-product app: the **Offline AI Japanese Language Trainer** — a FastAPI
backend (async, SQLModel/asyncpg) that also serves a Vue 3 SPA (CDN, no build step).
PostgreSQL is the only hard dependency; Ollama (AI tutor), Piper (TTS) and Whisper (STT)
are optional AI services. See `README.md` for the full product/endpoint overview and
`ARCHITECTURE.md` for internals.

### Environment layout (already provisioned by the startup update script)
- Python deps live in a project virtualenv at `/workspace/.venv`. Run tools with
  `.venv/bin/<cmd>` (e.g. `.venv/bin/uvicorn`, `.venv/bin/pytest`, `.venv/bin/python`).
- `requirements.txt` is incomplete on purpose-of-record: it omits `torch`, `openai-whisper`
  (needed because `routers/speech.py` imports `core.whisper` at import time, so the app and
  the test suite cannot even import without them) and `pytest`/`pytest-asyncio`. The update
  script installs these extras (CPU-only torch) on top of `requirements.txt`. `pixi` is not
  installed/used here — use the venv.
- `.env` already exists (copied from `.env.example`); defaults point at local Postgres.

### PostgreSQL (must be running before the app or tests)
- Start it each session (it is not auto-started): `sudo pg_ctlcluster 16 main start`
- Credentials/DBs are already created and seeded: user `postgres`/`postgres`, databases
  `jlpt_trainer` (dev) and `jlpt_trainer_test` (tests, default `TEST_DATABASE_URL`).
- The app exits immediately if Postgres is unreachable; it auto-runs Alembic migrations on
  startup. Data seeding is already done — only kanji are populated (see gotcha below); to
  re-seed run `.venv/bin/python tools/seed.py` (full first-run is `tools/setup.py`, which
  needs internet to download JMdict/KANJIDIC2).

### Run / test / lint
- Run (dev): `.venv/bin/uvicorn main:app --reload --host 127.0.0.1 --port 8000`, then
  the API + Swagger docs are at `http://127.0.0.1:8000` and `/docs`.
- Tests: `.venv/bin/pytest tests/ -v` (needs Postgres up + the `jlpt_trainer_test` DB).
- No linter is configured in this repo (no ruff/flake8/black config); there is no lint step.

### Known pre-existing issues (NOT environment problems — do not "fix" as part of setup)
- The Vue SPA does not render: `static/js/views/Dashboard.js` declares
  `const { ref, onMounted } = Vue;` at global scope, which collides with `app.js` and throws
  a redeclaration SyntaxError on the default route. The backend API and Swagger `/docs` work
  fine — use those to exercise/demonstrate functionality.
- `vocab` table is empty: seeding requires `data/jlpt_overlay.json` (described as "bundled"
  but absent), so JMdict entries get no JLPT level and none are inserted. Kanji (KANJIDIC2)
  seed fine and have levels N4–N1 (no N5). Vocab-based flashcards/browser will be empty;
  use kanji (e.g. `GET /api/cards/new?type=kanji&level=N4`).
- The test suite is out of sync with the code (e.g. `sm2_review()` signature, response keys
  like `id`/`session_id`); most tests fail by design. The harness itself works and
  `test_health_endpoint` passes.
- Optional services (Ollama, Piper) are not installed; `/api/health` reports them
  `unavailable` and the app logs non-fatal warnings. Whisper STT is installed and loads.
