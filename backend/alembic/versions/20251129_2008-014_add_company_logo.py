"""add_company_logo

Revision ID: 014
Revises: 013
Create Date: 2025-11-29 20:08:14.852191

"""

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "014"
down_revision = "013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add logo_filename column to companies table
    op.add_column("companies", sa.Column("logo_filename", sa.String(), nullable=True))


def downgrade() -> None:
    # Remove logo_filename column from companies table
    op.drop_column("companies", "logo_filename")
