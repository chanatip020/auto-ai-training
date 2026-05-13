"""Build a tiny fake YOLO-format dataset and zip it for testing uploads.

Usage:
    python scripts/make_fake_dataset.py [--out fake.zip] [--n 6]

Produces a ZIP with:
    images/{0..n-1}.jpg
    labels/{0..n-1}.txt    (one bbox each)
    classes.txt            (person, car)
"""
from __future__ import annotations

import argparse
import io
import struct
import zipfile
import zlib
from pathlib import Path


def _png_bytes(width: int = 4, height: int = 4) -> bytes:
    """Return a minimal valid PNG (gray gradient)."""
    def chunk(tag: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + tag + data + struct.pack(
            ">I", zlib.crc32(tag + data) & 0xFFFFFFFF
        )

    sig = b"\x89PNG\r\n\x1a\n"
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 0, 0, 0, 0)
    raw = b"".join(b"\x00" + bytes(range(width)) for _ in range(height))
    idat = zlib.compress(raw)
    return sig + chunk(b"IHDR", ihdr) + chunk(b"IDAT", idat) + chunk(b"IEND", b"")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="fake.zip")
    parser.add_argument("--n", type=int, default=6)
    args = parser.parse_args()

    img = _png_bytes()
    out = Path(args.out)

    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("classes.txt", "person\ncar\n")
        for i in range(args.n):
            z.writestr(f"images/{i:03d}.png", img)
            cls = i % 2
            z.writestr(f"labels/{i:03d}.txt", f"{cls} 0.5 0.5 0.2 0.2\n")

    print(f"Wrote {out}  ({out.stat().st_size} bytes, {args.n} images)")


if __name__ == "__main__":
    main()
