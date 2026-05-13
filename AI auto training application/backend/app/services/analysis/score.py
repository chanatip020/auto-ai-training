"""Dataset health score.

Weighted blend documented in the design doc (Appendix 12.2):

    score =  20 * (1 - missing_label_ratio)
           + 15 * (1 - empty_label_ratio)
           + 15 * (1 - duplicate_ratio)
           + 10 * (1 - corrupt_ratio)
           + 20 * class_balance_score      # 1 - Gini
           + 10 * resolution_score          # 1 if median >= 640
           + 10 * volume_score              # piecewise on image count

Total in [0, 100].
"""
from __future__ import annotations


def _clamp(x: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, x))


def _volume_score(n_images: int) -> float:
    if n_images < 100:
        return 0.1
    if n_images < 500:
        return 0.4
    if n_images < 2000:
        return 0.7
    if n_images < 5000:
        return 0.9
    return 1.0


def _resolution_score(median_w: int | None, median_h: int | None) -> float:
    if not median_w or not median_h:
        return 0.0
    m = min(median_w, median_h)
    if m >= 1280:
        return 1.0
    if m >= 640:
        return 0.9
    if m >= 320:
        return 0.6
    return 0.3


def compute(findings: dict) -> tuple[float, dict[str, float]]:
    """Return (total_score, per_component_score). Both 0-100."""
    counts = findings.get("counts", {})
    label_health = findings.get("label_health", {})
    dup = findings.get("duplicates", {})
    corr = findings.get("corruption", {})
    cdist = findings.get("class_distribution", {})
    res = findings.get("resolution", {})

    n_images = counts.get("image_count", 0)
    missing_ratio = label_health.get("missing_ratio", 0.0) or 0.0
    empty_ratio = label_health.get("empty_ratio", 0.0) or 0.0
    dup_imgs = dup.get("duplicate_images", 0) or 0
    dup_ratio = dup_imgs / n_images if n_images else 0.0
    corr_count = len(corr.get("corrupt", []) or [])
    corr_ratio = corr_count / n_images if n_images else 0.0
    gini = cdist.get("gini", 0.0) or 0.0
    balance = _clamp(1.0 - gini)

    res_score = _resolution_score(res.get("widths_median"), res.get("heights_median"))
    vol_score = _volume_score(n_images)

    components = {
        "missing_labels": 20.0 * _clamp(1 - missing_ratio),
        "empty_labels":   15.0 * _clamp(1 - empty_ratio),
        "duplicates":     15.0 * _clamp(1 - dup_ratio),
        "corruption":     10.0 * _clamp(1 - corr_ratio),
        "class_balance":  20.0 * balance,
        "resolution":     10.0 * res_score,
        "volume":         10.0 * vol_score,
    }
    total = round(sum(components.values()), 2)
    return total, {k: round(v, 2) for k, v in components.items()}
