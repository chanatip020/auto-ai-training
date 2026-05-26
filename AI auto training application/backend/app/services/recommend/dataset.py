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

    # ------------------------------------------------------------------
    # Missing / empty labels — interpretation depends on whether the user
    # opted into "treat unlabeled images as background images" on the
    # dataset (Ultralytics recommends 0-10% background frames to reduce
    # false positives).
    #
    #   * Opted IN (treat_unlabeled_as_background=True):
    #       Zero-object images are intentional. Surface the background
    #       ratio as INFO (or nudge them toward the 10% sweet spot), and
    #       never block.
    #
    #   * Opted OUT (default):
    #       Use a tiered judgment on the unlabeled ratio:
    #         <=10%   -> INFO ("looks like background frames, confirm")
    #         10-30%  -> WARNING ("likely unlabeled, please confirm")
    #         >30%    -> BLOCKER ("looks unlabeled, fix before training")
    # ------------------------------------------------------------------
    treat_bg = bool(lh.get("treat_unlabeled_as_background", False))
    miss = lh.get("missing", 0)
    miss_ratio = lh.get("missing_ratio", 0.0) or 0.0
    empty = lh.get("empty", 0)
    empty_ratio = lh.get("empty_ratio", 0.0) or 0.0

    if treat_bg:
        bg_count = lh.get("background", miss + empty)
        bg_ratio = lh.get("background_ratio", (miss + empty) / max(n, 1))
        if bg_count > 0:
            # Ultralytics docs: "background images" should sit in 0-10%.
            if bg_ratio > 0.20:
                recs.append(_rec(
                    "BACKGROUND_RATIO_HIGH", "warning",
                    f"{bg_count} background image(s) — {bg_ratio*100:.0f}% of the dataset. "
                    "More than ~10% can hurt recall.",
                    "Reduce the share of label-free frames, or add more positive samples.",
                    {"background_count": bg_count, "ratio": bg_ratio},
                ))
            elif bg_ratio < 0.01 and n >= 200:
                recs.append(_rec(
                    "BACKGROUND_RATIO_LOW", "info",
                    f"Only {bg_count} background image(s) — {bg_ratio*100:.1f}%.",
                    "Add a few label-free frames (target ~10%) to reduce false positives.",
                    {"background_count": bg_count, "ratio": bg_ratio},
                ))
            else:
                recs.append(_rec(
                    "BACKGROUND_RATIO_OK", "info",
                    f"{bg_count} background image(s) — {bg_ratio*100:.1f}% of the dataset.",
                    None,
                    {"background_count": bg_count, "ratio": bg_ratio},
                ))
    else:
        if miss > 0:
            if miss_ratio > 0.30:
                sev = "blocker"
                msg = (f"{miss} image(s) ({miss_ratio*100:.0f}%) have no label file — "
                       "likely an annotation issue.")
                fix = ("Annotate the missing images, remove them, or — if these are "
                       "intentional background frames — enable "
                       "'treat unlabeled as background' on this dataset.")
            elif miss_ratio > 0.10:
                sev = "warning"
                msg = (f"{miss} image(s) ({miss_ratio*100:.0f}%) have no label file. "
                       "This could be unlabeled images or intentional background frames.")
                fix = ("Confirm intent: label them, drop them, or enable "
                       "'treat unlabeled as background' on this dataset.")
            else:
                sev = "info"
                msg = (f"{miss} image(s) ({miss_ratio*100:.1f}%) have no label file — "
                       "consistent with intentional background frames.")
                fix = ("If these are intentional, enable 'treat unlabeled as background' "
                       "on this dataset so the recommender stops flagging them.")
            recs.append(_rec(
                "MISSING_LABELS", sev, msg, fix,
                {"missing": miss, "ratio": miss_ratio},
            ))
        if empty > 0:
            recs.append(_rec(
                "EMPTY_LABELS", "warning",
                f"{empty} label file(s) are empty.",
                "Either annotate the image, remove it, or enable 'treat unlabeled "
                "as background' on this dataset to mark them as intentional.",
                {"empty": empty, "ratio": empty_ratio},
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

    # Augmentation hint — dataset is "clean enough" if either:
    #   - opted into background mode (missing labels are intentional), OR
    #   - actual unlabeled ratio is <5%
    clean_enough = treat_bg or miss_ratio < 0.05
    if n < 1000 and clean_enough:
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
