"""add pipeline execution events

Revision ID: e7f8a9b0c1d2
Revises: d1e2f3a4b5c6
Create Date: 2026-05-14 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "e7f8a9b0c1d2"
down_revision: Union[str, Sequence[str], None] = "d1e2f3a4b5c6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "pipeline_execution_events",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "execution_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("pipeline_executions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("event_type", sa.String(length=100), nullable=False),
        sa.Column("payload_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index(
        "idx_pipeline_execution_events_execution_created",
        "pipeline_execution_events",
        ["execution_id", "created_at"],
        unique=False,
    )
    op.create_index(
        "idx_pipeline_execution_events_event_type",
        "pipeline_execution_events",
        ["event_type"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("idx_pipeline_execution_events_event_type", table_name="pipeline_execution_events")
    op.drop_index("idx_pipeline_execution_events_execution_created", table_name="pipeline_execution_events")
    op.drop_table("pipeline_execution_events")
