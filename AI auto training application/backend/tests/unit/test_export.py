"""Unit tests for dataset-version export streaming."""
from __future__ import annotations

import io
import zipfile
from pathlib import Path

import pytest

from app.core.errors import AppError
from app.services.datasets.export import (
    stream_directory_as_zip,
    suggested_filename,
)


def _make_converted_tree(root: Path) -> None:
    """Lay out a tiny YOLO-det-shaped folder on disk."""
    for split in ("train", "val", "test"):
        (root / "images" / split).mkdir(parents=True)
        (root / "labels" / split).mkdir(parents=True)
    (root / "images" / "train" / "a.jpg").write_bytes(b"\xff\xd8\xff\xd9")  # fake jpg
    (root / "images" / "val" / "b.jpg").write_bytes(b"\xff\xd8\xff\xd9")
    (root / "labels" / "train" / "a.txt").write_text("0 0.5 0.5 0.1 0.1\n")
    (root / "labels" / "val" / "b.txt").write_text("")  # background frame
    (root / "data.yaml").write_text(
        "path: .\ntrain: images/train\nval: images/val\nnames: [cat]\n"
    )


def test_stream_directory_as_zip_includes_full_tree(tmp_path: Path) -> None:
    _make_converted_tree(tmp_path)

    blob = io.BytesIO()
    for chunk in stream_directory_as_zip(tmp_path):
        blob.write(chunk)
    blob.seek(0)

    with zipfile.ZipFile(blob, "r") as zf:
        names = set(zf.namelist())
        # Forward-slash POSIX paths inside the archive
        assert "data.yaml" in names
        assert "images/train/a.jpg" in names
        assert "images/val/b.jpg" in names
        assert "labels/train/a.txt" in names
        assert "labels/val/b.txt" in names
        # Empty label round-trips correctly (background image)
        assert zf.read("labels/val/b.txt") == b""
        # data.yaml content is preserved
        assert b"names: [cat]" in zf.read("data.yaml")


def test_stream_directory_as_zip_chunked_output_is_valid(tmp_path: Path) -> None:
    """Many tiny files exercise the per-file drain loop."""
    for i in range(20):
        (tmp_path / f"f{i:02d}.txt").write_text(f"hello {i}\n")

    chunks = list(stream_directory_as_zip(tmp_path))
    # We should see incremental output rather than one giant chunk.
    assert len(chunks) > 1
    blob = b"".join(chunks)
    with zipfile.ZipFile(io.BytesIO(blob), "r") as zf:
        assert len(zf.namelist()) == 20
        assert zf.read("f07.txt") == b"hello 7\n"


def test_stream_directory_missing_root_raises(tmp_path: Path) -> None:
    with pytest.raises(AppError) as exc:
        list(stream_directory_as_zip(tmp_path / "does-not-exist"))
    assert exc.value.code == "EXPORT_NO_DATA"


def test_suggested_filename_sanitizes_unsafe_chars() -> None:
    class _DS:
        name = "my dataset / v2!"

    class _V:
        version = 3
        format = "yolo-det"

    fn = suggested_filename(_DS(), _V())
    # No spaces or slashes, valid filename, includes version + format
    assert "/" not in fn and " " not in fn
    assert fn.endswith(".zip")
    assert "v3" in fn
    assert "yolo-det" in fn


def test_suggested_filename_falls_back_when_name_is_unsafe() -> None:
    class _DS:
        name = "///"

    class _V:
        version = 1
        format = "yolo-cls"

    fn = suggested_filename(_DS(), _V())
    assert fn == "dataset_v1_yolo-cls.zip"
