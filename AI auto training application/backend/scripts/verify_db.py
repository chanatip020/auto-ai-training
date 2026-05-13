"""Quick connectivity + schema check for Supabase Postgres.

Run after `alembic upgrade head` to confirm the schema is in place:

    python scripts/verify_db.py
"""
from __future__ import annotations

import asyncio

from sqlalchemy import text

from app.db import engine


EXPECTED_TABLES = {"users", "projects", "audit_log", "alembic_version"}
EXPECTED_ENUMS = {"project_status", "model_family", "task_type"}


async def main() -> None:
    async with engine.connect() as conn:
        version = (await conn.execute(text("select version()"))).scalar_one()
        print(f"Connected. Postgres: {version.split(',')[0]}")

        rows = await conn.execute(
            text(
                "select table_name from information_schema.tables "
                "where table_schema = 'public'"
            )
        )
        tables = {r[0] for r in rows}
        missing_t = EXPECTED_TABLES - tables
        print(f"Tables found: {sorted(tables)}")
        if missing_t:
            print(f"  MISSING: {sorted(missing_t)}")

        rows = await conn.execute(
            text(
                "select t.typname from pg_type t "
                "join pg_namespace n on n.oid = t.typnamespace "
                "where n.nspname = 'public' and t.typtype = 'e'"
            )
        )
        enums = {r[0] for r in rows}
        missing_e = EXPECTED_ENUMS - enums
        print(f"Enums found: {sorted(enums)}")
        if missing_e:
            print(f"  MISSING: {sorted(missing_e)}")

        rev = (
            await conn.execute(text("select version_num from alembic_version"))
        ).scalar_one_or_none()
        print(f"Alembic head: {rev}")

        if missing_t or missing_e:
            print("\nSchema NOT fully applied. Run: alembic upgrade head")
        else:
            print("\nAll good. Schema is in place.")


if __name__ == "__main__":
    asyncio.run(main())
