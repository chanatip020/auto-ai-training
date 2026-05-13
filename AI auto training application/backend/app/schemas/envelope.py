"""Standard JSON response envelope used by every endpoint."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class Meta(BaseModel):
    request_id: str | None = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ErrorBody(BaseModel):
    code: str
    message: str
    details: dict[str, Any] = Field(default_factory=dict)


class Envelope(BaseModel, Generic[T]):
    data: T | None = None
    error: ErrorBody | None = None
    meta: Meta = Field(default_factory=Meta)


def ok(data: T, request_id: str | None = None) -> Envelope[T]:
    return Envelope[T](data=data, error=None, meta=Meta(request_id=request_id))
