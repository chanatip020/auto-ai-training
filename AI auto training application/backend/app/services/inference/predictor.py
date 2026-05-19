"""Inference + export for trained models.

Both `predict` and `export` are SYNCHRONOUS in v1 — fast enough for nano /
small YOLO models (predict ~0.5–2s for one image on CPU; ONNX export
~5–30s). If you train larger models or need batch inference, lift them
into the existing background-job system (see CONTRIBUTING.md).

We keep a small in-memory LRU of loaded YOLO models so repeated predictions
on the same training_job_id don't pay the cold-load cost (~1–2s) every time.
"""
from __future__ import annotations

import uuid
from collections import OrderedDict
from pathlib import Path
from threading import Lock
from typing import Any
from urllib.parse import urlparse

from app.core.errors import AppError
from app.models.training import TrainingArtifact, TrainingJob


# ---- model cache ----
_MAX_MODELS = 4
_cache: "OrderedDict[uuid.UUID, Any]" = OrderedDict()
_cache_lock = Lock()


def _ultralytics_available() -> bool:
    import importlib.util
    return importlib.util.find_spec("ultralytics") is not None


def _require_ultralytics() -> None:
    if not _ultralytics_available():
        raise AppError(
            "ULTRALYTICS_NOT_INSTALLED",
            (
                "The 'ultralytics' package is not installed in the API container.\n"
                "Install it:\n"
                "  docker compose exec api pip install ultralytics\n"
                "  (or: make install-training)"
            ),
            status_code=400,
        )


def _find_best_weights(tj: TrainingJob, artifacts: list[TrainingArtifact]) -> Path:
    """Locate the best.pt artifact for a finished training job."""
    # Prefer 'best.pt' over 'last.pt'.
    by_name = {a.name: a for a in artifacts}
    for name in ("best.pt", "last.pt"):
        a = by_name.get(name)
        if a and a.storage_uri.startswith("file://"):
            p = Path(urlparse(a.storage_uri).path)
            if p.exists():
                return p
    raise AppError(
        "WEIGHTS_NOT_FOUND",
        "Could not find best.pt or last.pt for this training job. "
        "Did training complete successfully?",
        status_code=404,
    )


def load_model(tj: TrainingJob, artifacts: list[TrainingArtifact]):
    """LRU-cached YOLO model loader. Returns an Ultralytics YOLO instance."""
    _require_ultralytics()
    with _cache_lock:
        if tj.id in _cache:
            _cache.move_to_end(tj.id)
            return _cache[tj.id]

    weights = _find_best_weights(tj, artifacts)

    from ultralytics import YOLO  # type: ignore
    model = YOLO(str(weights))

    with _cache_lock:
        _cache[tj.id] = model
        while len(_cache) > _MAX_MODELS:
            _cache.popitem(last=False)
    return model


def evict_model(training_job_id: uuid.UUID) -> None:
    """Drop a model from the cache (e.g. if its weights changed)."""
    with _cache_lock:
        _cache.pop(training_job_id, None)


# ---- prediction ----
def predict_image(
    tj: TrainingJob,
    artifacts: list[TrainingArtifact],
    image_bytes: bytes,
    *,
    conf: float = 0.25,
    iou: float = 0.7,
    imgsz: int | None = None,
) -> dict[str, Any]:
    """Run prediction on a single image. Returns a dict the API can serialize."""
    import io
    from PIL import Image

    model = load_model(tj, artifacts)

    # Open as PIL so we don't write to disk
    try:
        img = Image.open(io.BytesIO(image_bytes))
        img.verify()
        img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    except Exception as e:
        raise AppError("BAD_IMAGE", f"Could not decode image: {e}", status_code=400)

    # Run prediction
    results = model.predict(
        source=img, conf=conf, iou=iou,
        imgsz=imgsz or 640, verbose=False,
    )
    if not results:
        return {"width": img.width, "height": img.height, "predictions": []}

    r = results[0]
    return _result_to_json(r, image_size=(img.width, img.height))


def _result_to_json(r, *, image_size: tuple[int, int]) -> dict[str, Any]:
    """Convert an Ultralytics Result to a JSON-safe dict."""
    w, h = image_size
    names = r.names or {}
    preds: list[dict[str, Any]] = []

    # Detection / segmentation share .boxes; classification has .probs
    if getattr(r, "boxes", None) is not None and r.boxes is not None and len(r.boxes) > 0:
        # Detection / segmentation
        xyxy = r.boxes.xyxy.cpu().numpy().tolist() if hasattr(r.boxes, "xyxy") else []
        conf = r.boxes.conf.cpu().numpy().tolist() if hasattr(r.boxes, "conf") else []
        cls = r.boxes.cls.cpu().numpy().tolist() if hasattr(r.boxes, "cls") else []
        # Optional polygons for segmentation
        polys = None
        if getattr(r, "masks", None) is not None and r.masks is not None:
            try:
                polys = [m.tolist() for m in r.masks.xy]  # list of [N, 2] arrays
            except Exception:
                polys = None
        for i in range(len(xyxy)):
            cls_idx = int(cls[i]) if i < len(cls) else 0
            entry: dict[str, Any] = {
                "class_idx": cls_idx,
                "class_name": names.get(cls_idx, f"class_{cls_idx}"),
                "confidence": float(conf[i]) if i < len(conf) else 0.0,
                "bbox": [float(v) for v in xyxy[i]],  # [x1, y1, x2, y2]
            }
            if polys is not None and i < len(polys):
                entry["polygon"] = polys[i]
            preds.append(entry)
        return {"width": w, "height": h, "task": "detection", "predictions": preds}

    if getattr(r, "probs", None) is not None and r.probs is not None:
        # Classification: top-5
        top5_idx = r.probs.top5
        top5_conf = r.probs.top5conf.cpu().numpy().tolist()
        for j, (i, c) in enumerate(zip(top5_idx, top5_conf)):
            preds.append({
                "rank": j + 1,
                "class_idx": int(i),
                "class_name": names.get(int(i), f"class_{i}"),
                "confidence": float(c),
            })
        return {"width": w, "height": h, "task": "classification", "predictions": preds}

    return {"width": w, "height": h, "task": "unknown", "predictions": []}


# ---- export ----
SUPPORTED_EXPORT_FORMATS = ("onnx", "torchscript", "coreml", "tflite")


def export_model(
    tj: TrainingJob, artifacts: list[TrainingArtifact], *, format: str,
) -> Path:
    """Export the model. Returns the on-disk path of the new artifact."""
    _require_ultralytics()
    if format not in SUPPORTED_EXPORT_FORMATS:
        raise AppError(
            "UNSUPPORTED_EXPORT_FORMAT",
            f"Format {format!r} not supported. Try one of: {', '.join(SUPPORTED_EXPORT_FORMATS)}",
            status_code=400,
        )
    model = load_model(tj, artifacts)
    out = model.export(format=format)
    # Ultralytics returns a Path or str
    return Path(str(out))
