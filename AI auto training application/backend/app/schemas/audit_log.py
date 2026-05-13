from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class AuditLogOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    project_id: uuid.UUID
    event: str
    payload: dict[str, Any]
    actor: str | None
    created_at: datetime


class TimelineOut(BaseModel):
    items: list[AuditLogOut]
