"""Extend org_number field length

Revision ID: 003
Revises: 002
Create Date: 2024-11-09 17:30:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '003'
down_revision = '002'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Extend org_number column from varchar(10) to varchar(15)
    op.alter_column('companies', 'org_number',
                    existing_type=sa.VARCHAR(length=10),
                    type_=sa.VARCHAR(length=15),
                    existing_nullable=False)


def downgrade() -> None:
    # Revert org_number column back to varchar(10)
    op.alter_column('companies', 'org_number',
                    existing_type=sa.VARCHAR(length=15),
                    type_=sa.VARCHAR(length=10),
                    existing_nullable=False)
