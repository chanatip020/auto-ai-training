"""LocalStorage — filesystem-backed implementation of StorageBackend.

Layout:
    {root}/
        raw/{project_id}/{dataset_id}/{upload_id}/...
        normalized/{project_id}/{dataset_id}/v{n}/...
        runs/{training_job_id}/...
"""
from __future__ import annotations

import asyncio
import shutil
from collections.abc import AsyncIterator
from os import PathLike
from pathlib import Path


class LocalStorage:
    def __init__(self, root: str | PathLike[str]):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    # ---- internal helpers ----
    def _abs(self, key: str) -> Path:
        # Strip any leading slash from the key to keep it relative to root.
        rel = Path(key.lstrip("/"))
        # Guard against path traversal.
        full = (self.root / rel).resolve()
        if not str(full).startswith(str(self.root)):
            raise ValueError(f"Key escapes storage root: {key!r}")
        return full

    # ---- interface methods ----
    async def put_file(self, key: str, src: PathLike[str] | str) -> str:
        dst = self._abs(key)
        dst.parent.mkdir(parents=True, exist_ok=True)
        await asyncio.to_thread(shutil.copyfile, str(src), str(dst))
        return self.to_uri(key)

    async def put_bytes(self, key: str, data: bytes) -> str:
        dst = self._abs(key)
        dst.parent.mkdir(parents=True, exist_ok=True)

        def _write() -> None:
            with open(dst, "wb") as f:
                f.write(data)

        await asyncio.to_thread(_write)
        return self.to_uri(key)

    async def open_read(self, key: str) -> AsyncIterator[bytes]:
        path = self._abs(key)

        async def _gen() -> AsyncIterator[bytes]:
            def _read_chunk(f, n: int) -> bytes:
                return f.read(n)

            f = await asyncio.to_thread(open, path, "rb")
            try:
                while True:
                    chunk = await asyncio.to_thread(_read_chunk, f, 64 * 1024)
                    if not chunk:
                        break
                    yield chunk
            finally:
                await asyncio.to_thread(f.close)

        return _gen()

    async def get_url(self, key: str, *, expires: int = 3600) -> str:  # noqa: ARG002
        # In v1 we don't proxy file downloads through the API; UI fetches
        # via a dedicated /files route (added when needed). For now return
        # the canonical URI so the caller can present *something*.
        return self.to_uri(key)

    async def delete(self, key: str) -> None:
        path = self._abs(key)

        def _rm() -> None:
            if path.is_dir():
                shutil.rmtree(path, ignore_errors=True)
            elif path.exists():
                path.unlink()

        await asyncio.to_thread(_rm)

    async def list_prefix(self, prefix: str) -> list[str]:
        base = self._abs(prefix)
        if not base.exists():
            return []

        def _walk() -> list[str]:
            out: list[str] = []
            for p in base.rglob("*"):
                if p.is_file():
                    out.append(str(p.relative_to(self.root)).replace("\\", "/"))
            return out

        return await asyncio.to_thread(_walk)

    def to_uri(self, key: str) -> str:
        return f"file://{self._abs(key).as_posix()}"

    def local_path(self, key: str) -> Path:
        return self._abs(key)
