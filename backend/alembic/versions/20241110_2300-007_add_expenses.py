"""add expenses

Revision ID: 007
Revises: 006
Create Date: 2024-11-10 23:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '007'
down_revision = '006'
branch_labels = None
depends_on = None


def upgrade():
    # Create expenses table
    op.create_table(
        'expenses',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('company_id', sa.Integer(), nullable=False),
        sa.Column('employee_name', sa.String(length=200), nullable=False),
        sa.Column('expense_date', sa.Date(), nullable=False),
        sa.Column('description', sa.String(length=500), nullable=False),
        sa.Column('amount', sa.Numeric(precision=15, scale=2), nullable=False, server_default='0'),
        sa.Column('vat_amount', sa.Numeric(precision=15, scale=2), nullable=False, server_default='0'),
        sa.Column('expense_account_id', sa.Integer(), nullable=True),
        sa.Column('vat_account_id', sa.Integer(), nullable=True),
        sa.Column('receipt_filename', sa.String(length=500), nullable=True),
        sa.Column('status', sa.Enum('draft', 'submitted', 'approved', 'paid', 'rejected', name='expensestatus'), nullable=False, server_default='draft'),
        sa.Column('approved_date', sa.DateTime(), nullable=True),
        sa.Column('paid_date', sa.DateTime(), nullable=True),
        sa.Column('verification_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['company_id'], ['companies.id'], ),
        sa.ForeignKeyConstraint(['expense_account_id'], ['accounts.id'], ),
        sa.ForeignKeyConstraint(['vat_account_id'], ['accounts.id'], ),
        sa.ForeignKeyConstraint(['verification_id'], ['verifications.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_expenses_id'), 'expenses', ['id'], unique=False)


def downgrade():
    op.drop_index(op.f('ix_expenses_id'), table_name='expenses')
    op.drop_table('expenses')
    op.execute('DROP TYPE expensestatus')
