"""Tests for the dataset-layout detector."""
from __future__ import annotations

from pathlib import Path

from app.services.datasets.detect import detect


def test_detect_empty_dir(tmp_path: Path):
    r = detect(tmp_path)
    assert r.detected_format == "empty"
    assert r.image_count == 0
    assert r.label_count == 0


def test_detect_yolo_format(fake_raw_dataset: Path):
    r = detect(fake_raw_dataset)
    assert r.detected_format == "yolo"
    assert r.image_count == 8
    assert r.label_count == 8
    assert r.classes_hint == ["person", "car"]


def test_detect_yolo_ignores_classes_txt_as_label(fake_raw_dataset: Path):
    # classes.txt sits at root but should NOT count as a label
    r = detect(fake_raw_dataset)
    assert r.label_count == 8  # not 9


def test_detect_images_only(tmp_path: Path):
    from tests.conftest import make_png
    for i in range(5):
        (tmp_path / f"{i}.png").write_bytes(make_png(seed=i))
    r = detect(tmp_path)
    assert r.detected_format == "images_only"
    assert r.image_count == 5
    assert "images-only" in (r.notes[0] if r.notes else "")


def test_detect_coco_format(tmp_path: Path):
    from tests.conftest import make_png
    (tmp_path / "images").mkdir()
    (tmp_path / "images" / "a.jpg").write_bytes(make_png())
    (tmp_path / "instances.json").write_text("{}")
    r = detect(tmp_path)
    assert r.detected_format == "coco"


def test_detect_warns_on_many_missing_labels(tmp_path: Path):
    """If most images have no .txt, the report should flag it."""
    from tests.conftest import make_png
    (tmp_path / "images").mkdir()
    (tmp_path / "labels").mkdir()
    for i in range(10):
        (tmp_path / "images" / f"{i}.jpg").write_bytes(make_png(seed=i))
    # only label 2 of 10
    for i in range(2):
        (tmp_path / "labels" / f"{i}.txt").write_text("0 0.5 0.5 0.1 0.1\n")
    r = detect(tmp_path)
    assert r.detected_format == "yolo"
    assert any("missing labels" in n for n in r.notes)
