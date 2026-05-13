"""Async SQLAlchemy engine + session factory."""
from __future__ import annotations

from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings


# When connecting via Supabase's transaction pooler (PgBouncer in transaction
# mode), asyncpg's prepared-statement cache must be disabled or you'll hit
# "prepared statement '__asyncpg_stmt_…' already exists" after the first batch.
# It's harmless to disable globally on a small app, so we always set it.
_pgbouncer_safe_connect_args: dict[str, object] = {"statement_cache_size": 0}

engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10,
    connect_args=_pgbouncer_safe_connect_args,
)

SessionLocal: async_sessionmaker[AsyncSession] = async_sessionmaker(
    engine,
    expire_on_commit=False,
    autoflush=False,
)


async def get_session() -> AsyncIterator[AsyncSession]:
    """FastAPI dependency yielding an async DB session.

    Commits on success, rolls back on exception, always closes.
    """
    async with SessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
