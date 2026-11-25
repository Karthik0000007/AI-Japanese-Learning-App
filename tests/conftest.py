"""tests/conftest.py — Shared async fixtures for the test suite."""
import os

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlmodel import SQLModel

# ── Use a dedicated test database ────────────────────────────────────────────
# Needs a running PostgreSQL with an existing, empty database. Override the URL
# with TEST_DATABASE_URL (see "Running tests" in README.md).
TEST_DB_URL = os.getenv(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://postgres:postgres@localhost:5432/jlpt_trainer_test",
)

os.environ.setdefault("DATABASE_URL", TEST_DB_URL)
os.environ.setdefault("OLLAMA_BASE_URL", "http://localhost:11434")
os.environ.setdefault("PIPER_BINARY", "piper")

# Import app after env vars are set
from database.db import get_session  # noqa: E402
from main import app  # noqa: E402

test_engine = create_async_engine(TEST_DB_URL, echo=False)
TestingSession = sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)


@pytest_asyncio.fixture(scope="session")
async def create_test_tables():
    async with test_engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.drop_all)
    await test_engine.dispose()


@pytest_asyncio.fixture()
async def session(create_test_tables):
    async with TestingSession() as s:
        yield s
        await s.rollback()


@pytest_asyncio.fixture()
async def client(session):
    async def override_get_session():
        yield session

    app.dependency_overrides[get_session] = override_get_session
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()


@pytest_asyncio.fixture()
async def db_conn(create_test_tables):
    """A raw connection inside a transaction that is rolled back after the test."""
    async with test_engine.connect() as conn:
        trans = await conn.begin()
        yield conn
        await trans.rollback()
