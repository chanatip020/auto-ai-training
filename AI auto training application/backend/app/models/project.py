from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum as SAEnum, ForeignKey, Text, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base
from app.models.enums import ModelFamily, ProjectStatus, TaskType


# Use sqlalchemy.Enum (not postgresql.ENUM) so SELECT returns the Python enum,
# not a raw string. The Postgres type itself was created by the alembic
# migration; create_type=False tells SQLAlchemy not to try to recreate it.
_project_status_t = SAEnum(
    ProjectStatus, name="project_status", create_type=False, native_enum=True,
    values_callable=lambda E: [e.value for e in E],
)
_model_family_t = SAEnum(
    ModelFamily, name="model_family", create_type=False, native_enum=True,
    values_callable=lambda E: [e.value for e in E],
)
_task_type_t = SAEnum(
    TaskType, name="task_type", create_type=False, native_enum=True,
    values_callable=lambda E: [e.value for e in E],
)


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    model_family: Mapped[ModelFamily] = mapped_column(
        _model_family_t, nullable=False, server_default=ModelFamily.YOLO.value
    )
    task_type: Mapped[TaskType] = mapped_column(
        _task_type_t, nullable=False, server_default=TaskType.DETECTION.value
    )
    status: Mapped[ProjectStatus] = mapped_column(
        _project_status_t, nullable=False, server_default=ProjectStatus.CREATED.value
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), nullable=False
    )
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
