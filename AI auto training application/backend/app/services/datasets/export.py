"""Stream a converted dataset version as a ZIP.

For local storage we walk the on-disk tree (images/, labels/, data.yaml) and
write a Deflate-compressed ZIP into a small in-process buffer, draining it
between files. That keeps memory bounded by the largest single file rather
than the whole dataset, which lets the API safely export multi-GB folders.
"""
from __future__ import annotations

import io
import re
import zipfile
from collections.abc import Iterator
from pathlib import Path
from urllib.parse import urlparse

from app.core.errors import AppError
from app.models.dataset import Dataset, DatasetVersion


def _uri_to_local(uri: str) -> Path:
    p = urlparse(uri)
    if p.scheme != "file":
        raise AppError(
            "EXPORT_NEEDS_LOCAL_STORAGE",
            f"Export requires a local storage backend; got {p.scheme!r}.",
            500,
        )
    return Path(p.path)


class _IterBuffer(io.RawIOBase):
    """Write-only stream buffer we can drain into a chunk iterator."""

    def __init__(self) -> None:
        self._buf = bytearray()

    def writable(self) -> bool:  # pragma: no cover - protocol bookkeeping
        return True

    def write(self, b) -> int:  # type: ignore[override]
        self._buf += bytes(b)
        return len(b)

    def drain(self) -> bytes:
        out = bytes(self._buf)
        self._buf.clear()
        return out


def stream_directory_as_zip(root: Path) -> Iterator[bytes]:
    """Yield ZIP bytes for every file under `root`, draining between files."""
    if not root.exists() or not root.is_dir():
        raise AppError(
            "EXPORT_NO_DATA",
            f"Dataset version folder is missing on disk: {root}",
            404,
        )

    buffer = _IterBuffer()
    with zipfile.ZipFile(buffer, mode="w", compression=zipfile.ZIP_DEFLATED,
                         allowZip64=True) as zf:
        for f in sorted(root.rglob("*")):
            if not f.is_file():
                continue
            arcname = f.relative_to(root).as_posix()
            zf.write(f, arcname=arcname)
            chunk = buffer.drain()
            if chunk:
                yield chunk
    tail = buffer.drain()
    if tail:
        yield tail


_FILENAME_SAFE = re.compile(r"[^A-Za-z0-9._-]+")


def suggested_filename(dataset: Dataset, version: DatasetVersion) -> str:
    """Build a friendly download filename: {dataset}_v{n}_{format}.zip."""
    base = _FILENAME_SAFE.sub("_", dataset.name).strip("_") or "dataset"
    fmt = _FILENAME_SAFE.sub("_", version.format).strip("_") or "export"
    return f"{base}_v{version.version}_{fmt}.zip"
