from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import ArtifactKind, JobStatus


class TrainingStartRequest(BaseModel):
    dataset_version_id: uuid.UUID
    params: dict[str, Any] = Field(
        default_factory=dict,
        description="Hyperparameters; missing keys filled from defaults.",
        examples=[{"model": "yolov8n", "epochs": 50, "imgsz": 640,
                   "batch": 16, "lr0": 0.01, "optimizer": "auto"}],
    )
    # ---- provenance fields (Phase 8) ----
    preset_source: Literal["recommended", "default", "manual"] | None = Field(
        default=None,
        description="Which preset the user started from before editing.",
    )
    override_blockers: bool = Field(
        default=False,
        description="True if the user opted to train despite a 'not ready' analysis.",
    )
    recommendation_snapshot: dict[str, Any] | None = Field(
        default=None,
        description=(
            "Optional snapshot of what the recommendation engine returned at start "
            "time. Used to compute params-vs-recommendation diff for later analysis."
        ),
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
    # Provenance (Phase 8)
    summary: dict[str, Any]
    dataset_snapshot: dict[str, Any] | None
    recommendation_snapshot: dict[str, Any] | None
    preset_source: str | None
    override_blockers: bool
    app_version: str | None
    # Lifecycle
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
    per_class: dict[str, Any]
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


# ---- Phase 8 history endpoints ----

class TrainingHistoryItem(BaseModel):
    """A summarised row for the project's training-history page."""
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    dataset_version_id: uuid.UUID
    status: JobStatus
    best_metric: Decimal | None
    total_epochs: int | None
    current_epoch: int | None
    # Model + key params hoisted from params jsonb for cheap sorting/display
    params: dict[str, Any]
    summary: dict[str, Any]
    preset_source: str | None
    override_blockers: bool
    started_at: datetime | None
    finished_at: datetime | None
    created_at: datetime


class TrainingHistoryOut(BaseModel):
    items: list[TrainingHistoryItem]
    total: int


class CloneConfigOut(BaseModel):
    """The params + readiness state needed to re-create a past run."""
    dataset_version_id: uuid.UUID
    params: dict[str, Any]
    preset_source: str | None
    override_blockers: bool
