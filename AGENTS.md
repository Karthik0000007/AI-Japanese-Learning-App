# AGENTS.md

## Cursor Cloud specific instructions

This is the **Offline AI Japanese Language Trainer** — a FastAPI backend + PostgreSQL +
a Vue 3 single-page app (Vue is loaded from a CDN, so there is **no frontend build step**).
See `README.md` and `ARCHITECTURE.md` for the full design.

### Environment layout
- Python deps live in a virtualenv at `.venv/` (created/refreshed by the startup update script).
  Run things with `.venv/bin/python`, `.venv/bin/uvicorn`, `.venv/bin/pytest`, etc.
- App config is read from `.env` (Pydantic settings). If it is missing, create it with
  `cp .env.example .env`. The defaults point at a local Postgres (`postgres:postgres@localhost:5432`).

### PostgreSQL (required, not auto-started)
PostgreSQL 16 is installed at the system level but is **not started automatically** on VM boot,
and the update script intentionally does not start it. Start it each session before running the
app or tests:

```
sudo pg_ctlcluster 16 main start
```

Databases (already created and seeded; data persists in the VM snapshot):
- `jlpt_trainer` — app database (user/password `postgres`/`postgres`).
- `jlpt_trainer_test` — used by the test suite (`TEST_DATABASE_URL` default).

### Data seeding (one-time, already done in the snapshot)
`.venv/bin/python tools/setup.py` runs Alembic migrations, fetches JMdict + KANJIDIC2 (needs
internet), and seeds the DB. The app also runs `alembic upgrade head` automatically on startup.

Known data gap: `data/jlpt_overlay.json` is **not bundled** in the repo, so JMdict vocab ends up
with no JLPT tag and the `vocab` table seeds **0 rows**. Only **kanji** are seeded (~10k rows,
levels N4–N1; there is no N5 kanji data). For flashcards/SRS use `type=kanji` and level `N4`+;
the default `type=vocab`/level `N5` returns empty results.

### Running the app (development)
```
.venv/bin/uvicorn main:app --reload --host 127.0.0.1 --port 8000
```
Then open http://127.0.0.1:8000 (API docs at `/docs`).

- On startup Whisper STT auto-loads the `base` model (downloaded into the snapshot already).
- `ollama` (AI Tutor, LLaMA 3.1 70B) and `piper` (TTS) are **not installed** — they are optional;
  `/api/health` reporting them `unavailable` and overall `status: degraded` is expected.

### Tests, lint, build
- Tests: `.venv/bin/python -m pytest tests/ -v` (requires Postgres running + `jlpt_trainer_test`).
  Note: the test suite has **pre-existing failures unrelated to the environment** —
  `tests/test_srs.py` calls an outdated `sm2_review(interval=, ease=, reps=, score=)` signature
  (the implementation is `sm2_review(card, grade)`), and `tests/test_cards_router.py` hits a
  pytest-asyncio "Future attached to a different loop" error caused by the module-level async
  engine combined with mixed fixture scopes in `tests/conftest.py`.
- Lint: no linter/formatter is configured in this repo.
- Build: none — the frontend is plain CDN-loaded Vue served as static files.

### Known pre-existing bug (frontend)
The Vue SPA currently fails to load in the browser because `static/js/app.js` and
`static/js/views/Dashboard.js` both declare `const { ref } = Vue;` at global script scope,
which is a duplicate-`const` redeclaration (`SyntaxError`). The **backend API is fully
functional**; this is an application code defect, not an environment issue.
