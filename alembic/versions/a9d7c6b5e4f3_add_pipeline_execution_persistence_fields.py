"""add pipeline execution persistence fields

Revision ID: a9d7c6b5e4f3
Revises: 4f9a1b2c3d4e
Create Date: 2026-05-14 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "a9d7c6b5e4f3"
down_revision: Union[str, Sequence[str], None] = "4f9a1b2c3d4e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE pipeline_executions
        ADD COLUMN IF NOT EXISTS review_required BOOLEAN NOT NULL DEFAULT FALSE
        """
    )
    op.execute(
        """
        ALTER TABLE pipeline_executions
        ADD COLUMN IF NOT EXISTS review_completed BOOLEAN NOT NULL DEFAULT FALSE
        """
    )
    op.execute(
        """
        ALTER TABLE pipeline_executions
        ADD COLUMN IF NOT EXISTS execution_duration_ms INTEGER
        """
    )
    op.execute(
        """
        ALTER TABLE pipeline_executions
        ADD COLUMN IF NOT EXISTS evaluation_duration_ms INTEGER
        """
    )
    op.execute(
        """
        ALTER TABLE pipeline_executions
        ADD COLUMN IF NOT EXISTS mutation_duration_ms INTEGER
        """
    )

    op.execute(
        """
        UPDATE pipeline_executions
        SET execution_duration_ms = COALESCE(execution_duration_ms, duration_ms)
        WHERE execution_duration_ms IS NULL AND duration_ms IS NOT NULL
        """
    )


def downgrade() -> None:
    op.execute("ALTER TABLE pipeline_executions DROP COLUMN IF EXISTS mutation_duration_ms")
    op.execute("ALTER TABLE pipeline_executions DROP COLUMN IF EXISTS evaluation_duration_ms")
    op.execute("ALTER TABLE pipeline_executions DROP COLUMN IF EXISTS execution_duration_ms")
    op.execute("ALTER TABLE pipeline_executions DROP COLUMN IF EXISTS review_completed")
    op.execute("ALTER TABLE pipeline_executions DROP COLUMN IF EXISTS review_required")
