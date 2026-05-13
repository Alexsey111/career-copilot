"""align pipeline_executions minimum fields

Revision ID: 4f9a1b2c3d4e
Revises: 167331481783
Create Date: 2026-05-13 15:10:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "4f9a1b2c3d4e"
down_revision: Union[str, Sequence[str], None] = "167331481783"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE pipeline_executions
        ADD COLUMN IF NOT EXISTS document_id UUID
        """
    )
    op.execute(
        """
        ALTER TABLE pipeline_executions
        ADD COLUMN IF NOT EXISTS execution_type VARCHAR(50) NOT NULL DEFAULT 'generic'
        """
    )
    op.execute(
        """
        ALTER TABLE pipeline_executions
        ADD COLUMN IF NOT EXISTS trigger_type VARCHAR(50) NOT NULL DEFAULT 'manual'
        """
    )
    op.execute(
        """
        ALTER TABLE pipeline_executions
        ADD COLUMN IF NOT EXISTS failure_reason TEXT
        """
    )
    op.execute(
        """
        ALTER TABLE pipeline_executions
        ADD COLUMN IF NOT EXISTS failure_code VARCHAR(100)
        """
    )
    op.execute(
        """
        ALTER TABLE pipeline_executions
        ADD COLUMN IF NOT EXISTS duration_ms INTEGER
        """
    )
    op.execute(
        """
        ALTER TABLE pipeline_executions
        ADD COLUMN IF NOT EXISTS output_artifact_ids JSON NOT NULL DEFAULT '[]'::json
        """
    )
    op.execute(
        """
        ALTER TABLE pipeline_executions
        ADD COLUMN IF NOT EXISTS input_params JSON NOT NULL DEFAULT '{}'::json
        """
    )
    op.execute(
        """
        ALTER TABLE pipeline_executions
        ADD COLUMN IF NOT EXISTS metadata_json JSON NOT NULL DEFAULT '{}'::json
        """
    )

    op.create_index(
        "ix_pipeline_executions_document_id",
        "pipeline_executions",
        ["document_id"],
        unique=False,
        if_not_exists=True,
    )
    op.create_index(
        "ix_pipeline_executions_failure_code",
        "pipeline_executions",
        ["failure_code"],
        unique=False,
        if_not_exists=True,
    )
    op.create_index(
        "idx_pipeline_executions_user_created",
        "pipeline_executions",
        ["user_id", "created_at"],
        unique=False,
        if_not_exists=True,
    )
    op.create_index(
        "idx_pipeline_executions_status_created",
        "pipeline_executions",
        ["status", "created_at"],
        unique=False,
        if_not_exists=True,
    )
    op.create_index(
        "idx_pipeline_executions_type_status",
        "pipeline_executions",
        ["execution_type", "status"],
        unique=False,
        if_not_exists=True,
    )

    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1
                FROM information_schema.table_constraints
                WHERE constraint_name = 'fk_pipeline_executions_document_id_document_versions'
            ) THEN
                ALTER TABLE pipeline_executions
                ADD CONSTRAINT fk_pipeline_executions_document_id_document_versions
                FOREIGN KEY (document_id) REFERENCES document_versions(id)
                ON DELETE SET NULL;
            END IF;
        END $$;
        """
    )


def downgrade() -> None:
    op.drop_index("idx_pipeline_executions_type_status", table_name="pipeline_executions", if_exists=True)
    op.drop_index("idx_pipeline_executions_status_created", table_name="pipeline_executions", if_exists=True)
    op.drop_index("idx_pipeline_executions_user_created", table_name="pipeline_executions", if_exists=True)
    op.drop_index("ix_pipeline_executions_failure_code", table_name="pipeline_executions", if_exists=True)
    op.drop_index("ix_pipeline_executions_document_id", table_name="pipeline_executions", if_exists=True)

    op.execute(
        """
        ALTER TABLE pipeline_executions
        DROP CONSTRAINT IF EXISTS fk_pipeline_executions_document_id_document_versions
        """
    )
    op.execute("ALTER TABLE pipeline_executions DROP COLUMN IF EXISTS metadata_json")
    op.execute("ALTER TABLE pipeline_executions DROP COLUMN IF EXISTS input_params")
    op.execute("ALTER TABLE pipeline_executions DROP COLUMN IF EXISTS output_artifact_ids")
    op.execute("ALTER TABLE pipeline_executions DROP COLUMN IF EXISTS duration_ms")
    op.execute("ALTER TABLE pipeline_executions DROP COLUMN IF EXISTS failure_code")
    op.execute("ALTER TABLE pipeline_executions DROP COLUMN IF EXISTS failure_reason")
    op.execute("ALTER TABLE pipeline_executions DROP COLUMN IF EXISTS trigger_type")
    op.execute("ALTER TABLE pipeline_executions DROP COLUMN IF EXISTS execution_type")
    op.execute("ALTER TABLE pipeline_executions DROP COLUMN IF EXISTS document_id")
