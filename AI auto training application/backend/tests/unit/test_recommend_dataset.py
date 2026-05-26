"""Tests for the rules-based dataset recommendation engine."""
from __future__ import annotations

from app.services.recommend.dataset import evaluate


def _findings(n=2000, missing=0, empty=0, dup=0, corrupt=None, gini=0.0,
              widths_median=1024, too_small=0, per_class=None,
              treat_bg=False, background=0) -> dict:
    bg_count = background if treat_bg else 0
    if treat_bg and background == 0:
        # If the caller didn't pass an explicit background count, reclassify
        # any missing/empty images as backgrounds (mirrors the analyzer).
        bg_count = missing + empty
    return {
        "counts": {"image_count": n},
        "label_health": {
            "missing": missing,
            "empty": empty,
            "background": bg_count,
            "missing_ratio": missing / max(n, 1),
            "empty_ratio": empty / max(n, 1),
            "background_ratio": bg_count / max(n, 1),
            "treat_unlabeled_as_background": treat_bg,
        },
        "duplicates": {"duplicate_images": dup, "duplicate_groups": 1 if dup else 0},
        "corruption": {"corrupt": corrupt or []},
        "class_distribution": {"gini": gini, "images_per_class": per_class or {}},
        "resolution": {"widths_median": widths_median, "too_small": too_small},
    }


def test_clean_dataset_has_no_blockers():
    recs, ready = evaluate(_findings(per_class={"a": 500, "b": 500}), health_score=85)
    blockers = [r for r in recs if r["severity"] == "blocker"]
    assert blockers == []
    assert ready is True


def test_too_few_images_is_blocker():
    recs, ready = evaluate(_findings(n=30), health_score=20)
    codes = {r["code"] for r in recs if r["severity"] == "blocker"}
    assert "TOO_FEW_IMAGES" in codes
    assert ready is False


def test_missing_labels_blocker_above_30pct():
    """>30% unlabeled is almost certainly an annotation defect."""
    recs, _ = evaluate(_findings(n=100, missing=40), health_score=40)
    blocker = next(r for r in recs if r["code"] == "MISSING_LABELS")
    assert blocker["severity"] == "blocker"


def test_missing_labels_warning_between_10_and_30pct():
    """10-30% unlabeled — could be unlabeled, could be background. Warn."""
    recs, _ = evaluate(_findings(n=100, missing=20), health_score=60)
    warning = next(r for r in recs if r["code"] == "MISSING_LABELS")
    assert warning["severity"] == "warning"


def test_missing_labels_info_below_10pct():
    """<=10% unlabeled looks like background images — info, not blocker."""
    recs, ready = evaluate(_findings(n=1000, missing=50, per_class={"a": 500, "b": 500}),
                           health_score=85)
    info = next(r for r in recs if r["code"] == "MISSING_LABELS")
    assert info["severity"] == "info"
    # Ready-for-training should NOT be blocked by a small unlabeled ratio.
    assert ready is True


def test_background_mode_skips_missing_labels_blocker():
    """When the user opts in, even a large unlabeled ratio is non-blocking."""
    recs, ready = evaluate(
        _findings(n=100, missing=40, per_class={"a": 50, "b": 50},
                  treat_bg=True),
        health_score=85,
    )
    # No MISSING_LABELS — instead a BACKGROUND_RATIO_* entry.
    assert not any(r["code"] == "MISSING_LABELS" for r in recs)
    assert any(r["code"].startswith("BACKGROUND_RATIO") for r in recs)
    assert ready is True


def test_background_ratio_too_high_warns():
    """>20% background images can hurt recall."""
    recs, _ = evaluate(
        _findings(n=100, missing=30, per_class={"a": 50, "b": 50}, treat_bg=True),
        health_score=85,
    )
    bg = next(r for r in recs if r["code"] == "BACKGROUND_RATIO_HIGH")
    assert bg["severity"] == "warning"


def test_background_ratio_too_low_suggests_more():
    """A clean dataset with no background frames gets a soft suggestion."""
    recs, _ = evaluate(
        _findings(n=1000, missing=0, per_class={"a": 500, "b": 500}, treat_bg=True),
        health_score=85,
    )
    # 0 background images is OK — no BACKGROUND_RATIO_LOW emitted (since
    # background_count is 0 we don't push noise).
    assert not any(r["code"] == "BACKGROUND_RATIO_LOW" for r in recs)


def test_background_ratio_in_sweet_spot_is_info():
    """5% background images — Ultralytics sweet spot. INFO only."""
    recs, ready = evaluate(
        _findings(n=1000, missing=50, per_class={"a": 500, "b": 500}, treat_bg=True),
        health_score=85,
    )
    ok = next(r for r in recs if r["code"] == "BACKGROUND_RATIO_OK")
    assert ok["severity"] == "info"
    assert ready is True


def test_corrupt_images_is_blocker():
    recs, ready = evaluate(_findings(corrupt=["bad.jpg"]), health_score=70)
    assert any(r["code"] == "CORRUPT_IMAGES" and r["severity"] == "blocker" for r in recs)
    assert ready is False


def test_class_low_samples_warning_per_class():
    recs, _ = evaluate(_findings(per_class={"rare": 10, "common": 1000}), health_score=70)
    low = [r for r in recs if r["code"] == "CLASS_LOW_SAMPLES"]
    assert len(low) == 1
    assert "rare" in low[0]["message"]


def test_class_imbalance_warning():
    recs, _ = evaluate(_findings(gini=0.7, per_class={"a": 800, "b": 200}), health_score=60)
    assert any(r["code"] == "CLASS_IMBALANCE" for r in recs)


def test_ready_requires_score_60():
    """Even with no blockers, score < 60 means not ready."""
    recs, ready = evaluate(_findings(per_class={"a": 500, "b": 500}), health_score=55)
    assert all(r["severity"] != "blocker" for r in recs)
    assert ready is False


def test_recommendations_sorted_by_severity():
    recs, _ = evaluate(
        _findings(n=30, corrupt=["x.jpg"], gini=0.7, per_class={"a": 10, "b": 1000}),
        health_score=30,
    )
    # All blockers should come before warnings, warnings before infos.
    rank = {"blocker": 0, "warning": 1, "info": 2}
    seq = [rank[r["severity"]] for r in recs]
    assert seq == sorted(seq)
