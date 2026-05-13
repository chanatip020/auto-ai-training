"""initial schema — users, projects, audit_log, plus enum types.

Revision ID: 0001
Revises:
Create Date: 2026-05-08
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


PROJECT_STATUS_VALUES = (
    "created",
    "dataset_uploaded",
    "dataset_analyzed",
    "ready_for_training",
    "training",
    "completed",
    "failed",
)
MODEL_FAMILY_VALUES = ("yolo",)
TASK_TYPE_VALUES = ("detection", "segmentation", "classification")


def upgrade() -> None:
    # Enable pgcrypto for gen_random_uuid() if not already (Supabase has it on by default).
    op.execute('create extension if not exists "pgcrypto"')

    project_status = postgresql.ENUM(
        *PROJECT_STATUS_VALUES, name="project_status", create_type=True
    )
    model_family = postgresql.ENUM(
        *MODEL_FAMILY_VALUES, name="model_family", create_type=True
    )
    task_type = postgresql.ENUM(
        *TASK_TYPE_VALUES, name="task_type", create_type=True
    )
    project_status.create(op.get_bind(), checkfirst=True)
    model_family.create(op.get_bind(), checkfirst=True)
    task_type.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True),
                  server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("email", sa.Text(), nullable=False, unique=True),
        sa.Column("display_name", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
    )

    op.create_table(
        "projects",
        sa.Column("id", postgresql.UUID(as_uuid=True),
                  server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("model_family",
                  postgresql.ENUM(name="model_family", create_type=False),
                  nullable=False, server_default="yolo"),
        sa.Column("task_type",
                  postgresql.ENUM(name="task_type", create_type=False),
                  nullable=False, server_default="detection"),
        sa.Column("status",
                  postgresql.ENUM(name="project_status", create_type=False),
                  nullable=False, server_default="created"),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_projects_user_status_active",
        "projects",
        ["user_id", "status"],
        postgresql_where=sa.text("deleted_at is null"),
    )

    op.create_table(
        "audit_log",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("project_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("event", sa.Text(), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()),
                  nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("actor", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_audit_project_created", "audit_log",
                    ["project_id", sa.text("created_at desc")])


def downgrade() -> None:
    op.drop_index("ix_audit_project_created", table_name="audit_log")
    op.drop_table("audit_log")
    op.drop_index("ix_projects_user_status_active", table_name="projects")
    op.drop_table("projects")
    op.drop_table("users")
    op.execute("drop type if exists project_status")
    op.execute("drop type if exists model_family")
    op.execute("drop type if exists task_type")
