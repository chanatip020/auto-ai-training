"""Probe the Supabase Postgres host before alembic does, with a clearer error.

Run from backend/:

    python scripts/test_connect.py

What the output tells you:

  - DNS / connection-refused   → project ref wrong, project paused, or
                                 outbound port blocked on your network
  - SCRAM authentication        → DB password wrong (or pooler username
                                 mismatch)
  - 'Tenant or user not found'  → username format wrong for the pooler
  - SUCCESS                    → ready to run alembic upgrade head
"""
from __future__ import annotations

import asyncio
import re
import socket
import sys

import asyncpg

from app.config import settings


def _parse(url: str) -> tuple[str, int, str, str, str]:
    # postgresql+asyncpg://user:pass@host:port/db
    m = re.match(
        r"postgresql(?:\+asyncpg)?://([^:]+):([^@]+)@([^:/]+):(\d+)/([^?]+)",
        url,
    )
    if not m:
        raise ValueError("Could not parse DATABASE_URL")
    return m.group(3), int(m.group(4)), m.group(1), m.group(2), m.group(5)


async def main() -> int:
    host, port, user, password, db = _parse(settings.DATABASE_URL)
    print(f"Target: {host}:{port}  user={user}  db={db}")

    # 1. DNS
    try:
        ip = socket.gethostbyname(host)
        print(f"  DNS:    {host} -> {ip}  ✓")
    except socket.gaierror as e:
        print(f"  DNS:    FAILED ({e})  -- check the project ref in the host name")
        return 1

    # 2. TCP
    try:
        with socket.create_connection((host, port), timeout=5) as s:  # noqa: F841
            print(f"  TCP:    open  ✓")
    except OSError as e:
        print(f"  TCP:    FAILED ({e})")
        if port == 5432:
            print("          Port 5432 may be blocked on your network. "
                  "Switch to the pooler (port 6543) and use username "
                  f"'postgres.<project-ref>'.")
        return 1

    # 3. Authenticated Postgres login
    try:
        conn = await asyncpg.connect(
            host=host, port=port, user=user, password=password, database=db,
            ssl="require", timeout=10,
        )
        ver = await conn.fetchval("select version()")
        await conn.close()
        print(f"  AUTH:   ✓  ({ver.split(',')[0]})")
        print()
        print("All good. You can run:  alembic upgrade head")
        return 0
    except asyncpg.InvalidPasswordError:
        print("  AUTH:   FAILED (invalid password)")
        return 1
    except Exception as e:
        print(f"  AUTH:   FAILED ({type(e).__name__}: {e})")
        return 1


if __name__ == "__main__":
    sys.path.insert(0, ".")
    sys.exit(asyncio.run(main()))
