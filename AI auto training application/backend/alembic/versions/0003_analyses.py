"""analyses table — dataset analysis report + recommendations.

Revision ID: 0003
Revises: 0002
Create Date: 2026-05-12
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "analyses",
        sa.Column("id", postgresql.UUID(as_uuid=True),
                  server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("dataset_version_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("dataset_versions.id", ondelete="CASCADE"),
                  nullable=False),
        sa.Column("health_score", sa.Numeric(5, 2), nullable=True),
        sa.Column("findings", postgresql.JSONB(astext_type=sa.Text()),
                  nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("recommendations", postgresql.JSONB(astext_type=sa.Text()),
                  nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("ready_for_training", sa.Boolean(), nullable=False,
                  server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
    )
    op.create_index(
        "ix_analyses_version_created",
        "analyses",
        ["dataset_version_id", sa.text("created_at desc")],
    )


def downgrade() -> None:
    op.drop_index("ix_analyses_version_created", table_name="analyses")
    op.drop_table("analyses")
