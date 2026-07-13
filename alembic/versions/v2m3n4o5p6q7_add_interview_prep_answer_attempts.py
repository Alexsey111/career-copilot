"""add interview prep answer attempts table

Revision ID: v2m3n4o5p6q7
Revises: u1l2m3n4o5p6
Create Date: 2026-07-13 00:00:00.000000

Новая таблица per-criterion rubric scoring ответов кандидата на practice-кейсы
(Этап 9.F). Без backfill — таблица новая. Образец: 8b9c0d1e2f3a.
answer_text хранится зашифрованным (EncryptedText=Text at DDL, ФЗ-152 ст.19).
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "v2m3n4o5p6q7"
down_revision = "u1l2m3n4o5p6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "interview_prep_answer_attempts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("vacancy_id", sa.Uuid(), nullable=False),
        sa.Column("case_id", sa.String(length=64), nullable=False),
        sa.Column("case_type", sa.String(length=50), nullable=False),
        sa.Column("answer_text", sa.Text(), nullable=False),
        sa.Column("criterion_scores_json", sa.JSON(), nullable=False),
        sa.Column("overall_score", sa.Float(), nullable=False),
        sa.Column("grade", sa.String(length=20), nullable=False),
        sa.Column("feedback_json", sa.JSON(), nullable=False),
        sa.Column("rubric_version", sa.String(length=20), nullable=False, server_default="deterministic_v1"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["vacancy_id"], ["vacancies.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_index(
        "ix_interview_prep_answer_attempts_user_id",
        "interview_prep_answer_attempts",
        ["user_id"],
    )
    op.create_index(
        "ix_interview_prep_answer_attempts_vacancy_id",
        "interview_prep_answer_attempts",
        ["vacancy_id"],
    )
    op.create_index(
        "ix_interview_prep_answer_attempts_case_id",
        "interview_prep_answer_attempts",
        ["case_id"],
    )
    op.create_index(
        "ix_interview_prep_answer_attempts_user_vacancy_case",
        "interview_prep_answer_attempts",
        ["user_id", "vacancy_id", "case_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_interview_prep_answer_attempts_user_vacancy_case",
        table_name="interview_prep_answer_attempts",
    )
    op.drop_index(
        "ix_interview_prep_answer_attempts_case_id",
        table_name="interview_prep_answer_attempts",
    )
    op.drop_index(
        "ix_interview_prep_answer_attempts_vacancy_id",
        table_name="interview_prep_answer_attempts",
    )
    op.drop_index(
        "ix_interview_prep_answer_attempts_user_id",
        table_name="interview_prep_answer_attempts",
    )
    op.drop_table("interview_prep_answer_attempts")