"""add company contact info

Revision ID: 008
Revises: 007
Create Date: 2025-01-11 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '008'
down_revision: Union[str, None] = '007'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add contact information columns to companies table
    op.add_column('companies', sa.Column('address', sa.String(), nullable=True))
    op.add_column('companies', sa.Column('postal_code', sa.String(length=10), nullable=True))
    op.add_column('companies', sa.Column('city', sa.String(), nullable=True))
    op.add_column('companies', sa.Column('phone', sa.String(length=20), nullable=True))
    op.add_column('companies', sa.Column('email', sa.String(), nullable=True))


def downgrade() -> None:
    # Remove contact information columns from companies table
    op.drop_column('companies', 'email')
    op.drop_column('companies', 'phone')
    op.drop_column('companies', 'city')
    op.drop_column('companies', 'postal_code')
    op.drop_column('companies', 'address')
