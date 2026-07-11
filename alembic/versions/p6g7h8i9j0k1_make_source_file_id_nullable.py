"""make file_extractions.source_file_id nullable

Revision ID: p6g7h8i9j0k1
Revises: o5f6g7h8i9j0
Create Date: 2026-07-03 00:00:06.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "p6g7h8i9j0k1"
down_revision = "o5f6g7h8i9j0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "file_extractions",
        "source_file_id",
        existing_type=sa.Uuid(),
        nullable=True,
    )


def downgrade() -> None:
    op.alter_column(
        "file_extractions",
        "source_file_id",
        existing_type=sa.Uuid(),
        nullable=False,
    )
