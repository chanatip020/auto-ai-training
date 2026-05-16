"""Tests for the dataset health-score computation."""
from __future__ import annotations

import pytest

from app.services.analysis.score import compute


def _good_findings(n_images: int = 2000, gini: float = 0.0) -> dict:
    """A dataset with no issues — should score close to 100."""
    return {
        "counts": {"image_count": n_images},
        "label_health": {"missing_ratio": 0.0, "empty_ratio": 0.0},
        "duplicates": {"duplicate_images": 0},
        "corruption": {"corrupt": []},
        "class_distribution": {"gini": gini},
        "resolution": {"widths_median": 1024, "heights_median": 1024},
    }


def test_score_perfect_dataset_is_near_100():
    total, comps = compute(_good_findings())
    assert 95 < total <= 100
    assert all(0 <= v <= 30 for v in comps.values())


def test_score_components_sum_to_total():
    total, comps = compute(_good_findings())
    assert abs(sum(comps.values()) - total) < 0.01


def test_score_drops_with_missing_labels():
    f = _good_findings()
    f["label_health"]["missing_ratio"] = 0.5
    total, _ = compute(f)
    base_total, _ = compute(_good_findings())
    assert total < base_total - 5  # significantly lower


def test_score_drops_with_class_imbalance():
    base_total, _ = compute(_good_findings(gini=0.0))
    skewed_total, _ = compute(_good_findings(gini=0.9))
    assert skewed_total < base_total - 10


def test_score_low_volume_capped():
    """A tiny dataset should score badly on the volume component."""
    _, comps = compute(_good_findings(n_images=50))
    assert comps["volume"] < 5.0


def test_score_handles_zero_images():
    f = _good_findings(n_images=0)
    total, comps = compute(f)
    assert 0 <= total <= 100
    assert comps["volume"] < 5.0


def test_score_resolution_scale():
    high_res = _good_findings()
    low_res = _good_findings()
    low_res["resolution"] = {"widths_median": 200, "heights_median": 200}
    total_high, _ = compute(high_res)
    total_low, _ = compute(low_res)
    assert total_low < total_high
