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
        return nano, "Few images — nano avoids overfitting and trains quickly."
    if n_images < 5000:
        return small, "Moderate dataset size — small balances accuracy and speed."
    return med, "Larger dataset — medium can use the extra signal without overfitting."


def _pick_epochs(n_images: int) -> tuple[int, str]:
    if n_images <= 0:
        return 50, "Default for empty/unknown dataset size."
    # piecewise: 50 + log2(n) * 10, clamped to [50, 300]
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
        return 1280, f"Median image side ~{m}px — higher imgsz captures more detail."
    return 640, f"Median image side ~{m}px — 640 is the YOLO default and a safe choice."


def _pick_batch_size(gpu_mem_gb: float | None, imgsz: int) -> tuple[int, str]:
    if gpu_mem_gb is None:
        return 16, "CPU mode: small batch keeps RAM use predictable."
    if gpu_mem_gb >= 16 and imgsz <= 640:
        return 32, f"GPU has {gpu_mem_gb:.0f} GB — 32 fits at imgsz=640."
    if gpu_mem_gb >= 8:
        return 16, f"GPU has {gpu_mem_gb:.0f} GB — 16 is a safe choice."
    return 8, f"GPU memory is tight ({gpu_mem_gb:.0f} GB) — 8 avoids OOM."


def _pick_lr_and_optimizer(n_images: int) -> tuple[float, str, str]:
    if n_images < 500:
        return 0.001, "AdamW", "Few images → AdamW with a smaller LR converges more smoothly."
    return 0.01, "auto", "Larger dataset → Ultralytics auto-picks SGD; standard initial LR 0.01."


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
    n = counts.get("image_count", 0)

    model_id, model_reason = _pick_model_size(n, task_type)
    epochs, epochs_reason = _pick_epochs(n)
    imgsz, imgsz_reason = _pick_imgsz(res.get("widths_median"), res.get("heights_median"), task_type)
    batch, batch_reason = _pick_batch_size(gpu_mem_gb, imgsz)
    lr, optimizer, lr_reason = _pick_lr_and_optimizer(n)

    return {
        "model_family": model_family.value,
        "task_type": task_type.value,
        "params": {
            "model": model_id,
            "epochs": epochs,
            "imgsz": imgsz,
            "batch": batch,
            "lr0": lr,
            "optimizer": optimizer,
            "augment": True,
        },
        "reasons": {
            "model": model_reason,
            "epochs": epochs_reason,
            "imgsz": imgsz_reason,
            "batch": batch_reason,
            "lr0_optimizer": lr_reason,
        },
        "assumptions": {
            "gpu_mem_gb": gpu_mem_gb,
            "image_count": n,
        },
    }
