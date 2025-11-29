"""add_company_logo

Revision ID: 6b60dd14b9bb
Revises: f8d6d475181b
Create Date: 2025-11-29 20:08:14.852191

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '6b60dd14b9bb'
down_revision = 'f8d6d475181b'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add logo_filename column to companies table
    op.add_column('companies', sa.Column('logo_filename', sa.String(), nullable=True))


def downgrade() -> None:
    # Remove logo_filename column from companies table
    op.drop_column('companies', 'logo_filename')
