"""training_jobs, training_metrics, training_artifacts.

Revision ID: 0004
Revises: 0003
Create Date: 2026-05-12
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


ARTIFACT_KIND_VALUES = ("weights", "plot", "log", "export", "other")


def upgrade() -> None:
    artifact_kind = postgresql.ENUM(*ARTIFACT_KIND_VALUES, name="artifact_kind", create_type=True)
    artifact_kind.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "training_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True),
                  server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("project_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("dataset_version_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("dataset_versions.id"), nullable=False),
        sa.Column("status",
                  postgresql.ENUM(name="job_status", create_type=False),
                  nullable=False, server_default="pending"),
        sa.Column("progress", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("current_epoch", sa.Integer(), nullable=True),
        sa.Column("total_epochs", sa.Integer(), nullable=True),
        sa.Column("best_metric", sa.Numeric(8, 4), nullable=True),
        sa.Column("params", postgresql.JSONB(astext_type=sa.Text()),
                  nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_training_jobs_project_status", "training_jobs",
                    ["project_id", "status"])

    op.create_table(
        "training_metrics",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("training_job_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("training_jobs.id", ondelete="CASCADE"),
                  nullable=False),
        sa.Column("epoch", sa.Integer(), nullable=False),
        sa.Column("loss", sa.Numeric(10, 6), nullable=True),
        sa.Column("val_loss", sa.Numeric(10, 6), nullable=True),
        sa.Column("precision", sa.Numeric(8, 4), nullable=True),
        sa.Column("recall", sa.Numeric(8, 4), nullable=True),
        sa.Column("map50", sa.Numeric(8, 4), nullable=True),
        sa.Column("map5095", sa.Numeric(8, 4), nullable=True),
        sa.Column("extra", postgresql.JSONB(astext_type=sa.Text()),
                  nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("recorded_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_training_metrics_job_epoch", "training_metrics",
                    ["training_job_id", "epoch"])

    op.create_table(
        "training_artifacts",
        sa.Column("id", postgresql.UUID(as_uuid=True),
                  server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("training_job_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("training_jobs.id", ondelete="CASCADE"),
                  nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("kind",
                  postgresql.ENUM(name="artifact_kind", create_type=False),
                  nullable=False, server_default="other"),
        sa.Column("storage_uri", sa.Text(), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_training_artifacts_job", "training_artifacts",
                    ["training_job_id"])


def downgrade() -> None:
    op.drop_index("ix_training_artifacts_job", table_name="training_artifacts")
    op.drop_table("training_artifacts")
    op.drop_index("ix_training_metrics_job_epoch", table_name="training_metrics")
    op.drop_table("training_metrics")
    op.drop_index("ix_training_jobs_project_status", table_name="training_jobs")
    op.drop_table("training_jobs")
    op.execute("drop type if exists artifact_kind")
