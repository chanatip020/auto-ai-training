"""StorageBackend interface.

Every persisted file is referenced by an opaque storage_uri (e.g.
file:///… or s3://…). Business logic never touches filesystem paths
directly — it goes through this interface, so swapping local → MinIO/S3
later is config-only.
"""
from __future__ import annotations

from collections.abc import AsyncIterator
from os import PathLike
from pathlib import Path
from typing import Protocol, runtime_checkable


@runtime_checkable
class StorageBackend(Protocol):
    """Minimal contract for a content-addressable file store.

    All methods are async because S3/MinIO are async; the LocalStorage
    implementation wraps sync filesystem operations in a thread.
    """

    async def put_file(self, key: str, src: PathLike[str] | str) -> str:
        """Copy a local file into the store under ``key``. Returns storage_uri."""

    async def put_bytes(self, key: str, data: bytes) -> str:
        """Write raw bytes into the store under ``key``. Returns storage_uri."""

    async def open_read(self, key: str) -> AsyncIterator[bytes]:
        """Stream bytes from the store. Async generator."""

    async def get_url(self, key: str, *, expires: int = 3600) -> str:
        """Return a URL the caller can fetch the file from.

        For 'local' this is a relative HTTP path served by the API; for S3
        this is a presigned URL.
        """

    async def delete(self, key: str) -> None:
        """Remove the file at ``key``. Idempotent."""

    async def list_prefix(self, prefix: str) -> list[str]:
        """List keys under a prefix (for cleanup, summary, etc.)."""

    def to_uri(self, key: str) -> str:
        """Convert a key to its canonical storage_uri (file:// / s3:// / minio://)."""

    def local_path(self, key: str) -> Path | None:
        """Return a local filesystem Path for ``key`` if the backend has one.

        Local FS returns the absolute Path; remote backends return None.
        Used by code that needs to invoke external tools (e.g. Ultralytics)
        which require a real on-disk path. Callers must fall back to a temp
        download for remote backends.
        """
