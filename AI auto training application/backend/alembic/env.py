"""Alembic environment.

Reads DATABASE_URL from app.config.settings, swaps the asyncpg driver for the
sync psycopg2 driver alembic prefers, and registers all SQLAlchemy models so
autogenerate works.
"""
from __future__ import annotations

from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

# Import settings + Base so metadata is populated.
from app.config import settings
from app.models.base import Base
from app.models import register_all  # noqa: F401  — side-effect: import all models

config = context.config

# Alembic prefers a sync driver; rewrite asyncpg → psycopg2 just for migrations.
# Also strip any asyncpg-specific query params (e.g. statement_cache_size,
# prepared_statement_cache_size) — psycopg2 rejects unknown kwargs.
sync_url = settings.DATABASE_URL.replace("+asyncpg", "+psycopg2")
if "?" in sync_url:
    sync_url = sync_url.split("?", 1)[0]
config.set_main_option("sqlalchemy.url", sync_url)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=sync_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
