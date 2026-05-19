from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Enum as SAEnum, ForeignKey, Integer, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base
from app.models.enums import CvatSourceType, JobStatus


_job_status_t = SAEnum(
    JobStatus, name="job_status", create_type=False, native_enum=True,
    values_callable=lambda E: [e.value for e in E],
)
_cvat_src_t = SAEnum(
    CvatSourceType, name="cvat_source_type", create_type=False, native_enum=True,
    values_callable=lambda E: [e.value for e in E],
)


class CvatConnection(Base):
    """Saved CVAT-server credentials.

    `encrypted_secret` stores a Fernet-encrypted password OR API token,
    decrypted only when the CVAT client needs to authenticate. Never
    returned by any API endpoint.
    """

    __tablename__ = "cvat_connections"
    __table_args__ = (
        UniqueConstraint("user_id", "name", name="uq_cvat_connection_user_name"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    base_url: Mapped[str] = mapped_column(Text, nullable=False)
    username: Mapped[str] = mapped_column(Text, nullable=False)
    encrypted_secret: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), nullable=False
    )
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class CvatImport(Base):
    """A single import run from a CVAT project or task into one of our projects."""

    __tablename__ = "cvat_imports"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    connection_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("cvat_connections.id", ondelete="SET NULL"),
        nullable=True,
    )
    source_type: Mapped[CvatSourceType] = mapped_column(_cvat_src_t, nullable=False)
    source_id: Mapped[int] = mapped_column(Integer, nullable=False)
    source_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[JobStatus] = mapped_column(
        _job_status_t, nullable=False, server_default=JobStatus.PENDING.value
    )
    progress: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    payload: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), nullable=False
    )
