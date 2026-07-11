"""add technologies_json to candidate_profiles

Revision ID: q7h8i9j0k1l2
Revises: p6g7h8i9j0k1
Create Date: 2026-07-05 00:00:07.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "q7h8i9j0k1l2"
down_revision = "p6g7h8i9j0k1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "candidate_profiles",
        sa.Column("technologies_json", sa.JSON(), nullable=False, server_default="[]"),
    )


def downgrade() -> None:
    op.drop_column("candidate_profiles", "technologies_json")
