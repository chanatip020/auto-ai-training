"""training_jobs provenance + per-class metrics.

Add columns so AI-agent phases (16/17) and history-comparison features
(Phase 8) have the data they need:

  training_jobs:
    + summary                jsonb  — best_epoch, total_time_s, hw fingerprint, exit_reason
    + dataset_snapshot       jsonb  — frozen copy of dataset_versions row at start
    + recommendation_snapshot jsonb — what the rec engine returned at start
    + preset_source          text   — 'recommended' | 'default' | 'manual'
    + override_blockers      bool   — did user override ready_for_training=false?
    + app_version            text   — git SHA or release tag

  training_metrics:
    + per_class              jsonb  — final-epoch per-class precision/recall/map

Revision ID: 0005
Revises: 0004
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0005"
down_revision: Union[str, None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # training_jobs additions
    op.add_column(
        "training_jobs",
        sa.Column("summary", postgresql.JSONB(astext_type=sa.Text()),
                  nullable=False, server_default=sa.text("'{}'::jsonb")),
    )
    op.add_column(
        "training_jobs",
        sa.Column("dataset_snapshot", postgresql.JSONB(astext_type=sa.Text()),
                  nullable=True),
    )
    op.add_column(
        "training_jobs",
        sa.Column("recommendation_snapshot", postgresql.JSONB(astext_type=sa.Text()),
                  nullable=True),
    )
    op.add_column(
        "training_jobs",
        sa.Column("preset_source", sa.Text(), nullable=True),
    )
    op.add_column(
        "training_jobs",
        sa.Column("override_blockers", sa.Boolean(), nullable=False,
                  server_default=sa.text("false")),
    )
    op.add_column(
        "training_jobs",
        sa.Column("app_version", sa.Text(), nullable=True),
    )

    # training_metrics addition
    op.add_column(
        "training_metrics",
        sa.Column("per_class", postgresql.JSONB(astext_type=sa.Text()),
                  nullable=False, server_default=sa.text("'{}'::jsonb")),
    )


def downgrade() -> None:
    op.drop_column("training_metrics", "per_class")
    op.drop_column("training_jobs", "app_version")
    op.drop_column("training_jobs", "override_blockers")
    op.drop_column("training_jobs", "preset_source")
    op.drop_column("training_jobs", "recommendation_snapshot")
    op.drop_column("training_jobs", "dataset_snapshot")
    op.drop_column("training_jobs", "summary")
