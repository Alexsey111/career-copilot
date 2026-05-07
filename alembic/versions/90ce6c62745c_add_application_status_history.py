# backend\alembic\script.py.mako

"""add application status history

Revision ID: 90ce6c62745c
Revises: 5505206e59d7
Create Date: 2026-05-07 15:25:32.829543

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa



# revision identifiers, used by Alembic.
revision: str = '90ce6c62745c'
down_revision: Union[str, Sequence[str], None] = '5505206e59d7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "application_status_history",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column(
            "application_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("application_records.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "previous_status",
            sa.String(length=50),
            nullable=True,
        ),
        sa.Column(
            "new_status",
            sa.String(length=50),
            nullable=False,
        ),
        sa.Column(
            "notes",
            sa.Text(),
            nullable=True,
        ),
        sa.Column(
            "changed_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    op.create_index(
        "ix_application_status_history_application_id",
        "application_status_history",
        ["application_id"],
    )

    op.create_index(
        "ix_application_status_history_changed_at",
        "application_status_history",
        ["changed_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_application_status_history_changed_at",
        table_name="application_status_history",
    )

    op.drop_index(
        "ix_application_status_history_application_id",
        table_name="application_status_history",
    )

    op.drop_table("application_status_history")
