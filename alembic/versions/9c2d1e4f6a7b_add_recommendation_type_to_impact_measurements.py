"""add recommendation_type to impact_measurements

Revision ID: 9c2d1e4f6a7b
Revises: 4f9a1b2c3d4e
Create Date: 2026-05-13 16:10:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "9c2d1e4f6a7b"
down_revision: Union[str, Sequence[str], None] = "4f9a1b2c3d4e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


recommendation_type_enum = sa.Enum(
    "add_metric",
    "add_evidence",
    "improve_description",
    "add_quantifiable_result",
    "add_timeframe",
    "add_context",
    "split_achievement",
    "merge_achievements",
    "add_skill_keyword",
    "remove_redundant",
    "improve_coverage",
    "unknown",
    name="impact_recommendation_type",
)


def upgrade() -> None:
    bind = op.get_bind()
    recommendation_type_enum.create(bind, checkfirst=True)

    op.add_column(
        "impact_measurements",
        sa.Column(
            "recommendation_type",
            recommendation_type_enum,
            nullable=True,
            server_default="unknown",
        ),
    )

    op.execute(
        """
        UPDATE impact_measurements
        SET recommendation_type = CASE split_part(recommendation_id, '_', 1)
            WHEN 'add' THEN CASE
                WHEN split_part(recommendation_id, '_', 2) = 'metric' THEN 'add_metric'
                WHEN split_part(recommendation_id, '_', 2) = 'evidence' THEN 'add_evidence'
                WHEN split_part(recommendation_id, '_', 2) = 'timeframe' THEN 'add_timeframe'
                WHEN split_part(recommendation_id, '_', 2) = 'context' THEN 'add_context'
                WHEN split_part(recommendation_id, '_', 2) = 'skill' THEN 'add_skill_keyword'
                ELSE 'unknown'
            END
            WHEN 'improve' THEN CASE
                WHEN split_part(recommendation_id, '_', 2) = 'description' THEN 'improve_description'
                WHEN split_part(recommendation_id, '_', 2) = 'coverage' THEN 'improve_coverage'
                ELSE 'unknown'
            END
            WHEN 'remove' THEN 'remove_redundant'
            WHEN 'split' THEN 'split_achievement'
            WHEN 'merge' THEN 'merge_achievements'
            ELSE 'unknown'
        END::impact_recommendation_type
        """
    )

    op.alter_column("impact_measurements", "recommendation_type", nullable=False, server_default=None)
    op.create_index(
        op.f("ix_impact_measurements_recommendation_type"),
        "impact_measurements",
        ["recommendation_type"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_impact_measurements_recommendation_type"), table_name="impact_measurements")
    op.drop_column("impact_measurements", "recommendation_type")
    bind = op.get_bind()
    recommendation_type_enum.drop(bind, checkfirst=True)
