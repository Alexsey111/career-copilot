"""add_pipeline_execution_lineage_fields

Revision ID: d7e8f9a0b1c2
Revises: c6d7e8f9a0b1
Create Date: 2026-05-19 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "d7e8f9a0b1c2"
down_revision: Union[str, Sequence[str], None] = "c6d7e8f9a0b1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "pipeline_executions",
        sa.Column("parent_execution_id", sa.Uuid(), nullable=True),
    )
    op.add_column(
        "pipeline_executions",
        sa.Column("lineage_kind", sa.String(length=50), nullable=True),
    )
    op.add_column(
        "pipeline_executions",
        sa.Column("lineage_reason", sa.Text(), nullable=True),
    )
    op.add_column(
        "pipeline_executions",
        sa.Column(
            "lineage_metadata_json",
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'{}'::json"),
        ),
    )
    op.create_foreign_key(
        "fk_pipeline_executions_parent_execution_id",
        "pipeline_executions",
        "pipeline_executions",
        ["parent_execution_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        op.f("ix_pipeline_executions_parent_execution_id"),
        "pipeline_executions",
        ["parent_execution_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_pipeline_executions_lineage_kind"),
        "pipeline_executions",
        ["lineage_kind"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_pipeline_executions_lineage_kind"), table_name="pipeline_executions")
    op.drop_index(op.f("ix_pipeline_executions_parent_execution_id"), table_name="pipeline_executions")
    op.drop_constraint(
        "fk_pipeline_executions_parent_execution_id",
        "pipeline_executions",
        type_="foreignkey",
    )
    op.drop_column("pipeline_executions", "lineage_metadata_json")
    op.drop_column("pipeline_executions", "lineage_reason")
    op.drop_column("pipeline_executions", "lineage_kind")
    op.drop_column("pipeline_executions", "parent_execution_id")
