"""add interview prep sessions table

Revision ID: 8b9c0d1e2f3a
Revises: 7a8b9c0d1e2f
Create Date: 2026-05-20 00:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "8b9c0d1e2f3a"
down_revision = "7a8b9c0d1e2f"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "interview_prep_sessions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("vacancy_id", sa.Uuid(), nullable=False),
        sa.Column("application_id", sa.Uuid(), nullable=False),
        sa.Column("prep_status", sa.String(length=50), nullable=False),
        sa.Column("readiness_score", sa.Integer(), nullable=True),
        sa.Column("competency_map_json", sa.JSON(), nullable=False),
        sa.Column("question_set_json", sa.JSON(), nullable=False),
        sa.Column("evidence_links_json", sa.JSON(), nullable=False),
        sa.Column("weak_areas_json", sa.JSON(), nullable=False),
        sa.Column("readiness_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.ForeignKeyConstraint(["application_id"], ["application_records.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["vacancy_id"], ["vacancies.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_index("ix_interview_prep_sessions_user_id", "interview_prep_sessions", ["user_id"])
    op.create_index("ix_interview_prep_sessions_vacancy_id", "interview_prep_sessions", ["vacancy_id"])
    op.create_index("ix_interview_prep_sessions_application_id", "interview_prep_sessions", ["application_id"])
    op.create_index(
        "ix_interview_prep_sessions_user_created",
        "interview_prep_sessions",
        ["user_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_interview_prep_sessions_user_created", table_name="interview_prep_sessions")
    op.drop_index("ix_interview_prep_sessions_application_id", table_name="interview_prep_sessions")
    op.drop_index("ix_interview_prep_sessions_vacancy_id", table_name="interview_prep_sessions")
    op.drop_index("ix_interview_prep_sessions_user_id", table_name="interview_prep_sessions")
    op.drop_table("interview_prep_sessions")
