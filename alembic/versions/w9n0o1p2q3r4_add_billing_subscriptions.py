"""add billing subscriptions and events tables

Revision ID: w9n0o1p2q3r4
Revises: v2m3n4o5p6q7
Create Date: 2026-07-21 00:00:00.000000

Этап 4 — Billing (Stripe, ТЗ §3.5). Две новые таблицы:
- ``subscriptions`` — одна запись на пользователя (uq_subscriptions_user_id),
  ``stripe_customer_id`` шифруется (EncryptedText=Text at DDL, ФЗ-152 ст.19);
  ``stripe_subscription_id`` — публичный Stripe id (plain String) для webhook lookup.
- ``billing_events`` — idempotency-лог Stripe webhook-событий
  (``stripe_event_id`` UNIQUE → дедуп ретраев).

Без backfill — новые таблицы. Образец: v2m3n4o5p6q7 / 8b9c0d1e2f3a.
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "w9n0o1p2q3r4"
down_revision = "v2m3n4o5p6q7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "subscriptions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("plan", sa.String(length=50), nullable=False, server_default="free"),
        sa.Column("status", sa.String(length=50), nullable=False, server_default="active"),
        # PII / finance — encrypted at rest (ФЗ-152 ст.19).
        sa.Column("stripe_customer_id", sa.Text(), nullable=True),
        sa.Column("stripe_subscription_id", sa.String(length=255), nullable=True),
        sa.Column("current_period_end", sa.DateTime(timezone=True), nullable=True),
        sa.Column("canceled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", name="uq_subscriptions_user_id"),
    )

    op.create_index("ix_subscriptions_user_id", "subscriptions", ["user_id"])
    op.create_index("ix_subscriptions_plan", "subscriptions", ["plan"])
    op.create_index("ix_subscriptions_status", "subscriptions", ["status"])
    # Без индекса по stripe_customer_id: EncryptedText (Fernet, random IV) —
    # equality-lookup по зашифрованному столбцу невозможен. Webhook-lookup идёт
    # по plain stripe_subscription_id (см. ниже).
    op.create_index("ix_subscriptions_stripe_subscription_id", "subscriptions", ["stripe_subscription_id"])

    op.create_table(
        "billing_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("stripe_event_id", sa.String(length=255), nullable=False),
        sa.Column("event_type", sa.String(length=100), nullable=False),
        sa.Column("subscription_id", sa.Uuid(), nullable=True),
        sa.Column("processed", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("payload_json", sa.JSON(), nullable=False),
        sa.Column("error_text", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.ForeignKeyConstraint(["subscription_id"], ["subscriptions.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("stripe_event_id", name="uq_billing_events_stripe_event_id"),
    )

    op.create_index("ix_billing_events_stripe_event_id", "billing_events", ["stripe_event_id"])
    op.create_index("ix_billing_events_event_type", "billing_events", ["event_type"])
    op.create_index("ix_billing_events_subscription_id", "billing_events", ["subscription_id"])


def downgrade() -> None:
    op.drop_index("ix_billing_events_subscription_id", table_name="billing_events")
    op.drop_index("ix_billing_events_event_type", table_name="billing_events")
    op.drop_index("ix_billing_events_stripe_event_id", table_name="billing_events")
    op.drop_table("billing_events")

    op.drop_index("ix_subscriptions_stripe_subscription_id", table_name="subscriptions")
    op.drop_index("ix_subscriptions_status", table_name="subscriptions")
    op.drop_index("ix_subscriptions_plan", table_name="subscriptions")
    op.drop_index("ix_subscriptions_user_id", table_name="subscriptions")
    op.drop_table("subscriptions")