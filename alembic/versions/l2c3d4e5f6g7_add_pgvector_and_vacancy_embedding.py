"""add pgvector extension and vacancy embedding column

Revision ID: l2c3d4e5f6g7
Revises: k1b2c3d4e5f6
Create Date: 2026-07-02 00:00:02.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "l2c3d4e5f6g7"
down_revision = "k1b2c3d4e5f6"
branch_labels = None
depends_on = None


def _has_vector_extension(bind) -> bool:
    try:
        result = bind.execute(
            sa.text("SELECT 1 FROM pg_extension WHERE extname = 'vector'")
        )
        return result.scalar() is not None
    except Exception:
        return False


def upgrade() -> None:
    bind = op.get_bind()
    has_vector = _has_vector_extension(bind)

    if has_vector:
        op.add_column(
            "vacancies",
            sa.Column("embedding", sa.dialects.postgresql.VECTOR(384), nullable=True),
        )
        try:
            op.execute(
                "CREATE INDEX ix_vacancies_embedding ON vacancies "
                "USING ivfflat (embedding vector_cosine_ops) WITH (lists = 10)"
            )
        except Exception:
            pass
    else:
        op.add_column(
            "vacancies",
            sa.Column("embedding", sa.Text(), nullable=True),
        )


def downgrade() -> None:
    try:
        op.execute("DROP INDEX IF EXISTS ix_vacancies_embedding")
    except Exception:
        pass
    op.drop_column("vacancies", "embedding")
