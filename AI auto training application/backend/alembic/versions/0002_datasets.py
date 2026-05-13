"""datasets, dataset_versions, jobs, plus job_status enum.

Revision ID: 0002
Revises: 0001
Create Date: 2026-05-12
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


JOB_STATUS_VALUES = ("pending", "running", "succeeded", "failed", "cancelled")
JOB_KIND_VALUES = ("ingest_zip", "ingest_files", "convert", "analyze", "train", "cvat_import")
DATASET_SOURCE_VALUES = ("upload", "cvat", "manual")


def upgrade() -> None:
    job_status = postgresql.ENUM(*JOB_STATUS_VALUES, name="job_status", create_type=True)
    job_kind = postgresql.ENUM(*JOB_KIND_VALUES, name="job_kind", create_type=True)
    dataset_source = postgresql.ENUM(
        *DATASET_SOURCE_VALUES, name="dataset_source", create_type=True
    )
    job_status.create(op.get_bind(), checkfirst=True)
    job_kind.create(op.get_bind(), checkfirst=True)
    dataset_source.create(op.get_bind(), checkfirst=True)

    # ---- datasets ----
    op.create_table(
        "datasets",
        sa.Column("id", postgresql.UUID(as_uuid=True),
                  server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("project_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("source",
                  postgresql.ENUM(name="dataset_source", create_type=False),
                  nullable=False, server_default="upload"),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_datasets_project_active", "datasets",
                    ["project_id"], postgresql_where=sa.text("deleted_at is null"))

    # ---- dataset_versions ----
    # Phase 2 puts only the columns we need now; the full schema (split,
    # num_images, classes, etc.) lands in Phase 3 when the converter runs.
    op.create_table(
        "dataset_versions",
        sa.Column("id", postgresql.UUID(as_uuid=True),
                  server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("dataset_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("datasets.id", ondelete="CASCADE"), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("format", sa.Text(), nullable=False, server_default="raw"),
        sa.Column("storage_uri", sa.Text(), nullable=False),
        sa.Column("num_images", sa.Integer(), nullable=True),
        sa.Column("num_labels", sa.Integer(), nullable=True),
        sa.Column("num_classes", sa.Integer(), nullable=True),
        sa.Column("classes",
                  postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("summary",
                  postgresql.JSONB(astext_type=sa.Text()),
                  nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("dataset_id", "version", name="uq_dataset_version"),
    )

    # ---- jobs ----
    op.create_table(
        "jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True),
                  server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("kind",
                  postgresql.ENUM(name="job_kind", create_type=False),
                  nullable=False),
        sa.Column("status",
                  postgresql.ENUM(name="job_status", create_type=False),
                  nullable=False, server_default="pending"),
        sa.Column("project_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=True),
        sa.Column("dataset_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("datasets.id", ondelete="CASCADE"), nullable=True),
        sa.Column("payload",
                  postgresql.JSONB(astext_type=sa.Text()),
                  nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("progress", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_jobs_kind_status", "jobs", ["kind", "status"])
    op.create_index("ix_jobs_project_created", "jobs",
                    ["project_id", sa.text("created_at desc")])


def downgrade() -> None:
    op.drop_index("ix_jobs_project_created", table_name="jobs")
    op.drop_index("ix_jobs_kind_status", table_name="jobs")
    op.drop_table("jobs")
    op.drop_table("dataset_versions")
    op.drop_index("ix_datasets_project_active", table_name="datasets")
    op.drop_table("datasets")
    op.execute("drop type if exists dataset_source")
    op.execute("drop type if exists job_kind")
    op.execute("drop type if exists job_status")
