"""Tests for the data.yaml writer."""
from __future__ import annotations

from pathlib import Path

from app.services.datasets.yaml_writer import write_data_yaml


def test_basic_yaml(tmp_path: Path):
    out = write_data_yaml(output_dir=tmp_path, classes=["person", "car"])
    text = out.read_text(encoding="utf-8")
    assert "path:" in text
    assert "train: images/train" in text
    assert "val: images/val" in text
    assert "test: images/test" in text
    assert "nc: 2" in text
    assert "names: [person, car]" in text


def test_no_test_split(tmp_path: Path):
    out = write_data_yaml(output_dir=tmp_path, classes=["a"], has_test=False)
    text = out.read_text(encoding="utf-8")
    assert "test:" not in text


def test_class_names_with_spaces_are_quoted(tmp_path: Path):
    out = write_data_yaml(output_dir=tmp_path, classes=["bike helmet", "stop sign"])
    text = out.read_text(encoding="utf-8")
    assert "'bike helmet'" in text
    assert "'stop sign'" in text


def test_class_names_with_colons_are_quoted(tmp_path: Path):
    out = write_data_yaml(output_dir=tmp_path, classes=["foo:bar"])
    text = out.read_text(encoding="utf-8")
    assert "'foo:bar'" in text


def test_round_trip_with_pyyaml(tmp_path: Path):
    import yaml
    write_data_yaml(output_dir=tmp_path, classes=["person", "car"])
    parsed = yaml.safe_load((tmp_path / "data.yaml").read_text(encoding="utf-8"))
    assert parsed["nc"] == 2
    assert parsed["names"] == ["person", "car"]
