"""add mock interview fields to interview sessions

Revision ID: 7a8b9c0d1e2f
Revises: d7e8f9a0b1c2
Create Date: 2026-05-19 00:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "7a8b9c0d1e2f"
down_revision = "d7e8f9a0b1c2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "interview_sessions",
        sa.Column(
            "mode",
            sa.String(length=50),
            nullable=False,
            server_default="preparation",
        ),
    )
    op.add_column(
        "interview_sessions",
        sa.Column("current_question_index", sa.Integer(), nullable=True),
    )
    op.add_column(
        "interview_sessions",
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("interview_sessions", "completed_at")
    op.drop_column("interview_sessions", "current_question_index")
    op.drop_column("interview_sessions", "mode")
