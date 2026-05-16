"""Shared pytest fixtures.

Most tests in this suite are pure-function tests with no DB or filesystem
dependency beyond a tmp_path. Anything that requires a real Postgres lives
under `tests/integration/` and is skipped when DATABASE_URL_TEST is unset.
"""
from __future__ import annotations

import os
import struct
import zlib
from pathlib import Path

import pytest


# ----- env defaults so app.config doesn't refuse to import during collection -----
os.environ.setdefault("API_TOKEN", "test-token-please-change-not-used")
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://test:test@localhost:5432/test")
os.environ.setdefault("STORAGE_BACKEND", "local")
os.environ.setdefault("STORAGE_ROOT", "/tmp/aiat-test-data")


# ----- shared helpers -----
def make_png(width: int = 32, height: int = 32, seed: int = 0) -> bytes:
    """Build a minimal valid grayscale PNG with pseudo-random texture."""
    import random
    rng = random.Random(seed)

    def chunk(tag: bytes, data: bytes) -> bytes:
        return (
            struct.pack(">I", len(data))
            + tag
            + data
            + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
        )

    sig = b"\x89PNG\r\n\x1a\n"
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 0, 0, 0, 0)
    raw = b"".join(
        b"\x00" + bytes(rng.randint(0, 255) for _ in range(width)) for _ in range(height)
    )
    return sig + chunk(b"IHDR", ihdr) + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b"")


@pytest.fixture
def png_bytes() -> bytes:
    """Plain valid PNG bytes for fast tests."""
    return make_png(seed=1)


@pytest.fixture
def fake_yolo_dataset(tmp_path: Path) -> Path:
    """Build a YOLO-detection dataset with 6 train + 2 val + 2 test images."""
    root = tmp_path / "yolo-det"
    for split in ("train", "val", "test"):
        (root / "images" / split).mkdir(parents=True)
        (root / "labels" / split).mkdir(parents=True)
    for i in range(10):
        split = "train" if i < 6 else ("val" if i < 8 else "test")
        (root / "images" / split / f"{i:03d}.png").write_bytes(make_png(seed=i))
        cls = 0 if i < 8 else 1
        (root / "labels" / split / f"{i:03d}.txt").write_text(f"{cls} 0.5 0.5 0.2 0.2\n")
    (root / "data.yaml").write_text(
        f"path: {root}\ntrain: images/train\nval: images/val\ntest: images/test\nnc: 2\nnames: [person, car]\n"
    )
    return root


@pytest.fixture
def fake_raw_dataset(tmp_path: Path) -> Path:
    """A raw (un-converted) YOLO-style upload."""
    root = tmp_path / "raw"
    (root / "images").mkdir(parents=True)
    (root / "labels").mkdir(parents=True)
    for i in range(8):
        (root / "images" / f"{i:03d}.png").write_bytes(make_png(seed=i))
        (root / "labels" / f"{i:03d}.txt").write_text(f"{i % 2} 0.5 0.5 0.2 0.2\n")
    (root / "classes.txt").write_text("person\ncar\n")
    return root


@pytest.fixture
def fake_cls_dataset(tmp_path: Path) -> Path:
    """Raw classification layout: top-level class folders."""
    root = tmp_path / "cls"
    for cls in ("cat", "dog"):
        d = root / cls
        d.mkdir(parents=True)
        for i in range(5):
            (d / f"{cls}_{i}.png").write_bytes(make_png(seed=hash(cls) ^ i))
    return root
