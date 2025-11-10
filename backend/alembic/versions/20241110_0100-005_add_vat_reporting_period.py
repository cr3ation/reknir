"""add vat reporting period

Revision ID: 005
Revises: 004
Create Date: 2024-11-10 01:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '005'
down_revision: Union[str, None] = '004'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add vat_reporting_period column with default 'quarterly'
    op.add_column(
        'companies',
        sa.Column(
            'vat_reporting_period',
            sa.Enum('monthly', 'quarterly', 'yearly', name='vatreportingperiod'),
            nullable=False,
            server_default='quarterly'
        )
    )


def downgrade() -> None:
    op.drop_column('companies', 'vat_reporting_period')
    # Drop the enum type
    op.execute("DROP TYPE vatreportingperiod")
