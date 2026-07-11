"""data_transfer_events audit table (ФЗ-152 transfer of PII)

Revision ID: s9j0k1l2m3n4
Revises: r8i9j0k1l2m3
Create Date: 2026-07-11 00:00:09.000000

Adds the ``data_transfer_events`` table used to audit every transfer of
personal data to an external processor (AI providers). Required by ФЗ-152
(ст.18/19): фиксация факта передачи ПДн, получателя, категории данных,
основания (согласие) и цели.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "s9j0k1l2m3n4"
down_revision = "r8i9j0k1l2m3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "data_transfer_events",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("recipient", sa.String(100), nullable=False),
        sa.Column("purpose", sa.String(100), nullable=False),
        sa.Column("data_categories", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("legal_basis", sa.String(50), nullable=False, server_default="consent"),
        sa.Column("consent_type", sa.String(50), nullable=True),
        sa.Column("model_name", sa.String(100), nullable=True),
        sa.Column("ip_address", sa.String(45), nullable=True),
        sa.Column("user_agent", sa.String(512), nullable=True),
        sa.Column("meta_json", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("ix_data_transfer_events_user_id", "data_transfer_events", ["user_id"])
    op.create_index("ix_data_transfer_events_recipient", "data_transfer_events", ["recipient"])
    op.create_index("ix_data_transfer_events_created_at", "data_transfer_events", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_data_transfer_events_created_at", table_name="data_transfer_events")
    op.drop_index("ix_data_transfer_events_recipient", table_name="data_transfer_events")
    op.drop_index("ix_data_transfer_events_user_id", table_name="data_transfer_events")
    op.drop_table("data_transfer_events")