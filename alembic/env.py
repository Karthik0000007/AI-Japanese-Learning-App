"""
alembic/env.py — Run migrations using the same asyncpg URL as the FastAPI app.
Alembic requires a *synchronous* connection for its internal bookkeeping, so we
use the run_sync pattern recommended in the official Alembic async docs.
"""
import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

# Import all models so their metadata is registered before Alembic introspects it
import models  # noqa: F401  (registers all table classes via side-effect)
from config import settings
from sqlmodel import SQLModel

# Alembic Config object — gives access to values in alembic.ini
config = context.config

# Override sqlalchemy.url with the value from settings (reads .env)
config.set_main_option("sqlalchemy.url", settings.database_url)

# Set up python logging from alembic.ini's [loggers] section
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# All SQLModel tables are registered in this metadata object
target_metadata = SQLModel.metadata


def run_migrations_offline() -> None:
    """Emit SQL to stdout without a live DB connection."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Create an async engine and run migrations through a sync shim."""
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
