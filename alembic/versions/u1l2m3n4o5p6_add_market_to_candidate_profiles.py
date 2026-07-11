"""add market column to candidate_profiles (jurisdiction switch RU/EU/US)

Revision ID: u1l2m3n4o5p6
Revises: t0k1l2m3n4o5
Create Date: 2026-07-12 00:00:11.000000

Adds a ``market`` column to ``candidate_profiles`` to persist the candidate's
target jurisdiction (RU/EU/US) — Этап 7. Nullable: historical rows have no
market; auto-detection and explicit intake/PATCH set it going forward.
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "u1l2m3n4o5p6"
down_revision = "t0k1l2m3n4o5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "candidate_profiles",
        sa.Column("market", sa.String(8), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("candidate_profiles", "market")