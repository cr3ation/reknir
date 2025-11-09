"""Add default_accounts table

Revision ID: 004
Revises: 003
Create Date: 2024-11-09 23:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '004'
down_revision = '003'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create default_accounts table
    op.create_table(
        'default_accounts',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('company_id', sa.Integer(), nullable=False),
        sa.Column('account_type', sa.String(), nullable=False),
        sa.Column('account_id', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['account_id'], ['accounts.id'], ),
        sa.ForeignKeyConstraint(['company_id'], ['companies.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('company_id', 'account_type', name='unique_company_account_type')
    )
    op.create_index(op.f('ix_default_accounts_id'), 'default_accounts', ['id'], unique=False)


def downgrade() -> None:
    # Drop default_accounts table
    op.drop_index(op.f('ix_default_accounts_id'), table_name='default_accounts')
    op.drop_table('default_accounts')
