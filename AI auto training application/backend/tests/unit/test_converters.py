"""Tests for the YOLO converters (detection + classification)."""
from __future__ import annotations

import uuid
from pathlib import Path

import pytest

from app.core.errors import AppError
from app.services.datasets.converters import (
    DEFAULT_FORMAT_FOR_TASK,
    FORMAT_TO_CONVERTER,
    get_converter,
)
from app.services.datasets.split import DEFAULT_RATIOS


SEED = uuid.UUID("00000000-0000-0000-0000-000000000042")


def test_registry_has_all_three_formats():
    assert set(FORMAT_TO_CONVERTER) == {"yolo-det", "yolo-seg", "yolo-cls"}


def test_get_converter_unknown_format_raises():
    with pytest.raises(KeyError):
        get_converter("not-a-format")


def test_default_format_map_matches_task_types():
    from app.models.enums import TaskType
    assert DEFAULT_FORMAT_FOR_TASK[TaskType.DETECTION] == "yolo-det"
    assert DEFAULT_FORMAT_FOR_TASK[TaskType.SEGMENTATION] == "yolo-seg"
    assert DEFAULT_FORMAT_FOR_TASK[TaskType.CLASSIFICATION] == "yolo-cls"


def test_yolo_det_basic_conversion(fake_raw_dataset: Path, tmp_path: Path):
    conv = get_converter("yolo-det")
    out = tmp_path / "out"
    result = conv.convert(
        input_dir=fake_raw_dataset, output_dir=out,
        ratios=DEFAULT_RATIOS, classes_override=None, seed=SEED,
    )
    assert result.format == "yolo-det"
    assert result.classes == ["person", "car"]
    assert result.num_images == 8
    assert result.num_labels == 8
    assert sum(result.counts.values()) == 8
    # On-disk structure
    assert (out / "data.yaml").exists()
    for split in ("train", "val", "test"):
        assert (out / "images" / split).is_dir()
        assert (out / "labels" / split).is_dir()


def test_yolo_det_no_images_raises(tmp_path: Path):
    (tmp_path / "classes.txt").write_text("a\n")
    conv = get_converter("yolo-det")
    with pytest.raises(AppError) as ei:
        conv.convert(
            input_dir=tmp_path, output_dir=tmp_path / "out",
            ratios=DEFAULT_RATIOS, classes_override=None, seed=SEED,
        )
    assert ei.value.code == "CONVERT_NO_IMAGES"


def test_yolo_det_no_classes_raises(tmp_path: Path):
    from tests.conftest import make_png
    (tmp_path / "images").mkdir()
    (tmp_path / "images" / "x.jpg").write_bytes(make_png())
    conv = get_converter("yolo-det")
    with pytest.raises(AppError) as ei:
        conv.convert(
            input_dir=tmp_path, output_dir=tmp_path / "out",
            ratios=DEFAULT_RATIOS, classes_override=None, seed=SEED,
        )
    assert ei.value.code == "CONVERT_NO_CLASSES"


def test_yolo_det_classes_override_wins(fake_raw_dataset: Path, tmp_path: Path):
    conv = get_converter("yolo-det")
    result = conv.convert(
        input_dir=fake_raw_dataset, output_dir=tmp_path / "out",
        ratios=DEFAULT_RATIOS, classes_override=["explicit-a", "explicit-b"], seed=SEED,
    )
    assert result.classes == ["explicit-a", "explicit-b"]


def test_yolo_det_is_deterministic(fake_raw_dataset: Path, tmp_path: Path):
    conv = get_converter("yolo-det")
    out1 = tmp_path / "a"
    out2 = tmp_path / "b"
    conv.convert(input_dir=fake_raw_dataset, output_dir=out1,
                 ratios=DEFAULT_RATIOS, classes_override=None, seed=SEED)
    conv.convert(input_dir=fake_raw_dataset, output_dir=out2,
                 ratios=DEFAULT_RATIOS, classes_override=None, seed=SEED)
    files1 = sorted(p.name for p in (out1 / "images" / "train").iterdir())
    files2 = sorted(p.name for p in (out2 / "images" / "train").iterdir())
    assert files1 == files2


def test_yolo_cls_basic_conversion(fake_cls_dataset: Path, tmp_path: Path):
    conv = get_converter("yolo-cls")
    out = tmp_path / "cls-out"
    result = conv.convert(
        input_dir=fake_cls_dataset, output_dir=out,
        ratios=DEFAULT_RATIOS, classes_override=None, seed=SEED,
    )
    assert result.format == "yolo-cls"
    assert set(result.classes) == {"cat", "dog"}
    assert result.num_images == 10  # 5 + 5
    # Per-split per-class folders exist
    for split in ("train", "val", "test"):
        for cls in result.classes:
            assert (out / split / cls).is_dir()


def test_yolo_seg_uses_det_layout(fake_raw_dataset: Path, tmp_path: Path):
    """Segmentation uses the same files-as-det layout; only the format_id differs."""
    conv = get_converter("yolo-seg")
    result = conv.convert(
        input_dir=fake_raw_dataset, output_dir=tmp_path / "seg-out",
        ratios=DEFAULT_RATIOS, classes_override=None, seed=SEED,
    )
    assert result.format == "yolo-seg"
    assert (tmp_path / "seg-out" / "data.yaml").exists()
