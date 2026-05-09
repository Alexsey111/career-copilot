"""add application_events table

Revision ID: g2b3c4d5e6f7
Revises: f1a2b3c4d5e6
Create Date: 2025-05-09 21:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'g2b3c4d5e6f7'
down_revision: Union[str, None] = 'f1a2b3c4d5e6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Обновляем существующую таблицу application_records
    op.add_column("application_records", sa.Column("source", sa.String(length=50), nullable=True))
    op.add_column("application_records", sa.Column("external_link", sa.String(length=1000), nullable=True))
    
    # Удаляем старый канал если есть
    try:
        op.drop_column("application_records", "channel")
    except Exception:
        pass  # Может не существовать

    # Создаем таблицу application_events
    op.create_table(
        "application_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("application_id", sa.Uuid(), nullable=False),
        sa.Column("event_type", sa.String(length=50), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("meta_json", sa.JSON(), nullable=False, default=list),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.ForeignKeyConstraint(["application_id"], ["application_records.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_index("ix_application_events_application_id", "application_events", ["application_id"])
    op.create_index("ix_application_events_event_type", "application_events", ["event_type"])
    op.create_index("ix_application_events_application_type", "application_events", ["application_id", "event_type"])


def downgrade() -> None:
    op.drop_index("ix_application_events_application_type", table_name="application_events")
    op.drop_index("ix_application_events_event_type", table_name="application_events")
    op.drop_index("ix_application_events_application_id", table_name="application_events")
    op.drop_table("application_events")
    
    op.add_column("application_records", sa.Column("channel", sa.String(length=50), nullable=True))
    try:
        op.drop_column("application_records", "source")
    except Exception:
        pass
    try:
        op.drop_column("application_records", "external_link")
    except Exception:
        pass
