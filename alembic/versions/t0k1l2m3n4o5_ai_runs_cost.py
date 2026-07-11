"""ai_runs.cost column (cost accounting)

Revision ID: t0k1l2m3n4o5
Revises: s9j0k1l2m3n4
Create Date: 2026-07-11 00:00:10.000000

Adds a ``cost`` column to ``ai_runs`` to persist the computed monetary cost
of each AI request (cost accounting, ТЗ §3.4). Nullable: historical rows and
failed runs have no cost.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "t0k1l2m3n4o5"
down_revision = "s9j0k1l2m3n4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "ai_runs",
        sa.Column("cost", sa.Numeric(12, 6), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("ai_runs", "cost")