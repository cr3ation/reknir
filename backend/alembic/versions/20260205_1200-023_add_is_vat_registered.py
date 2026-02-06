"""add is_vat_registered to companies

Revision ID: 023
Revises: 022
Create Date: 2026-02-05 12:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "023"
down_revision: str | None = "022"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Add is_vat_registered column with default True (backwards compatible)
    op.add_column(
        "companies",
        sa.Column("is_vat_registered", sa.Boolean(), nullable=False, server_default=sa.true()),
    )


def downgrade() -> None:
    op.drop_column("companies", "is_vat_registered")
