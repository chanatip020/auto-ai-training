"""Hardware + app-version snapshot helpers for training_jobs.summary.

Captured at training start (hardware fingerprint) and at completion
(elapsed time, exit_reason, diff vs recommendation).
"""
from __future__ import annotations

import os
import platform
import subprocess
import sys
from typing import Any


def app_version() -> str:
    """Return git short SHA if we're in a git checkout, else env var, else 'unknown'."""
    if env := os.environ.get("APP_VERSION"):
        return env
    try:
        out = subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            stderr=subprocess.DEVNULL,
            cwd=os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            timeout=2,
        )
        return out.decode().strip()
    except Exception:
        return "unknown"


def hardware_fingerprint() -> dict[str, Any]:
    """Snapshot of the machine running training.

    Captures Python/torch/CUDA versions, GPU info if any, and basic RAM.
    Designed to be cheap (no GPU benchmarks) and dependency-light — torch
    imports are guarded so this works in containers without [training].
    """
    info: dict[str, Any] = {
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "machine": platform.machine(),
        "processor": platform.processor() or "unknown",
        "cpu_count": os.cpu_count(),
    }

    # RAM (Linux /proc/meminfo; everywhere else: skip)
    try:
        with open("/proc/meminfo") as f:
            for line in f:
                if line.startswith("MemTotal:"):
                    kb = int(line.split()[1])
                    info["ram_gb"] = round(kb / 1024 / 1024, 1)
                    break
    except (OSError, ValueError):
        pass

    # Torch + CUDA (optional)
    try:
        import torch  # type: ignore
        info["torch"] = torch.__version__
        if torch.cuda.is_available():
            info["cuda"] = {
                "available": True,
                "device_count": torch.cuda.device_count(),
                "devices": [torch.cuda.get_device_name(i)
                            for i in range(torch.cuda.device_count())],
                "version": torch.version.cuda,
            }
        else:
            info["cuda"] = {"available": False}
    except ImportError:
        info["torch"] = "not_installed"

    # Ultralytics (optional)
    try:
        import ultralytics  # type: ignore
        info["ultralytics"] = ultralytics.__version__
    except ImportError:
        info["ultralytics"] = "not_installed"

    return info


def params_diff_vs_recommendation(
    params: dict[str, Any], recommendation: dict[str, Any] | None,
) -> dict[str, Any]:
    """Compute which user-submitted param keys diverged from the recommendation.

    Returns {"changed": {k: {"recommended": v_rec, "submitted": v_user}}, "matched": [k, ...]}
    Useful signal for AI agents: "user always lowers lr by 10x — bake that in".
    """
    if not recommendation:
        return {"changed": {}, "matched": []}
    rec_params = recommendation.get("params") if isinstance(recommendation, dict) else None
    if not isinstance(rec_params, dict):
        return {"changed": {}, "matched": []}

    changed: dict[str, dict[str, Any]] = {}
    matched: list[str] = []
    for k, v_user in params.items():
        if k in rec_params:
            v_rec = rec_params[k]
            if _values_differ(v_user, v_rec):
                changed[k] = {"recommended": v_rec, "submitted": v_user}
            else:
                matched.append(k)
    return {"changed": changed, "matched": sorted(matched)}


def _values_differ(a: Any, b: Any) -> bool:
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return abs(float(a) - float(b)) > 1e-6
    return a != b


def dataset_snapshot(version) -> dict[str, Any]:
    """Frozen copy of a DatasetVersion row at training start.

    Stored on training_jobs.dataset_snapshot so later interpretation of the
    run isn't broken if the version row is deleted.
    """
    return {
        "id": str(version.id),
        "dataset_id": str(version.dataset_id),
        "version": version.version,
        "format": version.format,
        "storage_uri": version.storage_uri,
        "num_images": version.num_images,
        "num_labels": version.num_labels,
        "num_classes": version.num_classes,
        "classes": version.classes,
        "summary": version.summary or {},
        "created_at": version.created_at.isoformat() if version.created_at else None,
    }
