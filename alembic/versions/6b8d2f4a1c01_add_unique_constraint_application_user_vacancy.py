"""add unique constraint on application_records user_id + vacancy_id

Revision ID: 6b8d2f4a1c01
Revises: c5e1b2062553
Create Date: 2026-04-15 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "6b8d2f4a1c01"
down_revision: Union[str, Sequence[str], None] = "c5e1b2062553"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_unique_constraint(
        "uq_application_records_user_vacancy",
        "application_records",
        ["user_id", "vacancy_id"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_application_records_user_vacancy",
        "application_records",
        type_="unique",
    )
