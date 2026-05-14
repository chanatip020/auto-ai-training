"""Training-parameter recommendations.

Stateless: derives suggested hyperparameters from dataset statistics, model
family, and task type. Each parameter comes with a human-readable reason
so the UI can explain *why* it was picked.
"""
from __future__ import annotations

import math
from typing import Any

from app.models.enums import ModelFamily, TaskType


def _pick_model_size(n_images: int, task: TaskType) -> tuple[str, str]:
    """Return (model_id, reason). YOLOv8 names map to v11 by the same suffix."""
    suffix_table = {
        TaskType.DETECTION: ("yolov8n", "yolov8s", "yolov8m"),
        TaskType.SEGMENTATION: ("yolov8n-seg", "yolov8s-seg", "yolov8m-seg"),
        TaskType.CLASSIFICATION: ("yolov8n-cls", "yolov8s-cls", "yolov8m-cls"),
    }
    nano, small, med = suffix_table[task]
    if n_images < 500:
        return nano, "Few images - nano avoids overfitting and trains quickly."
    if n_images < 5000:
        return small, "Moderate dataset size - small balances accuracy and speed."
    return med, "Larger dataset - medium can use the extra signal without overfitting."


def _pick_epochs(n_images: int) -> tuple[int, str]:
    if n_images <= 0:
        return 50, "Default for empty/unknown dataset size."
    raw = 50 + int(math.log2(max(n_images, 1)) * 10)
    epochs = max(50, min(300, raw))
    return epochs, f"Scaled with dataset size (log2 of {n_images})."


def _pick_imgsz(median_w: int | None, median_h: int | None, task: TaskType) -> tuple[int, str]:
    m = min(median_w or 0, median_h or 0)
    if task == TaskType.CLASSIFICATION:
        if m >= 320:
            return 224, "Classification: 224px is the standard input size."
        return 160, "Median image is small; using a smaller classification crop."
    if m >= 1024:
        return 1280, f"Median image side ~{m}px - higher imgsz captures more detail."
    return 640, f"Median image side ~{m}px - 640 is the YOLO default and a safe choice."


def _pick_batch_size(gpu_mem_gb: float | None, imgsz: int) -> tuple[int, str]:
    if gpu_mem_gb is None:
        return 16, "CPU mode: small batch keeps RAM use predictable."
    if gpu_mem_gb >= 16 and imgsz <= 640:
        return 32, f"GPU has {gpu_mem_gb:.0f} GB - 32 fits at imgsz=640."
    if gpu_mem_gb >= 8:
        return 16, f"GPU has {gpu_mem_gb:.0f} GB - 16 is a safe choice."
    return 8, f"GPU memory is tight ({gpu_mem_gb:.0f} GB) - 8 avoids OOM."


def _pick_lr_and_optimizer(n_images: int) -> tuple[float, str, str]:
    if n_images < 500:
        return 0.001, "AdamW", "Few images -> AdamW with a smaller LR converges more smoothly."
    return 0.01, "auto", "Larger dataset -> Ultralytics auto-picks SGD; standard initial LR 0.01."


# --------- augmentation ---------

def _pick_augmentation(
    n_images: int, task: TaskType, gini: float,
) -> tuple[dict[str, float], dict[str, str]]:
    """Return (augmentation_params, per-param reasons).

    Strategy:
      - Small datasets (<500): aggressive aug to fight overfitting
      - Medium (500-5000): YOLO defaults
      - Large (>5000): slightly reduced mosaic to expose model to clean samples
      - Classification: no mosaic; mixup helps a lot when imbalanced/small
      - Heavy class imbalance: turn on mixup for det/seg too
    """
    is_small = n_images < 500
    is_medium = 500 <= n_images < 5000
    imbalanced = gini > 0.5

    if task == TaskType.CLASSIFICATION:
        params = {
            "hsv_h": 0.015,
            "hsv_s": 0.7,
            "hsv_v": 0.4,
            "degrees": 0.0,
            "translate": 0.1,
            "scale": 0.5,
            "fliplr": 0.5,
            "flipud": 0.0,
            "mosaic": 0.0,
            "mixup": 0.2 if (is_small or imbalanced) else 0.0,
            "erasing": 0.4,
        }
        reasons = {
            "hsv_h": "Small color-jitter range; keeps semantic colour cues intact.",
            "hsv_s": "Saturation jitter helps the model ignore lighting variation.",
            "hsv_v": "Value (brightness) jitter for indoor/outdoor robustness.",
            "translate": "10% translate covers crop offsets between samples.",
            "scale": "+/-50% scale variance handles foreground size changes.",
            "fliplr": "Horizontal flip is safe for most non-text classes.",
            "flipud": "Vertical flip OFF - usually wrong-side-up for natural images.",
            "mosaic": "OFF for classification - mosaic mixes class labels.",
            "mixup": (
                "Small or imbalanced classification dataset - mixup smooths the decision boundary."
                if (is_small or imbalanced) else
                "Standard classification: mixup off."
            ),
            "erasing": "Random erasing forces the model to use multiple cues.",
        }
        return params, reasons

    # detection / segmentation
    if is_small:
        params = {
            "hsv_h": 0.015, "hsv_s": 0.7, "hsv_v": 0.4,
            "degrees": 5.0, "translate": 0.1, "scale": 0.5, "shear": 0.0,
            "perspective": 0.0, "fliplr": 0.5, "flipud": 0.0,
            "mosaic": 1.0, "mixup": 0.10, "copy_paste": 0.0,
            "close_mosaic": 10,
        }
        reasons = {
            "hsv_h": "Default HSV jitter - safe across most domains.",
            "hsv_s": "Saturation jitter improves robustness to lighting.",
            "hsv_v": "Brightness jitter improves robustness to exposure.",
            "degrees": "Small dataset - +/-5 deg rotation is a cheap diversity boost.",
            "translate": "Default 10% translate.",
            "scale": "+/-50% scale - helps with object-size variation.",
            "fliplr": "Horizontal flip is almost always safe for det/seg.",
            "mosaic": "Small dataset - mosaic creates synthetic 4-image composites.",
            "mixup": "10% mixup adds extra regularization for small datasets.",
            "close_mosaic": "Disable mosaic for last 10 epochs to fine-tune on clean images.",
        }
        return params, reasons

    if is_medium:
        params = {
            "hsv_h": 0.015, "hsv_s": 0.7, "hsv_v": 0.4,
            "degrees": 0.0, "translate": 0.1, "scale": 0.5, "shear": 0.0,
            "perspective": 0.0, "fliplr": 0.5, "flipud": 0.0,
            "mosaic": 1.0, "mixup": 0.10 if imbalanced else 0.0, "copy_paste": 0.0,
            "close_mosaic": 10,
        }
        reasons = {
            "hsv_h": "Standard YOLO HSV-H jitter.",
            "hsv_s": "Standard saturation jitter.",
            "hsv_v": "Standard value jitter.",
            "translate": "Default 10% translate.",
            "scale": "Default 50% scale jitter - the most useful single aug for det.",
            "fliplr": "Horizontal flip enabled.",
            "mosaic": "Standard YOLO mosaic - default 1.0.",
            "mixup": (
                "Class imbalance (Gini > 0.5) detected - 10% mixup helps minority classes."
                if imbalanced else
                "Medium dataset, balanced classes - mixup off."
            ),
            "close_mosaic": "Disable mosaic for last 10 epochs to clean up final convergence.",
        }
        return params, reasons

    # large
    params = {
        "hsv_h": 0.015, "hsv_s": 0.7, "hsv_v": 0.4,
        "degrees": 0.0, "translate": 0.1, "scale": 0.5, "shear": 0.0,
        "perspective": 0.0, "fliplr": 0.5, "flipud": 0.0,
        "mosaic": 0.85, "mixup": 0.0, "copy_paste": 0.10,
        "close_mosaic": 10,
    }
    reasons = {
        "hsv_h": "Standard HSV-H jitter.",
        "hsv_s": "Standard saturation jitter.",
        "hsv_v": "Standard value jitter.",
        "translate": "Default 10% translate.",
        "scale": "Default 50% scale jitter.",
        "fliplr": "Horizontal flip enabled.",
        "mosaic": "Large dataset - mosaic at 0.85 keeps some clean samples in each batch.",
        "copy_paste": "Copy-paste at 10% adds object-level variety on large datasets.",
        "close_mosaic": "Disable mosaic for last 10 epochs.",
    }
    return params, reasons


# --------- top-level ---------

def recommend(
    *,
    model_family: ModelFamily,
    task_type: TaskType,
    findings: dict,
    gpu_mem_gb: float | None = None,
) -> dict[str, Any]:
    """Top-level entry. Returns a JSON-ready dict the API surfaces directly."""
    if model_family != ModelFamily.YOLO:
        raise ValueError(f"Unsupported model_family: {model_family}")

    counts = findings.get("counts", {})
    res = findings.get("resolution", {})
    cdist = findings.get("class_distribution", {})
    n = counts.get("image_count", 0)
    gini = float(cdist.get("gini", 0.0) or 0.0)

    model_id, model_reason = _pick_model_size(n, task_type)
    epochs, epochs_reason = _pick_epochs(n)
    imgsz, imgsz_reason = _pick_imgsz(res.get("widths_median"), res.get("heights_median"), task_type)
    batch, batch_reason = _pick_batch_size(gpu_mem_gb, imgsz)
    lr, optimizer, lr_reason = _pick_lr_and_optimizer(n)
    aug_params, aug_reasons = _pick_augmentation(n, task_type, gini)

    params: dict[str, Any] = {
        "model": model_id,
        "epochs": epochs,
        "imgsz": imgsz,
        "batch": batch,
        "lr0": lr,
        "optimizer": optimizer,
        "augment": True,
        **aug_params,
    }

    reasons = {
        "model": model_reason,
        "epochs": epochs_reason,
        "imgsz": imgsz_reason,
        "batch": batch_reason,
        "lr0": lr_reason,
        "optimizer": lr_reason,
        **aug_reasons,
    }

    return {
        "model_family": model_family.value,
        "task_type": task_type.value,
        "params": params,
        "reasons": reasons,
        "assumptions": {
            "gpu_mem_gb": gpu_mem_gb,
            "image_count": n,
            "class_imbalance_gini": gini,
        },
        # Logical groupings the UI can use to render sections.
        "groups": {
            "basic": ["model", "epochs", "imgsz", "batch", "lr0", "optimizer"],
            "augmentation": list(aug_params.keys()),
        },
    }
