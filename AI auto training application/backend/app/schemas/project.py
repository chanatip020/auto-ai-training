from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import ModelFamily, ProjectStatus, TaskType


class ProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    model_family: ModelFamily = ModelFamily.YOLO
    task_type: TaskType = TaskType.DETECTION


class ProjectUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2000)


class ProjectStatusUpdate(BaseModel):
    """Allows manual status transitions in v1; later phases drive this automatically."""
    status: ProjectStatus


class ProjectOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    description: str | None
    model_family: ModelFamily
    task_type: TaskType
    status: ProjectStatus
    created_at: datetime
    updated_at: datetime


class ProjectListOut(BaseModel):
    items: list[ProjectOut]
    total: int
