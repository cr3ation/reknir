"""add sru_code to accounts

Revision ID: 031
Revises: 030
Create Date: 2026-09-30 12:00:00.000000

SRU codes (Skatteverket's field codes) come with the BAS chart and with SIE
files from other programs. They are needed for INK2/NE tax return exports.
"""

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "031"
down_revision = "030"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("accounts", sa.Column("sru_code", sa.String(10), nullable=True))


def downgrade() -> None:
    op.drop_column("accounts", "sru_code")
