from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import DatasetSource


class DatasetCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    source: DatasetSource = DatasetSource.UPLOAD


class DatasetOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    name: str
    source: DatasetSource
    created_at: datetime


class DatasetVersionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    dataset_id: uuid.UUID
    version: int
    format: str
    storage_uri: str
    num_images: int | None
    num_labels: int | None
    num_classes: int | None
    classes: list[str] | None
    summary: dict[str, Any]
    created_at: datetime


class DatasetDetailOut(BaseModel):
    """Full view: dataset + its versions."""
    model_config = ConfigDict(from_attributes=True)

    dataset: DatasetOut
    versions: list[DatasetVersionOut]


class DatasetListOut(BaseModel):
    items: list[DatasetOut]
    total: int


class SplitRatios(BaseModel):
    train: float = Field(0.7, ge=0.0, le=1.0)
    val: float = Field(0.2, ge=0.0, le=1.0)
    test: float = Field(0.1, ge=0.0, le=1.0)


class DatasetConvertRequest(BaseModel):
    """Body of POST /datasets/{id}/convert."""
    format: str = Field(
        ...,
        description="One of: yolo-det, yolo-seg, yolo-cls",
        examples=["yolo-det"],
    )
    ratios: SplitRatios | None = None
    classes_override: list[str] | None = Field(
        default=None,
        description="Explicit class list. Overrides any classes.txt in the upload.",
    )
