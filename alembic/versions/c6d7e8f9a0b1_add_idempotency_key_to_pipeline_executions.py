"""add idempotency_key to pipeline_executions

Revision ID: c6d7e8f9a0b1
Revises: b4c5d6e7f8a9
Create Date: 2026-05-18 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "c6d7e8f9a0b1"
down_revision: Union[str, Sequence[str], None] = "b4c5d6e7f8a9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE pipeline_executions
        ADD COLUMN IF NOT EXISTS idempotency_key VARCHAR(100)
        """
    )
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_pipeline_executions_idempotency_key
        ON pipeline_executions (user_id, document_id, vacancy_id, idempotency_key)
        WHERE idempotency_key IS NOT NULL
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uq_pipeline_executions_idempotency_key")
    op.execute("ALTER TABLE pipeline_executions DROP COLUMN IF EXISTS idempotency_key")
