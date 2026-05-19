from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import CvatSourceType, JobStatus


class CvatConnectionCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    base_url: str = Field(..., description="e.g. https://cvat.example.com")
    username: str = Field(min_length=1)
    # Either a CVAT API token (40+ char alnum) or a password — see client.py.
    secret: str = Field(min_length=1)


class CvatConnectionOut(BaseModel):
    """Public view — never exposes the encrypted secret."""
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    base_url: str
    username: str
    created_at: datetime
    last_used_at: datetime | None


class CvatConnectionListOut(BaseModel):
    items: list[CvatConnectionOut]
    total: int


class CvatProjectSummary(BaseModel):
    id: int
    name: str
    status: str | None = None
    tasks_count: int | None = None
    updated_date: str | None = None


class CvatTaskSummary(BaseModel):
    id: int
    name: str
    status: str | None = None
    size: int | None = None
    project_id: int | None = None
    updated_date: str | None = None


class CvatImportCreate(BaseModel):
    connection_id: uuid.UUID
    source_type: CvatSourceType
    source_id: int
    source_name: str | None = None
    # Auto-convert after ingest. Defaults to project's task_type-driven format.
    auto_convert: bool = True


class CvatImportOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    connection_id: uuid.UUID | None
    source_type: CvatSourceType
    source_id: int
    source_name: str | None
    status: JobStatus
    progress: int
    message: str | None
    error: str | None
    payload: dict[str, Any]
    attempts: int
    started_at: datetime | None
    finished_at: datetime | None
    created_at: datetime
