"""Rules-based dataset recommendations.

Inputs: the findings dict from analysis.checks.run_all_checks + health score.
Output: list of {code, severity, message, fix} entries plus a single
`ready_for_training` boolean.
"""
from __future__ import annotations

from typing import Any

# Severity ranks (used for sorting only)
_RANK = {"blocker": 0, "warning": 1, "info": 2}


def _rec(code: str, severity: str, message: str, fix: str | None = None,
         meta: dict | None = None) -> dict[str, Any]:
    return {"code": code, "severity": severity, "message": message,
            "fix": fix, "meta": meta or {}}


def evaluate(findings: dict, *, health_score: float) -> tuple[list[dict[str, Any]], bool]:
    recs: list[dict[str, Any]] = []
    counts = findings.get("counts", {})
    lh = findings.get("label_health", {})
    cd = findings.get("class_distribution", {})
    dup = findings.get("duplicates", {})
    corr = findings.get("corruption", {})
    res = findings.get("resolution", {})

    n = counts.get("image_count", 0)

    # Volume
    if n < 100:
        recs.append(_rec(
            "TOO_FEW_IMAGES", "blocker",
            f"Only {n} images — model will overfit. Recommended minimum: 100 per class.",
            "Collect more samples or use a stronger augmentation policy.",
            {"image_count": n},
        ))
    elif n < 500:
        recs.append(_rec(
            "LOW_VOLUME", "warning",
            f"Dataset has {n} images. Recommend at least 500 for stable training.",
            "Collect more images or expect higher variance between runs.",
            {"image_count": n},
        ))

    # Missing / empty labels
    miss = lh.get("missing", 0)
    if miss > 0:
        sev = "blocker" if lh.get("missing_ratio", 0) > 0.1 else "warning"
        recs.append(_rec(
            "MISSING_LABELS", sev,
            f"{miss} image(s) have no label file.",
            "Annotate them, or remove them from the dataset before training.",
            {"missing": miss, "ratio": lh.get("missing_ratio", 0)},
        ))
    empty = lh.get("empty", 0)
    if empty > 0:
        recs.append(_rec(
            "EMPTY_LABELS", "warning",
            f"{empty} label file(s) are empty.",
            "Either remove the image or add at least one annotation.",
            {"empty": empty, "ratio": lh.get("empty_ratio", 0)},
        ))

    # Class balance + per-class shortage
    per_class = cd.get("images_per_class", {}) or {}
    for cls, imgs in per_class.items():
        if imgs < 50:
            recs.append(_rec(
                "CLASS_LOW_SAMPLES", "warning",
                f"Class {cls!r} has only {imgs} sample(s).",
                f"Collect more {cls!r} images (aim for 100+).",
                {"class": cls, "images": imgs},
            ))
    gini = cd.get("gini", 0.0) or 0.0
    if gini > 0.5:
        recs.append(_rec(
            "CLASS_IMBALANCE", "warning",
            f"Classes are imbalanced (Gini={gini:.2f}).",
            "Add samples for under-represented classes, or use class-weighting in training.",
            {"gini": gini, "per_class": per_class},
        ))

    # Duplicates
    dup_imgs = dup.get("duplicate_images", 0) or 0
    if dup_imgs > 0:
        recs.append(_rec(
            "DUPLICATES", "warning",
            f"{dup_imgs} image(s) appear to be near-duplicates "
            f"({dup.get('duplicate_groups', 0)} group(s)).",
            "Deduplicate to avoid train/val leakage.",
            {"groups": dup.get("duplicate_groups", 0)},
        ))

    # Corruption
    corrupt = corr.get("corrupt", []) or []
    if corrupt:
        recs.append(_rec(
            "CORRUPT_IMAGES", "blocker",
            f"{len(corrupt)} image(s) failed to open.",
            "Remove or replace the corrupt files before training.",
            {"examples": corrupt[:5]},
        ))

    # Resolution
    too_small = res.get("too_small", 0) or 0
    if too_small > 0:
        recs.append(_rec(
            "TINY_IMAGES", "warning",
            f"{too_small} image(s) are smaller than 32px on one side.",
            "Drop them or upscale before training.",
            {"too_small": too_small},
        ))
    median_w = res.get("widths_median") or 0
    if median_w and median_w < 320:
        recs.append(_rec(
            "LOW_RESOLUTION", "info",
            f"Median image width is {median_w}px.",
            "Consider higher-resolution sources for better small-object recall.",
            {"median_w": median_w},
        ))

    # Augmentation hint
    if n < 1000 and lh.get("missing_ratio", 0) < 0.05:
        recs.append(_rec(
            "AUGMENT", "info",
            "Dataset is small but clean — augmentation will help generalization.",
            "Train with Ultralytics' built-in augmentations enabled (default).",
            {},
        ))

    # Sort by severity
    recs.sort(key=lambda r: _RANK.get(r["severity"], 9))

    # Readiness
    blockers = [r for r in recs if r["severity"] == "blocker"]
    ready = (not blockers) and health_score >= 60.0

    return recs, ready
