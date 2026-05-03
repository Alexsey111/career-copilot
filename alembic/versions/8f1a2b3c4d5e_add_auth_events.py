"""add auth events

Revision ID: 8f1a2b3c4d5e
Revises: 3c7e9f2a8b4d
Create Date: 2026-05-03 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "8f1a2b3c4d5e"
down_revision: Union[str, Sequence[str], None] = "3c7e9f2a8b4d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "auth_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=True),
        sa.Column("event_type", sa.String(length=50), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=True),
        sa.Column("ip_address", sa.String(length=45), nullable=True),
        sa.Column("user_agent", sa.String(length=512), nullable=True),
        sa.Column("meta_json", sa.JSON(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_auth_events_user_id"), "auth_events", ["user_id"])
    op.create_index(op.f("ix_auth_events_event_type"), "auth_events", ["event_type"])
    op.create_index(op.f("ix_auth_events_email"), "auth_events", ["email"])


def downgrade() -> None:
    op.drop_index(op.f("ix_auth_events_email"), table_name="auth_events")
    op.drop_index(op.f("ix_auth_events_event_type"), table_name="auth_events")
    op.drop_index(op.f("ix_auth_events_user_id"), table_name="auth_events")
    op.drop_table("auth_events")
