# 🗾 Offline AI Japanese Language Trainer

> A fully offline, JLPT-ordered spaced-repetition tutor with an AI sensei, kanji browser, and pronunciation — no internet required during use.

---

## Overview

A complete offline Japanese learning application built around three core ideas:

- **Learn in JLPT order** — all vocabulary and kanji are tagged N5 through N1 so you always study the most useful words first.
- **Never forget what you learn** — an SM-2 spaced-repetition system (like Anki) schedules every card for optimal review timing.
- **A tutor, not a translator** — the AI assistant teaches grammar, quizzes you, corrects your writing, and explains concepts. It will not simply translate for you.

---

## Features

- **Flashcard SRS** — SM-2 algorithm with Again / Hard / Good / Easy grades; daily new-card cap; streaks and mastery tracking
- **Full JLPT vocabulary** — sourced from JMdict; N5 through N1 with readings, meanings, and part-of-speech
- **Full kanji browser** — sourced from KANJIDIC2; on-yomi, kun-yomi, stroke count, meanings, and JLPT level
- **AI Tutor (5 modes)** — TEACH · QUIZ · EXPLAIN · CORRECT · CHAT; powered by LLaMA 3.1 70B via Ollama; streams responses in real time
- **Offline TTS** — Japanese pronunciation via Piper (`ja_JP-kokoro-medium`); no cloud calls
- **Progress dashboard** — day streak, accuracy, per-level mastery bars, 7-day review forecast
- **Fully local** — PostgreSQL + FastAPI + Vue 3; nothing leaves your machine

---

## Tech Stack

| Layer | Technology |
|---|---|
| API server | FastAPI + Uvicorn (async) |
| Database | PostgreSQL 16 + asyncpg |
| ORM / Models | SQLModel (SQLAlchemy 2 async) |
| Migrations | Alembic (auto-run on startup) |
| SRS engine | SM-2 (pure Python, `core/srs.py`) |
| AI Tutor | LLaMA 3.1 70B via [Ollama](https://ollama.com) (SSE streaming) |
| TTS | [Piper](https://github.com/rhasspy/piper) — `ja_JP-kokoro-medium` |
| Frontend | Vue 3 + Vue Router (CDN, no build step) |
| Data sources | JMdict XML + KANJIDIC2 XML + JLPT overlay |
| Config | Pydantic `BaseSettings` + `.env` |
| Tests | pytest + pytest-asyncio + httpx |

---

## Project Structure

```
AI-Japanese-Learning-App/
|
+-- main.py                      # FastAPI app entry point
+-- config.py                    # Pydantic settings (reads .env)
+-- requirements.txt
+-- pixi.toml
+-- .env.example                 # Copy to .env and edit
|
+-- database/
|   +-- db.py                    # Async engine, session factory
|
+-- models/
|   +-- vocab.py                 # Vocab table + JLPTLevel enum
|   +-- kanji.py                 # Kanji table (JSONB on/kun_yomi)
|   +-- srs.py                   # SRSCard, ReviewLog, StudySession
|   +-- meta.py                  # Key-value settings table
|
+-- alembic/
|   +-- env.py
|   +-- versions/
|       +-- 0001_initial_schema.py
|       +-- 0002_srs_cards.py
|       +-- 0003_sessions_and_meta.py
|       +-- 0004_indexes.py
|
+-- core/
|   +-- srs.py                   # SM-2 algorithm + DB helpers
|   +-- tutor.py                 # Ollama streaming, 5 tutor modes
|   +-- tts_piper.py             # Piper subprocess TTS
|
+-- routers/
|   +-- cards.py                 # /api/cards — due, new, review, sessions
|   +-- vocab.py                 # /api/vocab
|   +-- kanji.py                 # /api/kanji
|   +-- tutor.py                 # /api/tutor/chat (SSE)
|   +-- tts.py                   # /api/tts
|   +-- progress.py              # /api/progress
|   +-- settings.py              # /api/settings
|   +-- health.py                # /api/health
|
+-- tools/
|   +-- setup.py                 # First-run orchestrator
|   +-- fetch_jmdict.py          # Download + parse JMdict XML
|   +-- fetch_kanjidic.py        # Download + parse KANJIDIC2 XML
|   +-- seed.py                  # Bulk-insert vocab + kanji into DB
|
+-- templates/
|   +-- index.html               # Vue 3 SPA shell
|
+-- static/
|   +-- css/app.css
|   +-- js/
|   |   +-- app.js               # Vue createApp + router bootstrap
|   |   +-- views/
|   |       +-- Dashboard.js
|   |       +-- Flashcards.js
|   |       +-- VocabBrowser.js
|   |       +-- KanjiBrowser.js
|   |       +-- Tutor.js
|   |       +-- Progress.js
|   +-- piper/                   # Voice model downloaded by setup.py
|
+-- data/                        # Created by fetch_* tools (git-ignored)
|   +-- jmdict_parsed.json
|   +-- kanjidic_parsed.json
|   +-- jlpt_overlay.json
|
+-- tests/
    +-- conftest.py
    +-- test_srs.py
    +-- test_cards_router.py
```

---

## Setup & First Run

### Prerequisites

| Requirement | Notes |
|---|---|
| Python 3.10+ | |
| PostgreSQL 16 | Running locally or via Docker |
| [Ollama](https://ollama.com/download) | For the AI Tutor (optional but recommended) |
| [Piper](https://github.com/rhasspy/piper/releases) | For offline TTS (optional) |

### PostgreSQL via Docker (quickest option)

```powershell
docker run -d --name jlpt-postgres `
  -e POSTGRES_PASSWORD=postgres `
  -e POSTGRES_DB=jlpt_trainer `
  -p 5432:5432 postgres:16
```

### Install Python dependencies

```powershell
pip install -r requirements.txt
```

### Configure environment

```powershell
copy .env.example .env
# Edit .env — set DATABASE_URL at minimum
```

Key `.env` settings:

```ini
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/jlpt_trainer
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama3.1:70b
PIPER_BINARY=piper
PIPER_MODEL_PATH=static/piper/ja_JP-kokoro-medium.onnx
NEW_CARDS_PER_DAY=20
```

### First-run setup (one-time)

Checks all dependencies, runs Alembic migrations, downloads the Piper voice model, and seeds the full JLPT database from JMdict + KANJIDIC2:

```powershell
python tools/setup.py
```

### Pull the AI Tutor model

```powershell
ollama serve
ollama pull llama3.1:70b
```

### Start the app

```powershell
uvicorn main:app --reload
```

Open **http://localhost:8000**

---

## Running Tests

```powershell
pytest tests/ -v
```

---

## API Reference

| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/health` | DB / Ollama / Piper status |
| GET | `/api/cards/due` | SRS cards due for review today |
| GET | `/api/cards/new` | Unseeded items ready to learn |
| POST | `/api/cards/review` | Submit a grade (0 / 2 / 3 / 5) |
| POST | `/api/cards/sessions` | Start a study session |
| PATCH | `/api/cards/sessions/{id}` | End a study session |
| GET | `/api/vocab` | Paginated vocab list (filter by level / search) |
| GET | `/api/vocab/{id}` | Single vocab item |
| GET | `/api/kanji` | Paginated kanji list |
| GET | `/api/kanji/{character}` | Single kanji detail |
| POST | `/api/tutor/chat` | AI tutor — SSE streaming response |
| POST | `/api/tts` | Text to `audio/wav` |
| GET | `/api/progress` | Streak, accuracy, level stats, 7-day forecast |
| GET/POST | `/api/settings` | Read / update app settings |

---

## SM-2 Grading Scale

| Button | Score | Meaning |
|---|---|---|
| Again | 0 | Completely forgot — card resets to day 1 |
| Hard | 2 | Recalled with significant difficulty |
| Good | 3 | Recalled correctly with some effort |
| Easy | 5 | Instant recall — interval boosted |

---

## AI Tutor Modes

| Mode | Behaviour |
|---|---|
| **TEACH** | Explains a grammar point, word, or concept step-by-step |
| **QUIZ** | Tests your knowledge and waits for your answer |
| **EXPLAIN** | Deep-dive into grammar structure, particles, conjugations |
| **CORRECT** | You write Japanese; the tutor corrects and explains errors |
| **CHAT** | Free conversation practice in Japanese |

> The tutor will not translate for you. Its job is to make you think.
