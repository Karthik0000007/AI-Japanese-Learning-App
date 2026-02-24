# Offline AI Japanese Language Trainer — Technical Architecture

> **Version:** 1.0
> **Last updated:** 2026-02-24
> **Language / Runtime:** Python 3.10+ · FastAPI · PostgreSQL 16 · SQLModel · Alembic · Vue 3 CDN · Ollama (LLaMA3.1 70B) · Piper TTS
> **Architecture style:** Offline-first, JLPT-ordered spaced-repetition tutor with AI conversation layer and fully local LLM/TTS backends

---

## Table of Contents

1. [System Overview](#1-system-overview)
2. [Architecture Breakdown](#2-architecture-breakdown)
3. [Domain Model](#3-domain-model)
4. [Execution Flow](#4-execution-flow)
5. [SM-2 Spaced-Repetition Engine](#5-sm-2-spaced-repetition-engine)
6. [AI Tutor Engine](#6-ai-tutor-engine)
7. [Key Design Decisions](#7-key-design-decisions)
8. [Failure & Edge Case Analysis](#8-failure--edge-case-analysis)
9. [Data Pipeline](#9-data-pipeline)
10. [Frontend Dashboard](#10-frontend-dashboard)
11. [Developer Onboarding Guide](#11-developer-onboarding-guide)
12. [Security & Operational Considerations](#12-security--operational-considerations)
13. [Suggested Improvements](#13-suggested-improvements)
14. [Appendix A: SM-2 Mathematical Reference](#appendix-a-sm-2-mathematical-reference)
15. [Appendix B: Glossary](#appendix-b-glossary)

---

## 1. System Overview

### Purpose

This system is a **production-quality, fully offline Japanese language tutor** designed for self-study learners progressing through the JLPT hierarchy (N5 → N4 → N3 → N2 → N1). Unlike translation apps or dictionary tools, this system acts as a **personal tutor that teaches, quizzes, corrects, and remembers**. Translation is explicitly forbidden — all interactions reinforce active production and comprehension in Japanese.

The core innovation is a **three-layer learning stack**:

1. **SM-2 Spaced-Repetition Scheduler** — A mathematically-grounded memory model (identical to early Anki) that calculates the precise future date each vocabulary item or kanji should be reviewed, right before the learner would naturally forget it.
2. **JLPT-Ordered Content Database** — A versioned PostgreSQL database seeded offline from JMdict and KANJIDIC2, containing all N5–N1 vocabulary with readings and example sentences, and all Jōyō kanji with on-yomi, kun-yomi, meanings, and real-life usage examples.
3. **LLaMA3.1 70B AI Tutor** — A locally-running large language model (via Ollama) that operates exclusively as a tutor: it introduces grammar in context, generates quizzes from the learner's own studied vocabulary, corrects written Japanese, and explains kanji deeply — never translating on demand.

### High-Level Architecture

```mermaid
flowchart TB
    subgraph Offline_Data ["Offline Data Pipeline (one-time setup)"]
        JMDICT[JMdict XML<br/>~196k entries]
        KANJIDIC[KANJIDIC2 XML<br/>2136 Jōyō kanji]
        SEED[tools/seed.py<br/>Deterministic seeder]
    end

    subgraph Database ["PostgreSQL 16 (local)"]
        VOCAB[(vocab table<br/>N5–N1 words)]
        KANJI[(kanji table<br/>readings + examples)]
        SRS[(srs_cards table<br/>SM-2 state)]
        LOGS[(review_log +<br/>study_sessions)]
        META[(meta table<br/>user settings)]
    end

    subgraph Backend ["FastAPI Application (localhost:8000)"]
        CARDS[cards router<br/>due / new / review]
        VOCABROUTER[vocab router<br/>browse + search]
        KANJIROUTER[kanji router<br/>browse + detail]
        PROGRESS[progress router<br/>stats + forecast]
        TUTOR[tutor router<br/>SSE stream]
        TTS_R[tts router<br/>WAV audio]
        SETTINGS[settings router]
        SRS_ENGINE[core/srs.py<br/>SM-2 Algorithm]
        TUTOR_ENGINE[core/tutor.py<br/>LLaMA3.1 70B]
        PIPER[core/tts_piper.py<br/>Piper TTS subprocess]
    end

    subgraph AI_Backends ["Local AI Backends"]
        OLLAMA[Ollama<br/>localhost:11434<br/>LLaMA3.1 70B]
        PIPER_BIN[Piper TTS Binary<br/>ja_JP-kokoro-medium.onnx]
    end

    subgraph Frontend ["Vue 3 SPA (CDN, served by FastAPI)"]
        DASH_V[Dashboard view]
        FLASH_V[Flashcards view]
        VOCAB_V[Vocabulary Browser]
        KANJI_V[Kanji Browser]
        TUTOR_V[AI Tutor view]
        PROG_V[Progress view]
    end

    JMDICT --> SEED
    KANJIDIC --> SEED
    SEED --> VOCAB
    SEED --> KANJI

    VOCAB --> VOCABROUTER
    KANJI --> KANJIROUTER
    SRS --> CARDS
    LOGS --> PROGRESS
    META --> SETTINGS

    CARDS --> SRS_ENGINE
    TUTOR --> TUTOR_ENGINE
    TTS_R --> PIPER
    TUTOR_ENGINE --> OLLAMA
    PIPER --> PIPER_BIN

    CARDS --> DASH_V
    CARDS --> FLASH_V
    VOCABROUTER --> VOCAB_V
    KANJIROUTER --> KANJI_V
    TUTOR --> TUTOR_V
    PROGRESS --> PROG_V

    style Database fill:#336699,color:#fff
    style Backend fill:#e67e22,color:#fff
    style AI_Backends fill:#2ecc71,color:#fff
    style Frontend fill:#6366f1,color:#fff
    style Offline_Data fill:#95a5a6,color:#fff
```

### Core Responsibilities

| Responsibility | Owner |
|---|---|
| JLPT vocabulary storage (N5–N1, readings, examples) | `vocab` PostgreSQL table |
| Jōyō kanji storage (on-yomi, kun-yomi, meanings, examples) | `kanji` PostgreSQL table |
| Per-card memory state (ease, interval, due date) | `srs_cards` table + `core/srs.py` |
| Determining which cards are due for review | SM-2 engine (`core/srs.py`) |
| Teaching, quizzing, correcting, explaining in Japanese | AI Tutor engine (`core/tutor.py`) |
| Streaming tutor responses to the browser | FastAPI `StreamingResponse` (SSE) |
| Fully offline Japanese text-to-speech (pronunciation) | Piper TTS (`core/tts_piper.py`) |
| User-facing UI: flashcards, browsers, tutor chat | Vue 3 SPA (no build step) |
| Versioned, deterministic schema management | Alembic migration chain |
| Study progress tracking and review forecasting | `review_log` table + `progress` router |

---

## 2. Architecture Breakdown

### Major Components

#### FastAPI Application (`main.py` + `routers/`)

The central backend process. Started with `uvicorn main:app --reload`, serves on `localhost:8000`. Uses FastAPI's **lifespan context** to run `alembic upgrade head` on startup before any request is served, guaranteeing the database schema is always at the latest migration.

All request/response bodies are validated via **SQLModel + Pydantic**, and every route is auto-documented at `/docs` (Swagger UI) and `/redoc` with no manual annotation required.

Key design points:
- **Async throughout** — all DB access uses `asyncpg` via SQLAlchemy's async engine; no thread pool or blocking I/O on the event loop
- **Dependency injection** — `Depends(get_session)` wires an `AsyncSession` into every route that touches the database
- **Router separation** — each concern (`cards`, `vocab`, `kanji`, `tutor`, `tts`, `progress`, `settings`) is an isolated `APIRouter` with its own prefix and tags
- **Static file serving** — `/static/` serves Vue JS files and Piper model; `/` serves `templates/index.html` (the Vue shell)

#### Database Layer (`database/db.py` + `models/`)

PostgreSQL 16 accessed via **SQLAlchemy 2.x async engine** with the `asyncpg` driver. `DATABASE_URL` is read from `.env` via Pydantic `BaseSettings`.

SQLModel table classes serve a dual role: they are simultaneously SQLAlchemy ORM models (table definitions, relationships) and Pydantic response models (serialization, validation). This eliminates the need for separate `schemas.py` / `models.py` pairs common in traditional FastAPI projects.

JSONB columns are used for `on_yomi`, `kun_yomi`, and `meaning` arrays in the `kanji` table — these are naturally multi-valued and benefit from PostgreSQL's native JSON indexing and containment operators for future search features.

#### Alembic Migration Chain (`alembic/`)

All schema changes are captured as versioned Python scripts in `alembic/versions/`. The chain is:

```
0001_initial_schema.py     → creates vocab, kanji tables
0002_srs_cards.py          → creates srs_cards table
0003_sessions_and_meta.py  → creates review_log, study_sessions, meta tables
0004_indexes.py            → adds B-tree indexes on jlpt_level, due_date; GIN index on kanji readings
```

Migrations are run automatically on startup. They are idempotent (Alembic tracks which versions have been applied). A developer can roll back with `alembic downgrade -1`.

#### SM-2 SRS Engine (`core/srs.py`)

Pure-Python module with no SQLAlchemy dependency — testable in complete isolation. Implements the SuperMemo-2 algorithm with four public functions:

| Function | Purpose |
|---|---|
| `review(card, grade) → SRSCard` | Recomputes ease factor, interval, and due date given a 0–5 grade |
| `get_due_cards(session, level, item_type, limit)` | Async DB query: cards where `due_date ≤ today`, sorted by most overdue |
| `get_new_cards(session, level, item_type, limit)` | Async DB query: vocab/kanji items with no `srs_cards` row yet |
| `get_stats(session, level) → LevelStats` | Aggregate query: mature/young/new/due counts per JLPT level |

The engine never touches the router layer and has no knowledge of HTTP. All DB writes for a review are committed in a single transaction by the calling route handler.

#### AI Tutor Engine (`core/tutor.py`)

Interfaces with Ollama's HTTP streaming API (`POST /api/generate`) using `httpx.AsyncClient`. Returns an `AsyncGenerator[str, None]` of text chunks that FastAPI wraps in a `StreamingResponse` with `Content-Type: text/event-stream`.

The tutor is forbidden (by system prompt) from providing direct translations. It reinforces comprehension through context, examples, and guided questions only. The four interaction modes (`TEACH`, `QUIZ`, `EXPLAIN`, `CORRECT`) are dispatched by injecting a mode-specific instruction block into the system prompt before the user's message.

Context injection per request:
- User's current JLPT focus level (from `meta` table)
- 10 most recently reviewed item names (from `review_log` JOIN `vocab`/`kanji`)
- 5 weakest cards (lowest `ease_factor` in `srs_cards`) for targeted reinforcement
- Current mode instruction block

#### Piper TTS (`core/tts_piper.py`)

Spawns the Piper binary as an `asyncio.subprocess.Process` with `stdin=PIPE, stdout=PIPE`. Japanese text is written to stdin; Piper streams PCM audio in WAV format to stdout. The WAV bytes are read and returned by the FastAPI `/api/tts` route.

The voice model (`ja_JP-kokoro-medium.onnx` + `.json` config, ~80 MB total) is stored in `static/piper/` and loaded by Piper at each invocation. Model path is configurable in `.env`. No network connection is required after the one-time model download in `tools/setup.py`.

`gTTS` is removed entirely — it is not listed in `requirements.txt` or `pixi.toml`.

#### Data Pipeline (`tools/`)

A one-time, offline seeding pipeline that produces the application database. Components:

| Script | Purpose |
|---|---|
| `tools/fetch_jmdict.py` | Downloads + caches `JMdict_e.xml.gz`; parses XML; writes `data/jmdict_parsed.json` |
| `tools/fetch_kanjidic.py` | Downloads + caches `kanjidic2.xml.gz`; parses XML; writes `data/kanjidic_parsed.json` |
| `tools/seed.py` | Reads parsed JSON, applies JLPT level mapping overlay, inserts rows into PostgreSQL via SQLModel; idempotent |
| `tools/setup.py` | Orchestrates full first-run: checks Ollama, Piper model, runs Alembic, runs seed |

### Dependency Relationships

```mermaid
graph TD
    MAIN[main.py<br/>FastAPI app + lifespan] --> ROUTERS[routers/]
    MAIN --> CFG[config.py<br/>BaseSettings]
    MAIN --> DB[database/db.py<br/>Async engine + session]
    MAIN --> ALEMBIC[alembic/<br/>upgrade head on startup]

    ROUTERS --> CARDS_R[routers/cards.py]
    ROUTERS --> VOCAB_R[routers/vocab.py]
    ROUTERS --> KANJI_R[routers/kanji.py]
    ROUTERS --> TUTOR_R[routers/tutor.py]
    ROUTERS --> TTS_R[routers/tts.py]
    ROUTERS --> PROGRESS_R[routers/progress.py]
    ROUTERS --> SETTINGS_R[routers/settings.py]

    CARDS_R --> SRS[core/srs.py<br/>SM-2 Algorithm]
    TUTOR_R --> TUTOR[core/tutor.py<br/>Ollama SSE]
    TTS_R --> PIPER[core/tts_piper.py<br/>Piper subprocess]

    SRS --> MODELS[models/<br/>SQLModel classes]
    MODELS --> DB

    TUTOR --> OLLAMA[Ollama HTTP API<br/>localhost:11434]
    PIPER --> PIPER_BIN[Piper binary<br/>static/piper/]

    TOOLS_SETUP[tools/setup.py] --> TOOLS_SEED[tools/seed.py]
    TOOLS_SEED --> TOOLS_JM[tools/fetch_jmdict.py]
    TOOLS_SEED --> TOOLS_KD[tools/fetch_kanjidic.py]
    TOOLS_SEED --> MODELS

    ALEMBIC --> ALEMBIC_V[alembic/versions/<br/>0001–0004]

    style MAIN fill:#4a9eff,color:#fff
    style SRS fill:#e74c3c,color:#fff
    style TUTOR fill:#e67e22,color:#fff
    style PIPER fill:#f39c12,color:#fff
    style DB fill:#336699,color:#fff
    style OLLAMA fill:#2ecc71,color:#fff
```

### External Integrations

| System | Protocol / Binding | Purpose |
|---|---|---|
| PostgreSQL 16 | `asyncpg` via SQLAlchemy 2 async engine | Primary data store for vocab, kanji, SRS state, sessions |
| Ollama | HTTP REST (`httpx.AsyncClient`) to `localhost:11434` | Local LLM serving (LLaMA3.1 70B) with streaming |
| Piper TTS | `asyncio.subprocess` (stdin/stdout pipe) | Offline Japanese text-to-speech |
| JMdict (edrdg.org) | HTTPS download (one-time, `tools/fetch_jmdict.py`) | Source for Japanese vocabulary, readings, examples |
| KANJIDIC2 (edrdg.org) | HTTPS download (one-time, `tools/fetch_kanjidic.py`) | Source for kanji, on-yomi, kun-yomi, meanings, JLPT levels |
| Vue 3 | CDN (`unpkg.com/vue@3`), loaded by browser | Frontend reactivity layer (no build step) |
| Vue Router | CDN | Client-side routing between the six app views |

---

## 3. Domain Model

### Key Entities

#### Vocab

A single Japanese vocabulary item, as stored in the database. Mapped from JMdict with JLPT level applied via overlay.

```python
class Vocab(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    word: str                      # Surface form (e.g., 食べる)
    reading: str                   # Hiragana/katakana reading (e.g., たべる)
    meaning: str                   # English gloss (e.g., "to eat")
    part_of_speech: str            # e.g., "verb", "noun", "adjective"
    jlpt_level: JLPTLevel          # Enum: N5, N4, N3, N2, N1
    example_jp: str | None         # Example sentence in Japanese
    example_en: str | None         # Example sentence in English
```

#### Kanji

A single Jōyō kanji entry, sourced from KANJIDIC2.

```python
class Kanji(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    character: str = Field(unique=True)      # Single kanji (e.g., 日)
    on_yomi: list[str] = Field(sa_column=Column(JSONB))   # e.g., ["ニチ", "ジツ"]
    kun_yomi: list[str] = Field(sa_column=Column(JSONB))  # e.g., ["ひ", "か"]
    meaning: list[str] = Field(sa_column=Column(JSONB))   # e.g., ["day", "sun", "Japan"]
    stroke_count: int
    jlpt_level: JLPTLevel | None             # None for kanji with no JLPT tag
    freq_rank: int | None                    # Newspaper frequency rank (1 = most common)
    example_word: str | None                 # e.g., 日本語
    example_sentence: str | None             # e.g., 日本語を勉強しています
```

#### SRSCard

The memory record for a single learnable item. One row per (item_type, item_id) pair. Created the first time a user is introduced to an item.

```python
class SRSCard(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    item_type: ItemType            # Enum: "vocab" | "kanji"
    item_id: int                   # FK to vocab.id or kanji.id
    ease_factor: float = 2.5       # Multiplier for interval growth (min: 1.3)
    interval_days: int = 1         # Days until next review
    reps: int = 0                  # Total successful reviews (0 = new card)
    due_date: date                 # Next review date (date, not datetime)
    last_reviewed: datetime | None # Timestamp of most recent review
```

#### ReviewLog

Append-only log of every review action. Never modified after insertion.

```python
class ReviewLog(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    session_id: int = Field(foreign_key="studysession.id")
    card_id: int = Field(foreign_key="srscard.id")
    grade: int                     # 0–5 (SM-2 scale)
    reviewed_at: datetime = Field(default_factory=datetime.utcnow)
```

#### StudySession

A single contiguous review session opened when the user starts a flashcard session and closed when they finish or navigate away.

```python
class StudySession(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    started_at: datetime
    ended_at: datetime | None
    cards_reviewed: int = 0
    correct: int = 0               # Grade >= 3
    incorrect: int = 0             # Grade <= 2
```

#### Meta

Flat key-value store for user configuration and application state.

```python
class Meta(SQLModel, table=True):
    key: str = Field(primary_key=True)    # e.g., "jlpt_focus", "new_cards_per_day"
    value: str                             # JSON-serialized value
```

Default meta values set by seed:

| key | default value | description |
|---|---|---|
| `jlpt_focus` | `"N5"` | Current JLPT level for card selection and tutor context |
| `new_cards_per_day` | `"20"` | Maximum new cards introduced per calendar day |
| `db_version` | `"jlpt-db-v1.0.0"` | Seed pipeline version for reproducibility |
| `build_date` | ISO date string | Date the database was seeded |

### API Response Models

Separate from table models, these Pydantic classes shape HTTP responses:

```python
class VocabResponse(SQLModel):
    id: int
    word: str
    reading: str
    meaning: str
    part_of_speech: str
    jlpt_level: str
    example_jp: str | None
    example_en: str | None
    srs_state: SRSCardSummary | None   # None if card not yet created

class KanjiDetailResponse(SQLModel):
    id: int
    character: str
    on_yomi: list[str]
    kun_yomi: list[str]
    meaning: list[str]
    stroke_count: int
    jlpt_level: str | None
    freq_rank: int | None
    example_word: str | None
    example_sentence: str | None
    srs_state: SRSCardSummary | None

class SRSCardSummary(SQLModel):
    ease_factor: float
    interval_days: int
    reps: int
    due_date: date

class ReviewRequest(SQLModel):
    card_id: int
    grade: int     # 0–5

class ReviewResponse(SQLModel):
    card: SRSCardSummary
    next_due: date
    session_correct: int
    session_incorrect: int

class LevelStats(SQLModel):
    level: str
    new: int           # Items with no srs_cards row
    young: int         # interval_days < 21
    mature: int        # interval_days >= 21
    due_today: int
    total: int

class ProgressResponse(SQLModel):
    streak_days: int
    level_stats: list[LevelStats]
    weekly_forecast: list[ForecastDay]   # Cards due each day for next 7 days
    all_time_accuracy: float             # correct / total across review_log

class TutorRequest(SQLModel):
    message: str
    mode: TutorMode    # Enum: TEACH | QUIZ | EXPLAIN | CORRECT
    level: str         # e.g., "N5"
```

### Data Transformations

| Stage | Input | Transformation | Output |
|---|---|---|---|
| JMdict parse | `JMdict_e.xml.gz` | XML parse → filter to JLPT-tagged entries → apply level overlay JSON → extract word/reading/meaning/example | `data/jmdict_parsed.json` |
| KANJIDIC2 parse | `kanjidic2.xml.gz` | XML parse → extract character/on/kun/meaning/stroke/grade/freq | `data/kanjidic_parsed.json` |
| DB seed | `jmdict_parsed.json` + `kanjidic_parsed.json` | INSERT via SQLModel session with `ON CONFLICT DO NOTHING` | `vocab` + `kanji` tables in PostgreSQL |
| Flashcard review | `ReviewRequest(card_id, grade)` | SM-2 algorithm → updated `SRSCard` → write `ReviewLog` row | `ReviewResponse` with next_due date |
| Tutor chat | `TutorRequest(message, mode, level)` | Assemble system prompt + context injection → POST to Ollama → stream chunks | SSE `text/event-stream` chunks |
| TTS synthesis | `{ text: str }` | Write text to Piper stdin → read WAV bytes from stdout | `audio/wav` response bytes |
| Progress query | `GET /api/progress` | Aggregate queries on `srs_cards`, `review_log`, `study_sessions` | `ProgressResponse` with forecast |

### Important Invariants

1. **`review_log` is append-only.** Rows are never updated or deleted. The complete review history is always available for analysis and streak calculation.
2. **One `SRSCard` per (item_type, item_id) pair.** A `UNIQUE(item_type, item_id)` constraint is enforced at the database level. Duplicate card creation is a programming error, not a conflict to be silently ignored.
3. **`due_date` is a `date`, not a `datetime`.** Reviews scheduled within the same calendar day are equivalent. This matches Anki's behavior and avoids timezone-dependent bugs in interval calculation.
4. **`ease_factor` has a hard floor of 1.3.** Enforced by `core/srs.py` after every grade-0 or grade-1 review. A card can become harder to schedule but never enters an infinite loop with a zero or negative ease factor.
5. **New card intake is capped per calendar day.** The `new_cards_per_day` meta value is checked in `get_new_cards()` by counting `SRSCard` rows created today. Existing due cards are never rate-limited.
6. **The AI tutor never writes to the database.** `routers/tutor.py` is a read-only consumer of the `meta` and `srs_cards` tables (for context injection). It has no write permissions to any table. All state mutations go through `routers/cards.py` and `core/srs.py`.
7. **Piper TTS is always called on UTF-8 Japanese text.** The route handler validates that the input text is non-empty and within 500 characters before spawning the subprocess; longer texts are rejected with HTTP 400.

---

## 4. Execution Flow

### Flashcard Review Lifecycle

```mermaid
sequenceDiagram
    participant UI as Flashcards View<br/>(Vue 3)
    participant API as FastAPI<br/>routers/cards.py
    participant SRS as core/srs.py<br/>SM-2 Engine
    participant DB as PostgreSQL

    UI->>API: GET /api/cards/due?level=N5&type=vocab&limit=20
    API->>DB: SELECT srs_cards JOIN vocab WHERE due_date <= today AND level = N5
    DB-->>API: List[SRSCard + Vocab]
    API-->>UI: DueCardsResponse {cards: [...]}

    loop For each card
        UI->>UI: Show card front (word)
        UI->>UI: User taps card — flip to back (reading + meaning + example)
        UI->>API: POST /api/tts {text: "食べる"}
        API->>API: core/tts_piper.py: spawn Piper subprocess
        API-->>UI: audio/wav bytes
        UI->>UI: Play pronunciation audio

        UI->>UI: User selects grade: Again(0) / Hard(2) / Good(3) / Easy(5)
        UI->>API: POST /api/cards/review {card_id: 42, grade: 3}
        API->>SRS: review(card, grade=3)
        SRS->>SRS: new_ease = max(1.3, ease + 0.1*(grade - 3.0) - 0.08)
        SRS->>SRS: new_interval = round(interval * new_ease)
        SRS->>SRS: new_due = today + timedelta(days=new_interval)
        SRS-->>API: Updated SRSCard

        API->>DB: UPDATE srs_cards SET ease_factor, interval_days, due_date, last_reviewed
        API->>DB: INSERT INTO review_log (session_id, card_id, grade, reviewed_at)
        API->>DB: UPDATE study_sessions SET cards_reviewed, correct/incorrect
        DB-->>API: OK
        API-->>UI: ReviewResponse {card: {...}, next_due: "2026-03-05"}

        UI->>UI: Animate card out, show next due card
    end

    UI->>UI: Session complete screen — show correct/incorrect summary
    UI->>API: PATCH /api/sessions/{id} {ended_at: now()}
```

### AI Tutor Chat (SSE Streaming)

```mermaid
sequenceDiagram
    participant UI as AI Tutor View<br/>(Vue 3)
    participant API as FastAPI<br/>routers/tutor.py
    participant TUTOR as core/tutor.py
    participant META as PostgreSQL<br/>(meta + srs_cards)
    participant OLLAMA as Ollama<br/>LLaMA3.1 70B

    UI->>API: POST /api/tutor/chat {message: "...", mode: "QUIZ", level: "N5"}
    API->>META: SELECT value FROM meta WHERE key IN ('jlpt_focus')
    META-->>API: {jlpt_focus: "N5"}
    API->>META: SELECT recent 10 reviewed items from review_log JOIN vocab
    META-->>API: ["食べる", "飲む", "見る", ...]
    API->>META: SELECT 5 weakest cards (ORDER BY ease_factor ASC LIMIT 5)
    META-->>API: [{word: "聞く", ease: 1.4}, ...]

    API->>TUTOR: stream_response(message, mode=QUIZ, context={...})
    TUTOR->>TUTOR: Build system prompt with tutor persona + no-translation rule
    TUTOR->>TUTOR: Inject JLPT level, recently studied words, weak cards
    TUTOR->>TUTOR: Append mode block: "Generate a fill-in-the-blank quiz using the learner's studied vocab"

    TUTOR->>OLLAMA: POST /api/generate {model: "llama3.1:70b", stream: true, ...}

    loop SSE stream
        OLLAMA-->>TUTOR: {"response": "では、", "done": false}
        TUTOR-->>API: yield "では、"
        API-->>UI: data: では、\n\n

        OLLAMA-->>TUTOR: {"response": "次の文を完成させてください", "done": false}
        TUTOR-->>API: yield "次の文を完成させてください"
        API-->>UI: data: 次の文を完成させてください\n\n
    end

    OLLAMA-->>TUTOR: {"response": "", "done": true}
    TUTOR-->>API: return (generator exhausted)
    API-->>UI: data: [DONE]\n\n
    UI->>UI: Render full message with ruby furigana HTML; scroll to bottom
```

### Application Startup Sequence

```mermaid
sequenceDiagram
    participant UV as uvicorn
    participant APP as main.py<br/>FastAPI lifespan
    participant ALB as alembic
    participant DB as PostgreSQL
    participant OLL as Ollama

    UV->>APP: Start application
    APP->>APP: Load config.py (BaseSettings reads .env)
    APP->>DB: Test connection (asyncpg ping)
    DB-->>APP: Connected

    APP->>ALB: alembic upgrade head
    ALB->>DB: SELECT version_num FROM alembic_version
    DB-->>ALB: "0003_sessions_and_meta"
    ALB->>DB: Run migration 0004_indexes.py
    DB-->>ALB: Migration applied
    ALB-->>APP: Schema at head

    APP->>OLL: GET localhost:11434/api/tags (health check)
    OLL-->>APP: {models: ["llama3.1:70b"]}

    APP->>APP: Verify PIPER_MODEL_PATH exists on disk
    APP->>APP: Register all APIRouter blueprints
    APP->>APP: Mount /static, serve templates/index.html at /

    APP-->>UV: Application ready
    UV->>UV: Serving at http://localhost:8000
```

### Shutdown Sequence

1. `Ctrl+C` / `SIGTERM` → uvicorn begins graceful shutdown
2. FastAPI lifespan `finally` block executes:
   - Any open `StudySession` rows with `ended_at = NULL` are closed with `ended_at = now()`
   - `AsyncSession` pool is disposed
3. `asyncpg` connection pool drains open connections
4. Piper subprocess (if active) receives `SIGTERM`, completes current WAV write
5. Uvicorn exits with code 0

---

## 5. SM-2 Spaced-Repetition Engine

### Overview

The SM-2 algorithm (Wozniak, 1987) is the scheduling backbone of early Anki and remains the most empirically validated open spaced-repetition algorithm. It models human long-term memory using two parameters per item: **ease factor** (how easily the learner remembers it) and **interval** (how many days until the next review is needed).

### Algorithm

Given a card with current state `(ease_factor E, interval I, reps n)` and a user-assigned grade `q` in `{0, 1, 2, 3, 4, 5}`:

**Step 1 — Update ease factor:**

$$E' = \max\!\bigl(1.3,\; E + 0.1 - (5 - q)(0.08 + (5 - q) \cdot 0.02)\bigr)$$

**Step 2 — Update interval:**

$$I' = \begin{cases}
1 & \text{if } q < 3 \text{ (failure)} \\
1 & \text{if } n = 0 \text{ (first successful review)} \\
6 & \text{if } n = 1 \text{ (second successful review)} \\
\text{round}(I \cdot E') & \text{if } n \geq 2 \text{ (subsequent reviews)}
\end{cases}$$

**Step 3 — Set due date:**

$$\text{due\_date} = \text{today} + I' \text{ days}$$

**Step 4 — Update reps:**
- If `q < 3`: reset `reps = 0` (card goes back to "new" state)
- If `q >= 3`: increment `reps += 1`

### Grade Scale

| Grade | Label | Meaning | Action |
|---|---|---|---|
| 0 | Blackout | Complete failure, didn't recognize | Reset interval to 1, ease drops sharply |
| 1 | Wrong | Recognized but couldn't recall | Reset interval to 1, ease drops |
| 2 | Hard | Recalled with significant effort | Interval unchanged, ease drops slightly |
| 3 | Good | Recalled with some effort (default) | Interval × ease, ease unchanged |
| 4 | Easy | Recalled quickly with little effort | Interval × ease × 1.3, ease increases |
| 5 | Very Easy | Instantly and effortlessly recalled | Interval × ease × 1.3, ease increases more |

The UI presents four buttons: **Again (0)**, **Hard (2)**, **Good (3)**, **Easy (5)**. Grades 1 and 4 are not surfaced to the user to reduce cognitive load during review.

### Card Lifecycle

```
┌─────────────────────────────────────────────────────────────────────┐
│                         SM-2 Card Lifecycle                         │
│                                                                     │
│  [New]                                                              │
│   No srs_cards row yet. Returned by get_new_cards().                │
│   Introduced up to new_cards_per_day new items per day.             │
│         │                                                           │
│         │ First review (any grade)                                  │
│         ▼                                                           │
│  [Learning / Young]                                                 │
│   srs_cards row exists. reps < threshold. interval_days < 21.       │
│   Seen again tomorrow (grade >= 3) or today again (grade < 3).      │
│         │                                                           │
│         │ interval_days >= 21 (reps accumulate)                    │
│         ▼                                                           │
│  [Mature]                                                           │
│   interval_days >= 21. Reviews spaced weeks to months apart.        │
│   Ease factor has stabilized based on recall performance.           │
│         │                                                           │
│         │ Grade <= 1 at any point                                   │
│         ▼                                                           │
│  [Lapsed]                                                           │
│   reps reset to 0, interval reset to 1. Card re-enters Learning.   │
└─────────────────────────────────────────────────────────────────────┘
```

### Due Card Query

```sql
SELECT srs_cards.*, vocab.*
FROM srs_cards
JOIN vocab ON srs_cards.item_id = vocab.id
WHERE srs_cards.item_type = 'vocab'
  AND vocab.jlpt_level = :level
  AND srs_cards.due_date <= CURRENT_DATE
ORDER BY srs_cards.due_date ASC
LIMIT :limit;
```

Cards overdue by the most days are prioritized (earliest `due_date` first).

### New Card Intake Control

```python
async def get_new_cards(session, level, item_type, limit) -> list[Vocab | Kanji]:
    # Count cards already created today to enforce daily cap
    cap = int(await get_meta(session, "new_cards_per_day"))
    created_today = await count_cards_created_today(session)
    remaining_cap = max(0, cap - created_today)
    effective_limit = min(limit, remaining_cap)

    # Select items with no existing srs_cards row
    stmt = (
        select(Vocab)
        .where(Vocab.jlpt_level == level)
        .where(~exists().where(SRSCard.item_id == Vocab.id,
                               SRSCard.item_type == "vocab"))
        .limit(effective_limit)
    )
    ...
```

---

## 6. AI Tutor Engine

### Design Principles

The AI tutor's single most important constraint is: **it is not a translator**. This is enforced architecturally, not just by instruction — the system prompt contains an explicit, top-priority prohibition on providing translations on demand. The tutor deflects translation requests with a pedagogically useful response ("Let's approach this differently — what does this word remind you of?") and continues in tutor mode.

The tutor operates like a human language tutor: it uses English to scaffold understanding, but always grounds explanations in Japanese examples. It assumes the learner's Japanese ability matches their stated JLPT level, and adjusts vocabulary used in examples accordingly.

### System Prompt Architecture

```
┌──────────────────────────────────────────────────────────────────────┐
│                        System Prompt (per request)                   │
│                                                                      │
│ [1. Persona block — static]                                          │
│    "You are a Japanese language tutor named Sensei. You help         │
│     learners with JLPT N5–N1. You explain grammar in English,        │
│     always provide Japanese examples with furigana in <ruby> tags.   │
│     You NEVER provide direct translations on demand. Translation     │
│     requests must be redirected to active learning exercises."       │
│                                                                      │
│ [2. Context injection — dynamic per request]                         │
│    "The learner's current focus: {jlpt_level}"                       │
│    "Recently studied words: {recent_10_words}"                       │
│    "Words needing reinforcement: {5_weakest_cards}"                  │
│                                                                      │
│ [3. Mode instruction block — dynamic per request]                    │
│    TEACH:   "Introduce one grammar point appropriate for {level}..."  │
│    QUIZ:    "Generate a fill-in-the-blank using one of the recently  │
│              studied words. Provide 4 options, mark the answer..."   │
│    EXPLAIN: "The learner is asking about: {user_message}. Explain    │
│              thoroughly with on-yomi, kun-yomi, and a real sentence."│
│    CORRECT: "The learner wrote: {user_message}. Check for grammar,   │
│              particle, and conjugation errors. Explain each issue."  │
│                                                                      │
│ [4. User message]                                                    │
│    {user_message}                                                    │
└──────────────────────────────────────────────────────────────────────┘
```

### Interaction Modes

| Mode | Trigger | Tutor Behavior | DB Read |
|---|---|---|---|
| `TEACH` | User opens tutor or presses "Teach me something new" | Introduces one grammar point or word class at the learner's JLPT level, with a dialogue example and usage notes | `meta.jlpt_focus` |
| `QUIZ` | User presses "Quiz Me" | Generates one fill-in-the-blank or multiple-choice question using the learner's recently studied vocabulary | `review_log + vocab + meta` |
| `EXPLAIN` | User types a kanji, word, or grammar point | Deep-dives: etymology, on/kun-yomi, three usage examples, common mistakes | `meta.jlpt_focus` |
| `CORRECT` | User pastes/types a Japanese sentence | Identifies errors (particle, conjugation, word order, register), explains each, offers the corrected sentence, does not just re-translate | `meta.jlpt_focus + recent vocab` |

### Streaming Implementation

```python
# core/tutor.py
async def stream_response(
    message: str,
    mode: TutorMode,
    context: TutorContext,
    model: str = "llama3.1:70b",
    ollama_base_url: str = "http://localhost:11434",
) -> AsyncGenerator[str, None]:

    system_prompt = build_system_prompt(mode, context)

    async with httpx.AsyncClient(timeout=None) as client:
        async with client.stream(
            "POST",
            f"{ollama_base_url}/api/generate",
            json={
                "model": model,
                "system": system_prompt,
                "prompt": message,
                "stream": True,
            },
        ) as response:
            async for line in response.aiter_lines():
                if not line:
                    continue
                chunk = json.loads(line)
                if token := chunk.get("response"):
                    yield token
                if chunk.get("done"):
                    return
```

```python
# routers/tutor.py
@router.post("/chat")
async def tutor_chat(
    request: TutorRequest,
    session: AsyncSession = Depends(get_session),
) -> StreamingResponse:
    context = await build_context(session, request.level)

    async def event_stream():
        async for token in tutor.stream_response(
            request.message, request.mode, context
        ):
            yield f"data: {json.dumps({'token': token})}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")
```

### Furigana Rendering

The tutor is instructed to wrap all kanji with furigana in HTML `<ruby>` tags:

```
食<ruby>たべ</ruby>る  →  rendered as 食 with たべ above it
```

The Vue frontend renders tutor messages using `v-html` on a sanitized string. A DOMPurify allowlist permits only `<ruby>`, `<rb>`, `<rt>`, `<rp>`, `<br>`, `<strong>`, `<em>` — all other tags are stripped before rendering.

---

## 7. Key Design Decisions

### Why This Architecture Exists

The system is built around a single principle: **every component that could require a network connection has an offline replacement**. Students study on planes, during commutes, in areas with poor connectivity. No feature degrades silently to "requires internet" — Ollama is local, Piper is local, PostgreSQL is local, and all JLPT data is pre-seeded.

### Trade-offs Visible in the Design

| Decision | Trade-off | Rationale |
|---|---|---|
| **FastAPI over Flask** | More initial setup (lifespan, routers, async patterns) | Native async required for simultaneous SSE streaming + DB queries; auto-generated `/docs` removes manual API documentation burden; Pydantic validation eliminates entire classes of input bugs |
| **PostgreSQL over SQLite** | Requires a running Postgres process (Docker recommended) | JSONB for on/kun-yomi arrays enables native containment queries; concurrent async writes from multiple browser tabs work correctly; matches production-quality tooling expectations; Alembic is better-supported against Postgres |
| **SQLModel over SQLAlchemy + Pydantic separately** | SQLModel is less mature; some edge cases require raw SQLAlchemy | Eliminates `schemas.py` / `models.py` duplication; single source of truth for column definitions, validation rules, and API response shapes; significantly reduces boilerplate |
| **Alembic for migrations vs. `SQLModel.metadata.create_all()`** | Alembic requires explicit migration scripts | `create_all()` cannot add columns to existing tables, cannot seed data, and cannot be rolled back. Alembic provides a complete audit trail of every schema change |
| **SM-2 over Anki's newer FSRS algorithm** | FSRS is more accurate for mature learners | SM-2 is simpler, has a 35-year track record, is deterministic and easy to test. FSRS requires 50+ reviews per card to outperform SM-2. FSRS can be added as a future migration |
| **LLaMA3.1 70B over LLaMA3 8B** | Requires ~40 GB RAM or ~20 GB VRAM with Q4 quantization | 8B models have poor Japanese grammar accuracy, frequently code-switch to English mid-explanation, and fail at generating JLPT-appropriate quizzes. 70B is the minimum for reliable Japanese language tutoring quality |
| **Piper TTS over gTTS** | ~80 MB voice model to download; slightly more complex setup | gTTS requires an internet connection for every audio request — incompatible with offline-first requirement; Piper is deterministic (same input = same output), enabling future audio caching |
| **Vue 3 CDN over React/Next.js/Vite** | Less ecosystem tooling, no tree-shaking | Zero build step means contributors can edit a `.js` file and refresh; no `node_modules`; no webpack config; appropriate for an app where the backend is the complex part |
| **mBART-50 translator removed** | Earlier prototype feature lost | Reinforces the tutor-not-translator identity at the architecture level; frees ~2 GB RAM and eliminates 30-second cold-start from model loading; transformers/torch removed from dependencies |
| **JMdict + KANJIDIC2 over curated JSON bundles** | Requires a one-time parse pipeline | JMdict has 196k entries (comprehensive); KANJIDIC2 has all 2136 Jōyō kanji with full metadata; both are CC BY-SA licensed; both are used by Jisho.org and other professional tools. Curated bundles become stale |

### Scalability Considerations

- **Single user.** The system is a personal language tutor with a single PostgreSQL database and no authentication. Multi-user support would require schema changes (user_id foreign keys on all tables), session isolation, and an auth layer.
- **Card counts are bounded.** N5 has ~800 vocab + 100 kanji; N1 has ~10,000 vocab + 2000 kanji. Total seeded items are ~15,000 vocab + 2136 kanji. SM-2 queries over this dataset are sub-millisecond with the indexes in migration `0004`.
- **LLaMA3.1 70B is the bottleneck.** A single Ollama instance processes one generation at a time. The SSE stream starts within 2–5 seconds of request due to first-token latency. Concurrent tutor sessions would queue behind each other — acceptable for a single-user app.
- **Piper TTS latency scales with text length.** Short words (1–3 chars) synthesize in ~100ms; full example sentences (~20 chars) in ~400ms. For longer texts, the route applies a 500-character cap.

### Observability Patterns

| Pattern | Implementation |
|---|---|
| **Review accuracy tracking** | Every `ReviewLog` row stores the grade; aggregate queries in `progress` router compute per-level accuracy at any time |
| **Streak calculation** | Query `review_log` grouped by `DATE(reviewed_at)` for the longest unbroken daily chain |
| **7-day review forecast** | `SELECT due_date, COUNT(*) FROM srs_cards WHERE due_date BETWEEN today AND today+7 GROUP BY due_date` |
| **Weak card identification** | `SELECT * FROM srs_cards ORDER BY ease_factor ASC LIMIT 20` — injected into tutor context |
| **API health** | `GET /api/health` returns `{db: ok, ollama: ok, piper: ok}` by probing each dependency |
| **Alembic state** | `GET /api/health` also returns `{schema_version: "0004_indexes"}` from `alembic_version` table |

---

## 8. Failure & Edge Case Analysis

### Where Failures May Occur

```mermaid
flowchart TD
    A[User opens app] -->|PostgreSQL not running| B[⚠ CRITICAL: 500 on all DB routes]
    A --> C[Dashboard loads]
    C -->|No due cards| D[Show 'All caught up!' screen<br/>Offer new cards instead]
    C --> E[User starts flashcard review]
    E -->|Ollama not running| F[⚠ Tutor tab shows error banner<br/>Flashcards unaffected]
    E --> G[User submits grade]
    G -->|DB connection drops mid-write| H[⚠ Transaction rolled back<br/>Card remains at previous state<br/>User shown error toast]
    G --> I[SRS card updated]
    I -->|ease_factor below 1.3| J[Clamped to 1.3 by srs.py]
    E --> K[User taps TTS button]
    K -->|Piper binary missing| L[⚠ TTS unavailable banner<br/>Card still usable without audio]
    K -->|Text over 500 chars| M[HTTP 400: text too long]
    K --> N[WAV audio plays]
    C --> O[User opens AI Tutor]
    O --> P[User sends message]
    P -->|LLaMA3.1 70B not pulled| Q[⚠ Ollama returns 404 model error<br/>Shown as error message in chat]
    P -->|Ollama timeout over 120s| R[⚠ SSE stream closes with error event<br/>Partial response already shown]
    P --> S[Tutor responds via SSE stream]

    style B fill:#e74c3c,color:#fff
    style H fill:#f39c12,color:#fff
    style F fill:#f39c12,color:#fff
    style L fill:#f39c12,color:#fff
    style Q fill:#f39c12,color:#fff
    style R fill:#f39c12,color:#fff
```

### Error Handling Strategy

| Layer | Failure Mode | Strategy | Severity |
|---|---|---|---|
| **Database** | PostgreSQL not reachable at startup | Log CRITICAL; lifespan raises `RuntimeError`; uvicorn exits; user sees instructions to start Postgres | CRITICAL |
| **Database** | Connection dropped during review write | Transaction rolled back atomically; HTTP 503 returned; Vue shows toast "Review not saved, please try again"; card state unchanged | MEDIUM |
| **Database** | `srs_cards` UNIQUE constraint violation (duplicate card creation) | HTTP 409 returned; frontend ignores and proceeds to next card | LOW |
| **Alembic** | Migration fails (e.g., column already exists from manual change) | Startup aborts; log shows failing migration version; user must manually resolve with `alembic stamp head` | HIGH |
| **Ollama** | Not running at startup | Logged as WARNING; app starts normally; tutor routes return HTTP 503 with `{"detail": "AI tutor unavailable — Ollama is not running"}` | MEDIUM |
| **Ollama** | Model `llama3.1:70b` not pulled | HTTP 503 with message including `ollama pull llama3.1:70b` instruction | MEDIUM |
| **Ollama** | Generation timeout (>120 seconds) | `httpx` raises `ReadTimeout`; SSE stream sends `{"error": "Response timed out"}` event; frontend displays error in chat | MEDIUM |
| **Ollama** | Malformed JSON chunk in stream | `json.loads` exception caught per-chunk; chunk skipped; stream continues | LOW |
| **Piper TTS** | Binary not found at configured path | HTTP 503 with message; TTS button disabled in frontend; all other features unaffected | LOW |
| **Piper TTS** | Subprocess returns non-zero exit code | WAV bytes discarded; HTTP 500 returned; error logged with stderr output | LOW |
| **Piper TTS** | Input text > 500 characters | HTTP 400 `{"detail": "Text exceeds 500 character limit"}`; frontend trims text before sending | LOW |
| **Data Seed** | `tools/seed.py` interrupted mid-run | Idempotent — re-running re-inserts only missing rows; no duplicates due to `ON CONFLICT DO NOTHING` | LOW |
| **JMdict download** | Network unavailable during `tools/fetch_jmdict.py` | Script exits with error; cached file from previous successful run is used if present | MEDIUM |
| **Vue Frontend** | `/api/cards/due` returns empty list | UI shows "Great work! No cards due right now" with CTA to study new cards | LOW |
| **Vue Frontend** | SSE connection dropped by browser (tab background) | EventSource auto-reconnects; duplicate `[DONE]` events are deduplicated by the message handler | LOW |

### Recovery Hierarchy

```
Priority 1: Flashcard review must always be available. The SRS scheduler,
            card display, and grade submission must work even if Ollama,
            Piper, and the internet are all unavailable simultaneously.

Priority 2: Audio pronunciation is a learning aid, not a requirement.
            A card without audio is still a functional flashcard.

Priority 3: The AI tutor enhances learning but is not the core loop.
            Its unavailability degrades experience but does not block progress.

Priority 4: Progress statistics are informational. Stale stats are
            preferable to a crashed app. Stats routes can return
            cached data when DB aggregate queries are slow.
```

### Potential Technical Debt

| Issue | Impact | Mitigation Path |
|---|---|---|
| **No user authentication** | Single-user only; unsuitable for family or classroom use | Add FastAPI Users or Auth0 integration; add `user_id` FK to all session/card tables |
| **SM-2 ease factor does not differentiate reading vs. meaning recognition** | A learner might know meaning but not reading; single ease factor conflates both | Split each item into two card sides (front=word→reading, front=word→meaning); independent ease factors |
| **Piper spawned as subprocess per request** | 50–200ms process spawn overhead per TTS call | Use Piper's HTTP server mode (available in Piper >= 1.3) to keep the model warm between calls |
| **LLaMA3.1 70B hardware requirement** | Inaccessible to users with < 16 GB RAM | Add `OLLAMA_MODEL` config option; document smaller alternatives (gemma2:27b, qwen2.5:14b) with quality trade-offs |
| **JLPT level assignments from overlay JSON may be incomplete** | Some JMdict entries legitimately lack JLPT tags | Add a `jlpt_level = NULL` bucket in the UI as "general vocabulary"; allow manual level assignment |
| **No audio caching** | Piper spawned per request; repeated words (e.g., N5 core vocab) incur repeated synthesis cost | Write WAV bytes to `static/audio_cache/{sha256_of_text}.wav` on first synthesis; serve static file on cache hit |
| **Vue 3 CDN dependency** | App requires internet on first load to fetch Vue CDN | Bundle Vue and Vue Router into `static/js/vendor/`; ship with the repo |

---

## 9. Data Pipeline

### Source Datasets

| Dataset | Provider | License | Size | Contents |
|---|---|---|---|---|
| JMdict_e.xml.gz | Electronic Dictionary Research and Development Group (edrdg.org) | CC BY-SA 4.0 | ~20 MB compressed | ~196,000 Japanese-English dictionary entries; includes JLPT level tags on a subset |
| kanjidic2.xml.gz | EDRDG | CC BY-SA 4.0 | ~7 MB compressed | 2136 Jōyō + 6355 additional kanji; on-yomi, kun-yomi, meanings, stroke count, JLPT grade, frequency rank |
| jlpt-vocab overlay | Community-maintained JSON (GitHub: `jlpt-vocab`) | MIT | ~500 KB | Maps ~15,000 word/reading pairs to N5–N1 JLPT levels; supplements JMdict's incomplete JLPT tagging |

### Pipeline Steps

```mermaid
flowchart LR
    subgraph Download ["tools/fetch_*.py (one-time)"]
        DL1[Download JMdict_e.xml.gz<br/>~20 MB]
        DL2[Download kanjidic2.xml.gz<br/>~7 MB]
        DL3[Download jlpt-vocab overlay<br/>~500 KB JSON]
    end

    subgraph Parse ["tools/fetch_*.py (parse)"]
        P1[lxml XML parse<br/>→ vocab list dicts]
        P2[lxml XML parse<br/>→ kanji list dicts]
    end

    subgraph Cache ["data/ (cached JSON)"]
        C1[data/jmdict_parsed.json]
        C2[data/kanjidic_parsed.json]
        C3[data/jlpt_overlay.json]
    end

    subgraph Seed ["tools/seed.py"]
        S1[Apply JLPT level overlay<br/>to jmdict entries]
        S2[Filter: keep only entries<br/>with jlpt_level assigned]
        S3[INSERT vocab rows<br/>ON CONFLICT DO NOTHING]
        S4[INSERT kanji rows<br/>ON CONFLICT DO NOTHING]
        S5[UPDATE meta table<br/>db_version + build_date]
    end

    subgraph DB ["PostgreSQL 16"]
        T1[(vocab<br/>~15,000 rows)]
        T2[(kanji<br/>~2,136 rows)]
        T3[(meta<br/>5 rows)]
    end

    DL1 --> P1 --> C1
    DL2 --> P2 --> C2
    DL3 --> C3

    C1 --> S1
    C3 --> S1
    S1 --> S2 --> S3 --> T1
    C2 --> S4 --> T2
    S5 --> T3
```

### Idempotency Guarantee

`tools/seed.py` is designed to be re-runnable at any time without data corruption:

```python
# All INSERT statements use conflict handling:
stmt = insert(Vocab).values(rows).on_conflict_do_nothing(index_elements=["word", "reading"])
await session.execute(stmt)

stmt = insert(Kanji).values(rows).on_conflict_do_nothing(index_elements=["character"])
await session.execute(stmt)

# Meta is upserted, not inserted:
stmt = insert(Meta).values(key="db_version", value="jlpt-db-v1.0.0")
stmt = stmt.on_conflict_do_update(index_elements=["key"], set_={"value": stmt.excluded.value})
await session.execute(stmt)
```

### Alembic Migration Chain

```
alembic/versions/
├── 0001_initial_schema.py        → CREATE TABLE vocab, kanji
├── 0002_srs_cards.py             → CREATE TABLE srs_cards
├── 0003_sessions_and_meta.py     → CREATE TABLE review_log, study_sessions, meta
│                                    INSERT default meta rows (jlpt_focus, new_cards_per_day)
└── 0004_indexes.py               → CREATE INDEX ON vocab(jlpt_level)
                                     CREATE INDEX ON kanji(jlpt_level)
                                     CREATE INDEX ON srs_cards(due_date)
                                     CREATE INDEX ON srs_cards(ease_factor)
                                     CREATE INDEX ON review_log(reviewed_at)
                                     CREATE GIN INDEX ON kanji(on_yomi, kun_yomi)
```

Each migration has a matching `downgrade()` function that fully reverses the `upgrade()` step.

---

## 10. Frontend Dashboard

### Overview

A **Vue 3 + Vue Router** single-page application loaded from a single HTML shell (`templates/index.html`). Vue 3 and Vue Router are loaded from CDN links in the `<head>`. No npm, no webpack, no build step — a contributor can open any `static/js/views/*.js` file and edit it with an immediate browser refresh reflecting the change.

The app communicates with the FastAPI backend exclusively via `fetch()` calls (JSON for all routes except `/api/tts` which returns bytes, and `/api/tutor/chat` which uses `EventSource` for SSE).

### Application Shell

```html
<!-- templates/index.html (stripped) -->
<script src="https://unpkg.com/vue@3/dist/vue.esm-browser.prod.js" type="module"></script>
<script src="https://unpkg.com/vue-router@4/dist/vue-router.esm-browser.js" type="module"></script>
<script src="/static/js/app.js" type="module"></script>

<nav>
  <!-- Tab bar: Dashboard · Flashcards · Vocabulary · Kanji · Tutor · Progress -->
  <router-link to="/">Dashboard</router-link>
  ...
</nav>
<router-view></router-view>
```

### Views

#### Dashboard (`static/js/views/Dashboard.js`)

The landing page and daily study entry point.

| Section | Data Source | Purpose |
|---|---|---|
| Streak counter | `GET /api/progress` → `streak_days` | Motivational daily habit tracker |
| Due cards by level | `GET /api/cards/due?limit=1` per level (count only) | See how many cards are waiting at each JLPT level |
| "Start Review" CTA | Routes to `/flashcards` | Primary daily action |
| JLPT level completion bars | `GET /api/progress` → `level_stats[].mature / total` | Shows mastery percentage per level |
| Recently learned carousel | `GET /api/vocab?recently_reviewed=true&limit=10` | Reinforces context for recently-introduced words |

#### Flashcards (`static/js/views/Flashcards.js`)

The core SRS review interface.

- **Level tabs:** N5 · N4 · N3 · N2 · N1 (synced to `meta.jlpt_focus` on load)
- **Type toggle:** Vocabulary / Kanji
- **Card front:** Displays the word (vocab) or kanji character; shows reading in small text if user has enabled "show reading hint"
- **Card flip:** Click/tap or spacebar → reveals reading + meaning + example sentence with furigana `<ruby>` rendered
- **TTS button (both sides):** Calls `POST /api/tts`, plays returned WAV via Web Audio API
- **Grade buttons:** Again · Hard · Good · Easy — trigger `POST /api/cards/review`
- **Progress bar:** `{cards_reviewed} / {total_due}` for current session
- **Session summary:** Shown after last card — correct %, time taken, streak update

#### Vocabulary Browser (`static/js/views/VocabBrowser.js`)

A searchable, paginated reference for all vocabulary.

- **Level tabs:** N5–N1
- **Search bar:** Debounced `GET /api/vocab?q={query}` — searches both Japanese and English fields
- **Vocab card:** Word (large), reading in hiragana, English meaning, JLPT badge, example sentence (Japanese + English), TTS button, "Add to queue" button (creates `SRSCard` if not yet studied)
- **Pagination:** 50 items per page; next/prev buttons call `GET /api/vocab?page={n}`

#### Kanji Browser (`static/js/views/KanjiBrowser.js`)

A grid of all Jōyō kanji, filterable by JLPT level.

- **Grid view:** Each cell shows the kanji character large, with stroke count and JLPT badge
- **Click → Detail modal:**

```
┌─────────────────────────────────┐
│       日          N5  ■■■■□     │  ← character, JLPT, stroke indicator
│                                 │
│  音読み (On-yomi):  ニチ · ジツ   │
│  訓読み (Kun-yomi): ひ · -か      │
│                                 │
│  Meanings: day, sun, Japan      │
│                                 │
│  Example: 日本語 (にほんご)        │
│  日本語を毎日勉強しています。        │
│                                 │
│  [▶ Hear it]  [Add to review]   │
└─────────────────────────────────┘
```

#### AI Tutor (`static/js/views/Tutor.js`)

Chat interface with the LLaMA3.1 70B tutor.

- **Mode selector:** 4 buttons — Free Chat / Quiz Me / Explain / Correct My Japanese
- **JLPT level badge:** Shows current focus level; click to change (writes to `meta`)
- **Message input:** Submit on Enter (Shift+Enter for newline)
- **Chat history:** Scrollable, with auto-scroll to bottom on new content
- **Streaming:** Uses `EventSource` pointed at the SSE endpoint; tokens appended to the last message div as they arrive
- **Furigana rendering:** Tutor message HTML is sanitized with DOMPurify then inserted with `v-html`; `<ruby>` tags render inline furigana
- **Error state:** If SSE returns `{"error": "..."}`, displays a red banner in the chat

#### Progress (`static/js/views/Progress.js`)

Analytics and motivation view.

- **Streak calendar:** 90-day GitHub-style contribution grid (`canvas`-based); dark cells = days with reviews
- **Accuracy by level:** Horizontal bar chart (`canvas`); shows `correct / total` per JLPT level from `review_log`
- **Maturity breakdown:** Stacked bar per level: new (grey) / young (yellow) / mature (green)
- **7-day forecast:** Line chart showing how many cards are due each day this week — data from `GET /api/progress` → `weekly_forecast`

---

## 11. Developer Onboarding Guide

### Prerequisites

| Requirement | Version | Notes |
|---|---|---|
| Python | 3.10+ | Via `pixi` (environment defined in `pixi.toml`) |
| PostgreSQL | 16+ | Docker recommended: `docker run -d -p 5432:5432 -e POSTGRES_PASSWORD=postgres postgres:16` |
| Ollama | Latest | [ollama.com/download](https://ollama.com/download); pull model after install |
| LLaMA3.1 70B | via Ollama | ~40 GB RAM or ~20 GB VRAM (Q4 quantized). Alternative: `qwen2.5:14b` for less powerful hardware |
| Piper TTS | >= 1.3 | Binary and voice model downloaded by `tools/setup.py` |
| Git | Any | |
| OS | Windows 10/11, macOS, or Linux | Windows users: Ollama runs natively; Piper available as Windows binary |

### Repository Structure

```
AI-Japanese-Language-App/
├── ARCHITECTURE.md               # This document
├── README.md                     # Quick-start guide
├── requirements.txt              # Python dependencies (pip-pinned)
├── pixi.toml                     # pixi lockfile-based environment definition
├── pixi.lock                     # Locked dependency versions
├── .env.example                  # Template for .env (copy and fill in)
│
├── main.py                       # FastAPI app entry point + lifespan
├── config.py                     # Pydantic BaseSettings (reads .env)
│
├── models/
│   ├── __init__.py
│   ├── vocab.py                  # Vocab SQLModel table + JLPTLevel enum
│   ├── kanji.py                  # Kanji SQLModel table
│   ├── srs.py                    # SRSCard, ReviewLog, StudySession SQLModel tables
│   └── meta.py                   # Meta SQLModel table
│
├── database/
│   ├── db.py                     # Async engine factory + get_session() dependency
│   └── schema.sql                # Reference-only SQL (canonical source is Alembic)
│
├── alembic/
│   ├── env.py                    # Alembic environment config (uses async engine)
│   ├── script.py.mako            # Migration file template
│   └── versions/
│       ├── 0001_initial_schema.py
│       ├── 0002_srs_cards.py
│       ├── 0003_sessions_and_meta.py
│       └── 0004_indexes.py
│
├── core/
│   ├── srs.py                    # SM-2 algorithm (pure Python, no DB dependency)
│   ├── tutor.py                  # Ollama streaming client + prompt builder
│   └── tts_piper.py              # Piper TTS asyncio subprocess wrapper
│
├── routers/
│   ├── cards.py                  # GET /api/cards/due|new, POST /api/cards/review
│   ├── vocab.py                  # GET /api/vocab, GET /api/vocab/{id}
│   ├── kanji.py                  # GET /api/kanji, GET /api/kanji/{char}
│   ├── tutor.py                  # POST /api/tutor/chat (SSE)
│   ├── tts.py                    # POST /api/tts
│   ├── progress.py               # GET /api/progress
│   ├── settings.py               # GET/POST /api/settings
│   └── health.py                 # GET /api/health
│
├── tools/
│   ├── setup.py                  # First-run orchestrator (checks deps, runs Alembic, seeds)
│   ├── fetch_jmdict.py           # Download + parse JMdict XML
│   ├── fetch_kanjidic.py         # Download + parse KANJIDIC2 XML
│   └── seed.py                   # Insert vocab + kanji into PostgreSQL
│
├── data/
│   ├── jmdict_parsed.json        # Cached JMdict parse output (generated by tools/)
│   ├── kanjidic_parsed.json      # Cached KANJIDIC2 parse output (generated by tools/)
│   └── jlpt_overlay.json         # Community JLPT level assignments (bundled in repo)
│
├── templates/
│   └── index.html                # Vue 3 SPA shell (CDN imports, router-view)
│
├── static/
│   ├── js/
│   │   ├── app.js                # Vue app init + Vue Router config
│   │   └── views/
│   │       ├── Dashboard.js
│   │       ├── Flashcards.js
│   │       ├── VocabBrowser.js
│   │       ├── KanjiBrowser.js
│   │       ├── Tutor.js
│   │       └── Progress.js
│   ├── css/
│   │   └── app.css               # Global styles (CSS variables, dark mode, card animations)
│   └── piper/
│       ├── ja_JP-kokoro-medium.onnx   # Piper voice model (~80 MB, downloaded by setup.py)
│       └── ja_JP-kokoro-medium.json  # Voice model config
│
└── tests/
    ├── test_srs.py               # SM-2 algorithm unit tests (grade transitions, edge cases)
    ├── test_cards_router.py      # FastAPI TestClient tests for /api/cards/*
    ├── test_vocab_router.py      # FastAPI TestClient tests for /api/vocab/*
    ├── test_kanji_router.py      # FastAPI TestClient tests for /api/kanji/*
    ├── test_progress_router.py   # FastAPI TestClient tests for /api/progress
    ├── test_seed.py              # Idempotency test for tools/seed.py
    └── conftest.py               # Shared fixtures: test DB, async session, sample data
```

### Environment Variables (`.env`)

```dotenv
# Database
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/jlpt_trainer

# Ollama
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama3.1:70b

# Piper TTS
PIPER_MODEL_PATH=static/piper/ja_JP-kokoro-medium.onnx
PIPER_BINARY_PATH=piper

# SRS defaults (can also be changed at runtime via /api/settings)
NEW_CARDS_PER_DAY=20

# App
APP_HOST=127.0.0.1
APP_PORT=8000
LOG_LEVEL=INFO
```

### Installation

**Step 1: Clone and configure environment**

```bash
git clone <repository-url>
cd AI-Japanese-Language-App
cp .env.example .env
# Edit .env — set DATABASE_URL, confirm Piper/Ollama paths
```

**Step 2: Install Python dependencies**

```bash
# Option A: pixi (recommended — fully reproducible)
pixi install
pixi shell

# Option B: pip virtualenv
python -m venv .venv
.venv\Scripts\activate          # Windows
pip install -r requirements.txt
```

**Step 3: Start PostgreSQL**

```bash
# Docker (recommended)
docker run -d --name jlpt-postgres \
  -e POSTGRES_USER=postgres \
  -e POSTGRES_PASSWORD=postgres \
  -e POSTGRES_DB=jlpt_trainer \
  -p 5432:5432 \
  postgres:16
```

**Step 4: Start Ollama and pull the model**

```bash
# Install Ollama from https://ollama.com/download
ollama serve                          # Start Ollama daemon (may auto-start on install)
ollama pull llama3.1:70b              # ~40 GB download — do this before running setup

# For lower-spec machines:
ollama pull qwen2.5:14b               # ~9 GB, good Japanese quality
# Then set OLLAMA_MODEL=qwen2.5:14b in .env
```

**Step 5: Run first-time setup**

```bash
python tools/setup.py
```

This script:
1. Verifies PostgreSQL connection
2. Verifies Ollama is running and the configured model is pulled
3. Checks for Piper binary and downloads voice model if missing
4. Runs `alembic upgrade head`
5. Runs `tools/seed.py` (parses JMdict + KANJIDIC2, seeds database)
6. Prints `uvicorn main:app --reload` to start

**Step 6: Start the application**

```bash
uvicorn main:app --reload
# Open http://localhost:8000
# Open http://localhost:8000/docs for the API explorer
```

### Quick Verification Checklist

| Check | Command / URL | Expected Result |
|---|---|---|
| API health | `GET /api/health` | `{db: "ok", ollama: "ok", piper: "ok", schema_version: "0004_indexes"}` |
| Kanji detail | `GET /api/kanji/日` | on_yomi: `["ニチ", "ジツ"]`, kun_yomi: `["ひ", "か"]`, example: `日本語` |
| Vocab count | `GET /api/vocab?level=N5&page=1` | ~800 N5 vocabulary entries |
| Card review | `POST /api/cards/review {card_id: 1, grade: 3}` | `{next_due: "<date>"}` with interval > 1 if reps > 0 |
| TTS audio | `POST /api/tts {text: "日本語"}` | Audio/WAV bytes; plays correctly in browser |
| Tutor stream | `POST /api/tutor/chat {message: "Explain に", mode: "EXPLAIN", level: "N5"}` | SSE stream with Japanese examples and furigana |
| Alembic history | `alembic history` | Shows 4 revisions, `(head)` on `0004_indexes` |

### Running Tests

```bash
# All tests (requires test database configured in conftest.py)
pytest tests/ -v

# SRS algorithm only (no DB required)
pytest tests/test_srs.py -v

# With coverage report
pytest tests/ --cov=. --cov-report=html
open htmlcov/index.html
```

### How to Add a New Feature

**Adding a new JLPT content field (e.g., `antonyms` to `Vocab`):**

1. Add the column to `models/vocab.py` SQLModel class.
2. Write a new Alembic migration: `alembic revision -m "add_vocab_antonyms"`. Implement `upgrade()` with `op.add_column()` and `downgrade()` with `op.drop_column()`.
3. Update `tools/seed.py` to extract and insert the new field from parsed JMdict data.
4. Update `VocabResponse` in `models/vocab.py` to include the new field.
5. Update `VocabBrowser.js` to display the new field.
6. Add a test to `tests/test_vocab_router.py` asserting the field is returned by `GET /api/vocab/{id}`.

**Swapping to a different LLM (e.g., `qwen2.5:14b`):**

1. Set `OLLAMA_MODEL=qwen2.5:14b` in `.env`.
2. Run `ollama pull qwen2.5:14b`.
3. Restart the app. No code changes required.

**Adding a new SRS card type (e.g., grammar points):**

1. Add `grammar` to the `ItemType` enum in `models/srs.py`.
2. Create a new `Grammar` SQLModel table (migration `0005_grammar.py`).
3. Seed grammar points from a new data source in `tools/seed.py`.
4. Add `routers/grammar.py` following the same pattern as `routers/vocab.py`.
5. Register the router in `main.py`.
6. Add a "Grammar" tab to `Flashcards.js` following the existing N5–N1 tab pattern.

---

## 12. Security & Operational Considerations

### Input Validation

| Check | Status | Gap |
|---|---|---|
| All API request bodies validated | Pydantic (via SQLModel) on all POST routes | None — Pydantic raises HTTP 422 with field-level error messages on invalid input |
| TTS text length cap | Enforced in `routers/tts.py` at 500 characters | No Unicode category check — Piper handles non-Japanese gracefully (outputs silence) |
| `grade` field in review endpoint | Validated as `int` in range 0–5 by Pydantic `Field(ge=0, le=5)` | None |
| Kanji character lookup | URL path parameter validated as single Unicode character | Multi-character strings return HTTP 404 (no match), not an error |
| `.env` loaded via Pydantic `BaseSettings` | Type-validated with defaults | `DATABASE_URL` may contain credentials in logs if debug logging is enabled |

### Dependency Security

| Component | Risk | Mitigation |
|---|---|---|
| **Ollama / LLaMA3.1** | Model weights are binary files; source cannot be audited | Pull only from official `ollama.com` registry; verify model hash after pull |
| **JMdict / KANJIDIC2** | Downloaded over HTTPS from edrdg.org; XML parsing uses `lxml` | `lxml` is not vulnerable to billion-laughs via external entity injection by default; parsing is one-time at setup |
| **Piper binary** | Downloaded from GitHub releases | Verify SHA-256 of binary against published checksums in `tools/setup.py` before execution |
| **Vue 3 CDN** | CDN compromise would inject JavaScript into the app | Pin CDN URLs to a fixed version hash (SRI: `integrity="sha384-..."`) |

### Operational Considerations

| Concern | Approach |
|---|---|
| **PostgreSQL data persistence** | If using Docker, always mount a named volume (`-v jlpt-data:/var/lib/postgresql/data`) to survive container restarts |
| **Database backup** | Run `pg_dump jlpt_trainer > backup.sql` periodically; `srs_cards` and `review_log` tables contain all learning progress |
| **LLaMA3.1 70B RAM requirement** | Monitor RAM; Ollama will swap to disk if insufficient physical RAM, causing very slow responses (>60s) |
| **Piper model storage** | The `.onnx` file is ~80 MB; excluded from git (`.gitignore`); re-downloaded by `tools/setup.py` |
| **FastAPI runs on localhost only** | `APP_HOST=127.0.0.1` by default; change to `0.0.0.0` only if network access is needed (LAN tutoring sessions) |
| **No rate limiting** | Single-user local app; no rate limiting needed. If exposed to network, add `slowapi` middleware |

---

## 13. Suggested Improvements

### High (Learning Quality / Correctness)

| Issue | Risk | Fix |
|---|---|---|
| **Single ease factor per card** | Reading and meaning recall are separate skills; one metric conflates them | Split each vocab item into `word→reading` and `word→meaning` card types; independent SM-2 scheduling |
| **No audio caching** | Piper spawned per request; repeated words (e.g., N5 core vocab) incur repeated synthesis cost | Write WAV bytes to `static/audio_cache/{sha256_of_text}.wav` on first synthesis; serve static file on cache hit |
| **SM-2 not calibrated for kanji complexity** | Kanji with 3+ readings (e.g., 生) may need slower initial intervals | Apply a `complexity_factor` multiplier to the initial interval based on reading count + stroke count |
| **FSRS algorithm not implemented** | SM-2 is less accurate than FSRS for mature learners (>100 reviews) | Implement FSRS-4.5 as an alternative scheduler; expose choice in settings |

### Medium (Reliability / UX)

| Issue | Impact | Fix |
|---|---|---|
| **Vue CDN requires internet on first load** | App doesn't load offline until Vue is cached | Bundle Vue + Vue Router into `static/js/vendor/`; serve locally from FastAPI |
| **No graceful LLM fallback** | If Ollama is not running, the entire tutor tab shows an error | Implement a fallback to pre-written tutor interactions (rule-based Q&A from a JSON dataset) for offline-only mode |
| **No undo on grade submission** | Fat-finger on "Again" when meaning "Good" permanently affects scheduling | Add a 3-second undo window after grade submission before the write is committed |
| **No dark mode** | Extended study sessions cause eye strain | Add CSS custom properties for light/dark toggle; respect `prefers-color-scheme` media query |
| **No keyboard shortcuts in flashcard view** | Must tap/click for every review action | Map `Space` = flip, `1`/`2`/`3`/`4` = grade buttons |

### Low (Code Quality / DevEx)

| Issue | Impact | Fix |
|---|---|---|
| **No mypy strict mode** | Runtime type errors possible in async DB code | Add `mypy --strict` to CI; SQLModel 0.0.14+ has improved type stubs |
| **No integration tests for Ollama streaming** | Tutor SSE stream only tested with mock in unit tests | Add `pytest-asyncio` integration test with a real Ollama instance (mark as `@pytest.mark.integration`) |
| **Alembic `env.py` uses sync engine workaround** | SQLAlchemy async + Alembic requires a sync shim; boilerplate-heavy | Standardize on Alembic's `run_async_migrations()` pattern from official docs |
| **`data/jmdict_parsed.json` not committed** | Fresh clone requires running `tools/fetch_jmdict.py` before seeding | Pre-parse and commit a filtered `data/n5_n4_parsed.json` (~1 MB) to eliminate the download step for common JLPT levels |

### Architecture Evolution Path

```mermaid
graph LR
    A["Current:<br/>Single-user<br/>local tutor<br/>SM-2 + LLaMA"] --> B["Add FSRS<br/>algorithm as<br/>alternative scheduler"]
    B --> C["Multi-side cards<br/>(reading / meaning<br/>independent SRS)"]
    C --> D["Audio caching +<br/>Piper HTTP server<br/>mode"]
    D --> E["Auth + multi-user<br/>classroom support"]
    E --> F["Mobile PWA<br/>(offline service worker,<br/>WebAssembly Piper)"]

    style A fill:#4a9eff,color:#fff
    style B fill:#e67e22,color:#fff
    style C fill:#e67e22,color:#fff
    style D fill:#95a5a6,color:#fff
    style E fill:#95a5a6,color:#fff
    style F fill:#95a5a6,color:#fff
```

---

## Appendix A: SM-2 Mathematical Reference

### Ease Factor Update

$$E' = \max\!\bigl(1.3,\; E + 0.1 - (5 - q)(0.08 + (5 - q) \cdot 0.02)\bigr)$$

Expanded per grade:

| Grade $q$ | $\Delta E$ | New ease (starting from $E = 2.5$) |
|---|---|---|
| 5 (Very Easy) | $+0.10$ | 2.60 |
| 4 (Easy) | $+0.00$ | 2.50 |
| 3 (Good) | $-0.14$ | 2.36 |
| 2 (Hard) | $-0.32$ | 2.18 |
| 1 (Wrong) | $-0.54$ | 1.96 |
| 0 (Blackout) | $-0.80$ | 1.70 |

### Interval Calculation

For a card with interval $I$ and updated ease $E'$:

$$I' = \begin{cases}
1 & \text{if } q < 3 \\
1 & \text{if reps} = 0 \\
6 & \text{if reps} = 1 \\
\operatorname{round}(I \cdot E') & \text{if reps} \geq 2
\end{cases}$$

### Interval Growth Example (perfect recalls, grade = 3)

Starting from $E = 2.5$, consistent grade 3 (Good):

| Review | Interval | Due in |
|---|---|---|
| 1st | 1 day | tomorrow |
| 2nd | 6 days | next week |
| 3rd | 6 × 2.36 = 14 days | 2 weeks |
| 4th | 14 × 2.36 = 33 days | ~1 month |
| 5th | 33 × 2.36 = 78 days | ~3 months |
| 6th | 78 × 2.36 = 184 days | ~6 months |

This matches the observed memory consolidation curve for long-term retention. A card reviewed 6 times with consistent recall needs only one more review in 6 months — total study time under 5 minutes for a word retained for life.

---

## Appendix B: Glossary

| Term | Definition |
|---|---|
| **JLPT** | Japanese Language Proficiency Test — the internationally recognized standard for Japanese certification, with levels N5 (beginner) through N1 (near-native). |
| **N5–N1** | JLPT proficiency levels. N5 is the most elementary (~800 vocabulary), N1 the most advanced (~10,000 vocabulary). Progression is N5 → N4 → N3 → N2 → N1. |
| **SRS** | Spaced Repetition System — a study method that schedules review of material at increasing intervals based on how well the learner remembers it. |
| **SM-2** | SuperMemo 2 — the spaced repetition algorithm developed by Piotr Wozniak in 1987, used as the basis for Anki's scheduling. |
| **Ease Factor** | An SM-2 parameter per card (default 2.5, floor 1.3) that scales how quickly the review interval grows. A low ease factor means a hard card reviewed more frequently. |
| **Interval** | The number of days until a card's next scheduled review. Grows exponentially on correct recall, resets to 1 on failure. |
| **Due Date** | The calendar date on which an SRS card should next be reviewed. Cards past their due date are overdue and shown first. |
| **Mature Card** | An SRS card whose current interval is >= 21 days. Indicates the item is well-consolidated in long-term memory. |
| **Young Card** | An SRS card with interval < 21 days. Still in the active learning phase. |
| **On-yomi (音読み)** | The Chinese-derived reading(s) of a kanji, traditionally used in compound words. Written in katakana. Example: 日 → ニチ, ジツ. |
| **Kun-yomi (訓読み)** | The native Japanese reading(s) of a kanji, used when the kanji stands alone or in native Japanese words. Written in hiragana. Example: 日 → ひ, か. |
| **Furigana** | Small hiragana text written above kanji to indicate pronunciation. Rendered in HTML with `<ruby>` tags. |
| **Jōyō Kanji** | The 2136 kanji designated by the Japanese government as the standard for general use in print media and education. |
| **Ollama** | A local LLM runtime that serves language models (LLaMA, Qwen, Gemma, etc.) via an HTTP API on the local machine, with no cloud dependency. |
| **LLaMA3.1 70B** | Meta's 70-billion-parameter language model, run locally via Ollama. Recommended minimum model quality for reliable Japanese language tutoring. |
| **Piper TTS** | A fast, lightweight, offline text-to-speech engine that uses ONNX voice models. Used here for Japanese pronunciation synthesis. |
| **Alembic** | SQLAlchemy's database migration tool. Tracks schema changes as versioned Python scripts, enabling reproducible, reversible schema evolution. |
| **SQLModel** | A Python library that combines SQLAlchemy ORM table definitions and Pydantic data validation into a single class hierarchy. |
| **asyncpg** | A high-performance, fully asynchronous PostgreSQL driver for Python, used via SQLAlchemy's async engine. |
| **SSE** | Server-Sent Events — a one-way HTTP streaming protocol where the server pushes `text/event-stream` chunks to the browser. Used here to stream AI tutor responses token-by-token. |
| **JMdict** | The Japanese-Multilingual Dictionary — a comprehensive, open-licensed Japanese-English electronic dictionary maintained by the EDRDG. |
| **KANJIDIC2** | The Kanji Dictionary — an open-licensed XML database of Japanese kanji with readings, meanings, stroke counts, and JLPT grades, maintained by the EDRDG. |
| **FSRS** | Free Spaced Repetition Scheduler — a modern algorithm (2022) that outperforms SM-2 for learners with many mature cards. Listed as a future improvement. |
| **DOMPurify** | A JavaScript HTML sanitizer. Used in the Vue tutor view to sanitize AI-generated HTML before inserting it with `v-html`, preventing XSS. |
| **JSONB** | PostgreSQL's binary JSON column type. Supports GIN indexing and containment operators, used here for `on_yomi` and `kun_yomi` arrays. |
