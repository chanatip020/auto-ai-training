from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Enum as SAEnum, ForeignKey, Integer, Text, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base
from app.models.enums import JobKind, JobStatus


_job_status_t = SAEnum(
    JobStatus, name="job_status", create_type=False, native_enum=True,
    values_callable=lambda E: [e.value for e in E],
)
_job_kind_t = SAEnum(
    JobKind, name="job_kind", create_type=False, native_enum=True,
    values_callable=lambda E: [e.value for e in E],
)


class Job(Base):
    """Generic background-job tracker.

    One row per long-running task (zip ingest, conversion, analysis, training,
    CVAT import). The UI polls /jobs/{id} for status + progress; later phases
    add SSE for richer live updates.
    """

    __tablename__ = "jobs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    kind: Mapped[JobKind] = mapped_column(_job_kind_t, nullable=False)
    status: Mapped[JobStatus] = mapped_column(
        _job_status_t, nullable=False, server_default=JobStatus.PENDING.value
    )
    project_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=True, index=True,
    )
    dataset_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("datasets.id", ondelete="CASCADE"),
        nullable=True,
    )
    payload: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    progress: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), nullable=False
    )
