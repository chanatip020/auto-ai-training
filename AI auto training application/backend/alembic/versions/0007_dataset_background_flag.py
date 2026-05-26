"""datasets.treat_unlabeled_as_background

Adds a per-dataset opt-in that tells the converter and recommender that any
images shipped without a label file are intentional 'background images'
(no objects, used in YOLO training to reduce false positives), not an
annotation defect.

Revision ID: 0007
Revises: 0006
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0007"
down_revision: Union[str, None] = "0006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "datasets",
        sa.Column(
            "treat_unlabeled_as_background",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )


def downgrade() -> None:
    op.drop_column("datasets", "treat_unlabeled_as_background")
