"""cvat_connections + cvat_imports + source_type enum.

Revision ID: 0006
Revises: 0005
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0006"
down_revision: Union[str, None] = "0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


CVAT_SOURCE_VALUES = ("cvat_project", "cvat_task")


def upgrade() -> None:
    src = postgresql.ENUM(*CVAT_SOURCE_VALUES, name="cvat_source_type", create_type=True)
    src.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "cvat_connections",
        sa.Column("id", postgresql.UUID(as_uuid=True),
                  server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("base_url", sa.Text(), nullable=False),
        sa.Column("username", sa.Text(), nullable=False),
        # Fernet-encrypted CVAT token / password — never logged or returned in API.
        sa.Column("encrypted_secret", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_unique_constraint(
        "uq_cvat_connection_user_name",
        "cvat_connections", ["user_id", "name"],
    )

    op.create_table(
        "cvat_imports",
        sa.Column("id", postgresql.UUID(as_uuid=True),
                  server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("project_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("connection_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("cvat_connections.id", ondelete="SET NULL"),
                  nullable=True),
        sa.Column("source_type",
                  postgresql.ENUM(name="cvat_source_type", create_type=False),
                  nullable=False),
        sa.Column("source_id", sa.Integer(), nullable=False),
        sa.Column("source_name", sa.Text(), nullable=True),
        sa.Column("status",
                  postgresql.ENUM(name="job_status", create_type=False),
                  nullable=False, server_default="pending"),
        sa.Column("progress", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        # Tracks resumable state — rq_id, last step name, download_path, dataset_id.
        sa.Column("payload",
                  postgresql.JSONB(astext_type=sa.Text()),
                  nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_cvat_imports_project", "cvat_imports",
                    ["project_id", sa.text("created_at desc")])


def downgrade() -> None:
    op.drop_index("ix_cvat_imports_project", table_name="cvat_imports")
    op.drop_table("cvat_imports")
    op.drop_constraint("uq_cvat_connection_user_name", "cvat_connections", type_="unique")
    op.drop_table("cvat_connections")
    op.execute("drop type if exists cvat_source_type")
