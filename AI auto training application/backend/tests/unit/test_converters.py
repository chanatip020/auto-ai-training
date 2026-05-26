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

def test_yolo_det_accepts_cvat_obj_names(tmp_path: Path):
    """CVAT 'YOLO 1.1' export ships obj.names + obj_train_data/."""
    from tests.conftest import make_png
    (tmp_path / "obj.names").write_text("cat\ndog\n")
    (tmp_path / "obj.data").write_text("classes = 2\n")
    (tmp_path / "train.txt").write_text("obj_train_data/img1.jpg\n")
    sub = tmp_path / "obj_train_data"
    sub.mkdir()
    for n in ("img1", "img2"):
        (sub / f"{n}.jpg").write_bytes(make_png())
        (sub / f"{n}.txt").write_text("0 0.5 0.5 0.2 0.2\n")
    conv = get_converter("yolo-det")
    result = conv.convert(
        input_dir=tmp_path, output_dir=tmp_path / "out",
        ratios=DEFAULT_RATIOS, classes_override=None, seed=SEED,
    )
    assert result.classes == ["cat", "dog"]
    assert result.num_images == 2
    assert result.num_labels == 2
    assert sum(result.counts.values()) == 2


def test_yolo_seg_uses_det_layout(fake_raw_dataset: Path, tmp_path: Path):
    """Segmentation uses the same files-as-det layout; only the format_id differs."""
    conv = get_converter("yolo-seg")
    result = conv.convert(
        input_dir=fake_raw_dataset, output_dir=tmp_path / "seg-out",
        ratios=DEFAULT_RATIOS, classes_override=None, seed=SEED,
    )
    assert result.format == "yolo-seg"
    assert (tmp_path / "seg-out" / "data.yaml").exists()


def test_yolo_det_orphan_images_default_no_empty_txt(tmp_path: Path):
    """Default: an image without a .txt is left as an orphan, no sidecar."""
    from tests.conftest import make_png
    (tmp_path / "classes.txt").write_text("cat\n")
    for stem in ("a", "b", "c"):
        (tmp_path / f"{stem}.jpg").write_bytes(make_png())
    # only one of the three has a label
    (tmp_path / "a.txt").write_text("0 0.5 0.5 0.1 0.1\n")

    conv = get_converter("yolo-det")
    result = conv.convert(
        input_dir=tmp_path, output_dir=tmp_path / "out",
        ratios=DEFAULT_RATIOS, classes_override=None, seed=SEED,
    )
    assert result.num_images == 3
    assert result.num_labels == 1
    assert result.extra["background_count"] == 0
    assert result.extra["unlabeled_count"] == 2
    label_files = list((tmp_path / "out" / "labels").rglob("*.txt"))
    assert len(label_files) == 1


def test_yolo_det_background_flag_materialises_empty_txt(tmp_path: Path):
    """treat_unlabeled_as_background=True writes empty .txt for each orphan."""
    from tests.conftest import make_png
    (tmp_path / "classes.txt").write_text("cat\n")
    for stem in ("a", "b", "c"):
        (tmp_path / f"{stem}.jpg").write_bytes(make_png())
    (tmp_path / "a.txt").write_text("0 0.5 0.5 0.1 0.1\n")

    conv = get_converter("yolo-det")
    result = conv.convert(
        input_dir=tmp_path, output_dir=tmp_path / "out",
        ratios=DEFAULT_RATIOS, classes_override=None, seed=SEED,
        treat_unlabeled_as_background=True,
    )
    assert result.num_images == 3
    assert result.num_labels == 3
    assert result.extra["background_count"] == 2
    assert result.extra["unlabeled_count"] == 0
    assert result.extra["treat_unlabeled_as_background"] is True
    label_files = sorted((tmp_path / "out" / "labels").rglob("*.txt"))
    assert len(label_files) == 3
    empties = [f for f in label_files if f.read_text() == ""]
    assert len(empties) == 2


def test_yolo_cls_accepts_background_flag_no_op(fake_cls_dataset: Path, tmp_path: Path):
    """Classification has no separate labels — flag is accepted but no-op."""
    conv = get_converter("yolo-cls")
    result = conv.convert(
        input_dir=fake_cls_dataset, output_dir=tmp_path / "cls-out",
        ratios=DEFAULT_RATIOS, classes_override=None, seed=SEED,
        treat_unlabeled_as_background=True,
    )
    assert result.format == "yolo-cls"
    assert result.num_images == 10

