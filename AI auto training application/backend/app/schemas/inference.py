from __future__ import annotations

import uuid
from typing import Any, Literal

from pydantic import BaseModel, Field


class Prediction(BaseModel):
    class_idx: int
    class_name: str
    confidence: float
    bbox: list[float] | None = None       # [x1, y1, x2, y2] in image px
    polygon: list[list[float]] | None = None
    rank: int | None = None                # classification only


class PredictionResult(BaseModel):
    width: int
    height: int
    task: str
    predictions: list[Prediction]


class ExportRequest(BaseModel):
    format: Literal["onnx", "torchscript", "coreml", "tflite"]


class ExportResult(BaseModel):
    artifact_id: uuid.UUID
    name: str
    storage_uri: str
    size_bytes: int | None
