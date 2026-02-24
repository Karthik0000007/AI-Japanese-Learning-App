"""
database/db.py — Async SQLAlchemy engine and session factory.

Usage in routes:
    async def my_route(session: AsyncSession = Depends(get_session)):
        ...
"""
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlmodel import SQLModel

from config import settings

# Create the async engine once at import time.
engine = create_async_engine(
    settings.database_url,
    echo=False,          # Set True to log all SQL (useful during development)
    pool_size=5,
    max_overflow=10,
)

# Async session factory
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency that yields one AsyncSession per request."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db() -> None:
    """
    Create all tables that don't exist yet.
    Called during app lifespan AFTER Alembic has run so that
    SQLModel metadata is never ahead of the Alembic-managed schema.
    """
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
