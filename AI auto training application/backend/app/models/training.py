from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    BigInteger, Boolean, DateTime, Enum as SAEnum, ForeignKey, Integer, Numeric, Text, text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base
from app.models.enums import ArtifactKind, JobStatus


_job_status_t = SAEnum(
    JobStatus, name="job_status", create_type=False, native_enum=True,
    values_callable=lambda E: [e.value for e in E],
)
_artifact_kind_t = SAEnum(
    ArtifactKind, name="artifact_kind", create_type=False, native_enum=True,
    values_callable=lambda E: [e.value for e in E],
)


class TrainingJob(Base):
    """A single training run.

    Stores enough provenance to (a) reproduce the run, (b) compare it to other
    runs in the same project, and (c) let future AI agents reason over the
    sequence of runs without having to re-derive context from logs.
    """

    __tablename__ = "training_jobs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
    )
    dataset_version_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("dataset_versions.id"), nullable=False
    )
    status: Mapped[JobStatus] = mapped_column(
        _job_status_t, nullable=False, server_default=JobStatus.PENDING.value
    )
    progress: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    current_epoch: Mapped[int | None] = mapped_column(Integer, nullable=True)
    total_epochs: Mapped[int | None] = mapped_column(Integer, nullable=True)
    best_metric: Mapped[Decimal | None] = mapped_column(Numeric(8, 4), nullable=True)

    # The full hyperparameter dict the user submitted.
    params: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )

    # ---- provenance (added in migration 0005) ----
    # Summary written at training end:
    #   best_epoch, total_time_s, hardware (Python/torch/CUDA/GPU/RAM),
    #   exit_reason ('done' | 'stopped' | 'failed'), n_epochs_completed,
    #   diff_vs_recommendation (which keys the user changed)
    summary: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    # Frozen copy of the dataset_versions row at training start time.
    # Lets us interpret old runs even if the version row is later deleted.
    dataset_snapshot: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    # What the recommendation engine returned at start. Compare to `params`
    # to see what the user changed.
    recommendation_snapshot: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    # 'recommended' | 'default' | 'manual'
    preset_source: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Did the user click "Train anyway" despite blockers?
    override_blockers: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )
    # Git SHA or release tag of the backend at training start.
    app_version: Mapped[str | None] = mapped_column(Text, nullable=True)

    # ---- lifecycle ----
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), nullable=False
    )


class TrainingMetric(Base):
    __tablename__ = "training_metrics"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    training_job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("training_jobs.id", ondelete="CASCADE"),
        nullable=False,
    )
    epoch: Mapped[int] = mapped_column(Integer, nullable=False)
    loss: Mapped[Decimal | None] = mapped_column(Numeric(10, 6), nullable=True)
    val_loss: Mapped[Decimal | None] = mapped_column(Numeric(10, 6), nullable=True)
    precision: Mapped[Decimal | None] = mapped_column(Numeric(8, 4), nullable=True)
    recall: Mapped[Decimal | None] = mapped_column(Numeric(8, 4), nullable=True)
    map50: Mapped[Decimal | None] = mapped_column(Numeric(8, 4), nullable=True)
    map5095: Mapped[Decimal | None] = mapped_column(Numeric(8, 4), nullable=True)
    extra: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    # Per-class precision/recall/map at this epoch (typically only populated
    # on the final epoch by Ultralytics). Empty dict otherwise.
    per_class: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), nullable=False
    )


class TrainingArtifact(Base):
    __tablename__ = "training_artifacts"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    training_job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("training_jobs.id", ondelete="CASCADE"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    kind: Mapped[ArtifactKind] = mapped_column(
        _artifact_kind_t, nullable=False, server_default=ArtifactKind.OTHER.value
    )
    storage_uri: Mapped[str] = mapped_column(Text, nullable=False)
    size_bytes: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), nullable=False
    )
