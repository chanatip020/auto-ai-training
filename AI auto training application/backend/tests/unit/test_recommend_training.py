"""Tests for the training-parameter recommendation engine."""
from __future__ import annotations

import json

from app.models.enums import ModelFamily, TaskType
from app.services.recommend.training import recommend


def _findings(n=1000, gini=0.1, w=640, h=640) -> dict:
    return {
        "counts": {"image_count": n},
        "resolution": {"widths_median": w, "heights_median": h},
        "class_distribution": {"gini": gini},
    }


def test_response_shape():
    r = recommend(model_family=ModelFamily.YOLO, task_type=TaskType.DETECTION,
                  findings=_findings(), gpu_mem_gb=None)
    assert set(r.keys()) >= {"model_family", "task_type", "params", "reasons",
                             "assumptions", "groups"}
    assert "model" in r["params"]
    assert r["groups"]["basic"]
    assert r["groups"]["augmentation"]


def test_json_serializable():
    r = recommend(model_family=ModelFamily.YOLO, task_type=TaskType.DETECTION,
                  findings=_findings())
    json.dumps(r)  # should not raise


def test_small_dataset_picks_nano():
    r = recommend(model_family=ModelFamily.YOLO, task_type=TaskType.DETECTION,
                  findings=_findings(n=300))
    assert r["params"]["model"] == "yolov8n"


def test_large_dataset_picks_medium():
    r = recommend(model_family=ModelFamily.YOLO, task_type=TaskType.DETECTION,
                  findings=_findings(n=20000))
    assert r["params"]["model"] == "yolov8m"


def test_classification_uses_cls_suffix():
    r = recommend(model_family=ModelFamily.YOLO, task_type=TaskType.CLASSIFICATION,
                  findings=_findings(w=320, h=320))
    assert r["params"]["model"].endswith("-cls")
    assert r["params"]["imgsz"] == 224  # classification standard


def test_segmentation_uses_seg_suffix():
    r = recommend(model_family=ModelFamily.YOLO, task_type=TaskType.SEGMENTATION,
                  findings=_findings())
    assert r["params"]["model"].endswith("-seg")


def test_high_res_picks_1280():
    r = recommend(model_family=ModelFamily.YOLO, task_type=TaskType.DETECTION,
                  findings=_findings(w=1600, h=1600))
    assert r["params"]["imgsz"] == 1280


def test_small_dataset_picks_adamw():
    r = recommend(model_family=ModelFamily.YOLO, task_type=TaskType.DETECTION,
                  findings=_findings(n=300))
    assert r["params"]["optimizer"] == "AdamW"
    assert r["params"]["lr0"] == 0.001


def test_imbalanced_classification_enables_mixup():
    r = recommend(model_family=ModelFamily.YOLO, task_type=TaskType.CLASSIFICATION,
                  findings=_findings(n=5000, gini=0.7))
    assert r["params"]["mixup"] > 0


def test_balanced_medium_det_disables_mixup():
    r = recommend(model_family=ModelFamily.YOLO, task_type=TaskType.DETECTION,
                  findings=_findings(n=2000, gini=0.0))
    assert r["params"]["mixup"] == 0.0


def test_imbalanced_medium_det_enables_mixup():
    r = recommend(model_family=ModelFamily.YOLO, task_type=TaskType.DETECTION,
                  findings=_findings(n=2000, gini=0.7))
    assert r["params"]["mixup"] > 0


def test_classification_disables_mosaic():
    r = recommend(model_family=ModelFamily.YOLO, task_type=TaskType.CLASSIFICATION,
                  findings=_findings())
    assert r["params"]["mosaic"] == 0.0


def test_all_basic_keys_have_reasons():
    r = recommend(model_family=ModelFamily.YOLO, task_type=TaskType.DETECTION,
                  findings=_findings())
    for k in r["groups"]["basic"]:
        assert k in r["reasons"], f"missing reason for {k}"
