from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import ArtifactKind, JobStatus


class TrainingStartRequest(BaseModel):
    dataset_version_id: uuid.UUID
    params: dict[str, Any] = Field(
        default_factory=dict,
        description="Hyperparameters; missing keys filled from recommendation defaults.",
        examples=[{"model": "yolov8n", "epochs": 50, "imgsz": 640,
                   "batch": 16, "lr0": 0.01, "optimizer": "auto"}],
    )


class TrainingJobOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    dataset_version_id: uuid.UUID
    status: JobStatus
    progress: int
    current_epoch: int | None
    total_epochs: int | None
    best_metric: Decimal | None
    params: dict[str, Any]
    message: str | None
    error: str | None
    started_at: datetime | None
    finished_at: datetime | None
    created_at: datetime


class TrainingJobListOut(BaseModel):
    items: list[TrainingJobOut]
    total: int


class TrainingMetricOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    epoch: int
    loss: Decimal | None
    val_loss: Decimal | None
    precision: Decimal | None
    recall: Decimal | None
    map50: Decimal | None
    map5095: Decimal | None
    extra: dict[str, Any]
    recorded_at: datetime


class TrainingMetricsOut(BaseModel):
    items: list[TrainingMetricOut]


class TrainingArtifactOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    kind: ArtifactKind
    storage_uri: str
    size_bytes: int | None
    created_at: datetime


class TrainingArtifactsOut(BaseModel):
    items: list[TrainingArtifactOut]
