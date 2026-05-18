"""add retry fields to pipeline_executions

Revision ID: b4c5d6e7f8a9
Revises: a1b2c3d4e5f7, a9d7c6b5e4f3
Create Date: 2026-05-18 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "b4c5d6e7f8a9"
down_revision: Union[str, Sequence[str], None] = ("a1b2c3d4e5f7", "a9d7c6b5e4f3")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE pipeline_executions
        ADD COLUMN IF NOT EXISTS retry_count INTEGER NOT NULL DEFAULT 0
        """
    )
    op.execute(
        """
        ALTER TABLE pipeline_executions
        ADD COLUMN IF NOT EXISTS failed_step VARCHAR(100)
        """
    )
    op.execute(
        """
        ALTER TABLE pipeline_executions
        ADD COLUMN IF NOT EXISTS last_error TEXT
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_pipeline_executions_failed_step
        ON pipeline_executions (failed_step)
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_pipeline_executions_failed_step")
    op.execute("ALTER TABLE pipeline_executions DROP COLUMN IF EXISTS last_error")
    op.execute("ALTER TABLE pipeline_executions DROP COLUMN IF EXISTS failed_step")
    op.execute("ALTER TABLE pipeline_executions DROP COLUMN IF EXISTS retry_count")
