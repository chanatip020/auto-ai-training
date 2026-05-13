"""Storage backend factory.

Configured via settings.STORAGE_BACKEND (local | minio | s3). Only 'local' is
wired in v1 — minio/s3 will share the same interface so a future upgrade is
config-only.
"""
from __future__ import annotations

from functools import lru_cache

from app.config import settings
from app.storage.base import StorageBackend
from app.storage.local import LocalStorage


@lru_cache(maxsize=1)
def get_storage() -> StorageBackend:
    backend = settings.STORAGE_BACKEND
    if backend == "local":
        return LocalStorage(root=settings.STORAGE_ROOT)
    # Minio / S3 implementations land in a later phase with the same interface.
    raise NotImplementedError(
        f"STORAGE_BACKEND={backend!r} is reserved for a future phase. "
        f"Use 'local' for v1."
    )


storage: StorageBackend = get_storage()
