"""expand vacancy and vacancy_analysis models

Revision ID: k1b2c3d4e5f6
Revises: j0a1b2c3d4e5
Create Date: 2026-07-02 00:00:01.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "k1b2c3d4e5f6"
down_revision = "j0a1b2c3d4e5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Vacancy: new columns
    op.add_column("vacancies", sa.Column("employment_type", sa.String(50), nullable=True))
    op.add_column("vacancies", sa.Column("experience_level", sa.String(50), nullable=True))
    op.add_column("vacancies", sa.Column("published_at", sa.DateTime(timezone=True), nullable=True))

    # VacancyAnalysis: new columns
    op.add_column("vacancy_analyses", sa.Column("risks_json", sa.JSON(), nullable=False, server_default="[]"))
    op.add_column("vacancy_analyses", sa.Column("match_logic_json", sa.JSON(), nullable=False, server_default="{}"))
    op.add_column("vacancy_analyses", sa.Column("language_tone_hints_json", sa.JSON(), nullable=False, server_default="{}"))


def downgrade() -> None:
    op.drop_column("vacancy_analyses", "language_tone_hints_json")
    op.drop_column("vacancy_analyses", "match_logic_json")
    op.drop_column("vacancy_analyses", "risks_json")
    op.drop_column("vacancies", "published_at")
    op.drop_column("vacancies", "experience_level")
    op.drop_column("vacancies", "employment_type")
