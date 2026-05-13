from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict

from app.models.enums import JobKind, JobStatus


class JobOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    kind: JobKind
    status: JobStatus
    project_id: uuid.UUID | None
    dataset_id: uuid.UUID | None
    payload: dict[str, Any]
    progress: int
    message: str | None
    error: str | None
    started_at: datetime | None
    finished_at: datetime | None
    created_at: datetime


class JobAcceptedOut(BaseModel):
    """Returned from endpoints that schedule background work."""
    job_id: uuid.UUID
