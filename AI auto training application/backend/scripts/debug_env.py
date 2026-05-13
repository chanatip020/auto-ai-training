"""Print exactly which DATABASE_URL the app is loading and where it came from.

Run from the backend/ folder:

    python scripts/debug_env.py

Why this exists: 'Tenant or user not found' from PgBouncer means the app is
still pointed at the pooler. This script answers:

  1. Which .env file is being read?
  2. What DATABASE_URL is in that file?
  3. Is a process-level env var overriding it?
  4. What does the app's typed Settings object actually load?
"""
from __future__ import annotations

import os
import re
import sys
from pathlib import Path


def _redact(url: str) -> str:
    return re.sub(r"://([^:]+):([^@]+)@", r"://\1:****@", url)


def main() -> None:
    cwd = Path.cwd()
    print(f"cwd: {cwd}")

    env_path = cwd / ".env"
    print(f"Looking for .env at: {env_path}  (exists: {env_path.exists()})")

    if env_path.exists():
        print()
        print(f".env  DATABASE_URL line(s):")
        any_match = False
        for i, line in enumerate(env_path.read_text(encoding="utf-8").splitlines(), 1):
            stripped = line.lstrip()
            if stripped.startswith("DATABASE_URL"):
                marker = "  <- ACTIVE" if not stripped.startswith("#") else "  (commented)"
                print(f"  line {i}: {_redact(line)}{marker}")
                any_match = True
        if not any_match:
            print("  (no DATABASE_URL line found)")

    print()
    proc_url = os.environ.get("DATABASE_URL")
    if proc_url:
        print(f"PROCESS env DATABASE_URL is SET — this OVERRIDES .env:")
        print(f"  {_redact(proc_url)}")
        print("  Unset it for this shell:  Remove-Item Env:DATABASE_URL")
    else:
        print("PROCESS env DATABASE_URL: (not set — good)")

    print()
    # Now ask the app what it actually resolved.
    sys.path.insert(0, str(cwd))
    try:
        from app.config import settings
    except Exception as e:
        print(f"Could not import app.config.settings: {e}")
        print("Are you running from the backend/ folder?")
        return

    url = settings.DATABASE_URL
    print(f"app.config.settings.DATABASE_URL (what the API actually uses):")
    print(f"  {_redact(url)}")

    # Sanity check the host/port.
    m = re.search(r"@([^:/]+):(\d+)/", url)
    if m:
        host, port = m.group(1), m.group(2)
        print()
        print(f"  host: {host}")
        print(f"  port: {port}")
        if "pooler.supabase.com" in host:
            print()
            print("  ⚠ This is the POOLER host. Migrations should use the DIRECT host.")
            print("    Direct host format:  db.<project-ref>.supabase.co  port 5432")
            print("    User on pooler MUST be 'postgres.<project-ref>', not 'postgres'.")
        elif "db." in host and host.endswith("supabase.co"):
            print()
            print("  ✓ This is the DIRECT host. Good for migrations.")


if __name__ == "__main__":
    main()
