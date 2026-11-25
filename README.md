# 🗾 Offline AI Japanese Trainer

[![CI](https://github.com/Karthik0000007/AI-Japanese-Learning-App/actions/workflows/ci.yml/badge.svg)](https://github.com/Karthik0000007/AI-Japanese-Learning-App/actions/workflows/ci.yml)

A self-hosted Japanese study app: JLPT-ordered flashcards with SM-2 spaced
repetition, vocabulary and kanji browsers, and an optional AI tutor that runs
on your own computer. One command starts it with Docker, and it works with no
internet connection once it is installed.

日本語版: [README.ja.md](README.ja.md)

![Flashcard review](docs/screenshots/flashcards.gif)

| Dashboard | AI tutor | Kanji browser |
|---|---|---|
| ![Dashboard](docs/screenshots/dashboard.png) | ![AI tutor](docs/screenshots/tutor.png) | ![Kanji browser](docs/screenshots/kanji.png) |

---

## Quick Start

Only [Docker](https://docs.docker.com/get-docker/) is needed.

```bash
docker compose up --build
```

Open **http://localhost:8000**. The first start creates the database, runs the
migrations and loads the bundled N5 sample (168 words and 80 kanji), so the
flashcards work straight away. Your data is kept in a Docker volume.

**Add the AI tutor** (downloads Ollama and the `llama3.1:8b` model, about 5 GB,
on the first run):

```bash
docker compose --profile ai up --build
```

Without the `ai` profile everything except the tutor works, and the tutor page
shows how to turn it on. Stop with `Ctrl+C` or `docker compose down`; add `-v`
to delete the data as well.

---

## Features

- **Flashcards with SM-2 spaced repetition** — grade each card Again / Hard /
  Good / Easy; the app schedules the next review. Daily cap on new cards.
- **JLPT order** — every word and kanji has a level from N5 to N1.
- **Vocabulary browser** — search by word, reading or meaning; filter by level.
- **Kanji browser** — on-yomi, kun-yomi, meanings and stroke count (plus an
  example word for most kanji in the N5 sample); search by character, reading or meaning.
- **Progress page** — day streak, all-time accuracy, per-level progress and a
  7-day review forecast.
- **AI tutor (optional)** — five modes (TEACH, QUIZ, EXPLAIN, CORRECT, CHAT).
  It answers with furigana and is told not to simply translate for you.
  Replies stream in word by word.
- **Voice input and Japanese audio (optional)** — speak to the tutor (Whisper)
  and hear Japanese words and tutor replies (pyopenjtalk).
- **Works offline and privately** — no cloud APIs. The tutor model runs locally
  in Ollama, and the frontend libraries are bundled. The internet is needed only
  to install and, the first time, to download the dictionaries and AI models.
- **Clear behaviour when AI is off** — the UI checks `/api/health`, disables
  buttons for missing services and explains how to enable them.

---

## Architecture

```mermaid
flowchart LR
    subgraph Browser["Browser: Vue 3, no build step"]
        UI[Dashboard / Flashcards / Vocab / Kanji / Tutor / Progress]
    end

    subgraph App["FastAPI app (port 8000)"]
        R[routers/*: cards, vocab, kanji, progress, settings, health]
        SRS[core/srs.py: SM-2]
        TUT[core/tutor.py: SSE stream]
        STT[core/whisper.py: optional]
        TTS[core/tts_piper.py: pyopenjtalk, optional]
    end

    DB[(PostgreSQL 16)]
    OLL[Ollama: llama3.1:8b, optional]
    SEED[tools/seed.py + data/sample_n5.json]

    UI -- JSON / audio --> R
    UI -- SSE --> TUT
    R --> SRS --> DB
    R --> DB
    TUT --> OLL
    UI --> STT
    UI --> TTS
    SEED --> DB
```

| Layer | Technology | Where |
|---|---|---|
| API server | FastAPI + Uvicorn (async) | `main.py`, `routers/` |
| Database | PostgreSQL 16, asyncpg, SQLModel | `models/`, `database/db.py` |
| Migrations | Alembic, run on every start | `alembic/versions/0001`–`0005` |
| Spaced repetition | SM-2, pure Python | `core/srs.py` |
| AI tutor | Ollama HTTP API, streamed as Server-Sent Events | `core/tutor.py`, `routers/tutor.py` |
| Speech-to-text | OpenAI Whisper (`base`), optional | `core/whisper.py`, `routers/speech.py` |
| Text-to-speech | pyopenjtalk, optional (file name is historical) | `core/tts_piper.py`, `routers/tts.py` |
| Frontend | Vue 3.5 + Vue Router 4.6 + DOMPurify, vendored | `templates/index.html`, `static/` |
| Data | JMdict + KANJIDIC2 | `tools/`, `data/sample_n5.json` |
| Packaging | Docker Compose: `db`, `app`, `ollama` (profile `ai`) | `Dockerfile`, `docker-compose.yml` |

Main API endpoints (interactive docs at `/docs`):

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/api/health` | Status of the database, tutor, speech and TTS |
| GET | `/api/cards/due` · `/api/cards/new` | Cards due today · introduce new cards |
| POST | `/api/cards/review` | Grade a card (`card_id`, `grade` 0–5) |
| POST / PATCH | `/api/cards/sessions` | Open / close a study session |
| GET | `/api/vocab` · `/api/kanji` | Paginated browse and search |
| GET | `/api/progress` | Streak, accuracy, level stats, forecast |
| GET / POST | `/api/settings` | JLPT focus, new cards per day |
| POST | `/api/tutor/chat` | Tutor reply as an SSE stream (503 if Ollama is off) |
| POST | `/api/tts` · `/api/speech-to-text` | Audio out · audio in (503 if not installed) |

---

## How SM-2 Works

Every card stores an ease factor (starting at 2.5), an interval in days and a
count of successful reviews. Only "easy" raises the ease factor; "good" lowers
it a little and failures lower it more, but never below 1.3. A grade below 3 ("again" or "hard")
counts as a failure, so the card starts again with a 1-day interval. A passed
card comes back after 1 day, then after 6 days, and after that after the
previous interval times the ease factor, rounded up. The due date is the review
date plus the new interval, so known cards appear less and less often while
difficult ones come back soon.

---

## Optional AI Features and Hardware

| Feature | How to enable | Hardware |
|---|---|---|
| AI tutor | Docker: `docker compose --profile ai up`. Manual: install [Ollama](https://ollama.com/download), then `ollama pull llama3.1:8b` | About **8 GB free RAM** for the default 8B model. Larger models (set `OLLAMA_MODEL`, e.g. `llama3.1:70b`) need far more, around 40 GB+. A GPU makes replies faster but is not required. |
| Voice input (Whisper) | Manual setup: `pip install -r requirements-speech.txt` | Runs on CPU, about 1 GB RAM. Downloads the `base` model (~140 MB) on first use. |
| Japanese audio (pyopenjtalk) | Same file as above | Light; runs on any CPU. |

The Docker image does not include the speech packages, to keep it small (323 MB).

---

## Manual Setup (without Docker)

Needs Python 3.10–3.12 and PostgreSQL 16 (a local install or
`docker run -d -e POSTGRES_PASSWORD=postgres -e POSTGRES_DB=jlpt_trainer -p 5432:5432 postgres:16`).

```bash
pip install -r requirements.txt
pip install -r requirements-speech.txt   # optional: voice input + Japanese audio
cp .env.example .env                     # then set DATABASE_URL
uvicorn main:app --reload                # creates the tables on startup
python -m tools.seed --sample            # bundled N5 sample; safe to run again
```

Open **http://localhost:8000**.

For the **full dictionaries** instead of the sample, run `python tools/setup.py`.
It downloads JMdict and KANJIDIC2 (~70 MB) and seeds everything. Seeding is
idempotent: running it again adds no duplicates and keeps settings you changed.

Main settings in `.env`: `DATABASE_URL`, `OLLAMA_BASE_URL`, `OLLAMA_MODEL`,
`WHISPER_MODEL`, `WHISPER_DEVICE`, `LOG_LEVEL`. The daily new-card cap and the
JLPT focus are stored in the database and changed through `/api/settings`.

---

## Running Tests

The SM-2 tests are pure Python. The other tests need a PostgreSQL database
called `jlpt_trainer_test` (the suite creates and drops its tables). Ollama,
Whisper and TTS are **not** needed.

```bash
docker run --rm -d --name jlpt-test-db -e POSTGRES_PASSWORD=postgres -e POSTGRES_DB=jlpt_trainer_test -p 5432:5432 postgres:16
pip install -r requirements.txt -r requirements-dev.txt
pytest -v
ruff check .
docker stop jlpt-test-db
```

If your Postgres uses another port or password, set `TEST_DATABASE_URL`, for
example `postgresql+asyncpg://postgres:secret@localhost:5433/jlpt_trainer_test`.

CI ([.github/workflows/ci.yml](.github/workflows/ci.yml)) runs the same lint and
tests against a `postgres:16` service on every push and pull request.

---

## Design Decisions

**Why PostgreSQL, even for one user?**
The data fits PostgreSQL features I actually use. Kanji readings are stored as
JSONB arrays with GIN indexes for fast reading search. Seeding uses
`INSERT … ON CONFLICT DO NOTHING` on unique keys, so it is safe to run again.
The async server can handle several requests at once (two browser tabs, the
tutor streaming while you review) without SQLite's single-writer locking. And
with Docker Compose, a PostgreSQL server costs the user nothing to set up.

**Why Server-Sent Events for the tutor?**
The tutor only sends data one way, from the server to the browser, so a
WebSocket would be more than needed. SSE is plain HTTP: FastAPI's
`StreamingResponse` produces it and the browser reads it with `fetch`. No extra
libraries are needed on either side. Because it is ordinary HTTP, the endpoint
can still return a normal `503` JSON error before the stream starts.

**Why no frontend build step?**
The UI is six views. Vue, Vue Router and DOMPurify are three pinned files in
`static/vendor/` (versions and checksums in `VERSIONS.md`), so the app needs no
Node.js, no `npm install` and no CDN, which keeps the offline promise. The
trade-off: no TypeScript, no single-file components and no minification of my
own code. That is acceptable at this size.

---

## Data Attribution

This app uses the **JMdict** (Japanese–English dictionary) and **KANJIDIC2**
(kanji dictionary) files. These files are the property of the
[Electronic Dictionary Research and Development Group](https://www.edrdg.org/)
(EDRDG) and are used in conformance with the Group's
[licence](https://www.edrdg.org/edrdg/licence.html), under the
[Creative Commons Attribution-ShareAlike 4.0](https://creativecommons.org/licenses/by-sa/4.0/) licence.

- JMdict: https://www.edrdg.org/wiki/index.php/JMdict-EDICT_Dictionary_Project
- KANJIDIC2: https://www.edrdg.org/wiki/index.php/KANJIDIC_Project

`data/sample_n5.json` is derived from these files by `tools/build_sample.py`
and is shared under the same CC BY-SA 4.0 licence. Kanji are the KANJIDIC2
entries tagged with the old JLPT level 4 (today's N5); the choice of vocabulary
words is a curated list of common N5 words, while their readings, meanings and
parts of speech come from JMdict.

---

## What I Would Improve Next

1. **Real JLPT levels for the full dictionary.** JMdict has no JLPT tags, so the
   full import currently guesses levels. I would add a licensed JLPT word list
   and match it by word and reading. (The bundled N5 sample is already correct.)
2. **Make "introduce new cards" an explicit action.** `GET /api/cards/new` also
   creates the cards, so even opening the Dashboard uses the daily quota. It
   should be a `POST`, called only when a review session starts.
3. **Let "Hard" keep progress.** SM-2 treats grade 2 as a failure, so "Hard"
   restarts a card. Sending grade 3 or 4 for "Hard" would match what users expect.
4. **Timezone-aware dates.** Times are stored without a timezone, which is why
   SQLModel is pinned to 0.0.37. Moving to UTC-aware timestamps would allow upgrades.
5. **Frontend tests** with Playwright for the review flow and the "AI is off" banners.
6. **Tidy up legacy TTS names.** Rename `core/tts_piper.py` and remove the old
   Piper settings and download step in `tools/setup.py`.
7. **Speak whole sentences.** The tutor's audio queue sends the last streamed
   token rather than the full sentence to TTS.
