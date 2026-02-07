"""add payment info

Revision ID: 025
Revises: 024
Create Date: 2026-02-07 15:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '025'
down_revision = '024'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create the paymenttype enum type
    paymenttype_enum = sa.Enum('bankgiro', 'plusgiro', 'bank_account', name='paymenttype')
    paymenttype_enum.create(op.get_bind(), checkfirst=True)

    # Companies: add all payment fields (optional)
    op.add_column('companies', sa.Column('payment_type',
        sa.Enum('bankgiro', 'plusgiro', 'bank_account', name='paymenttype'), nullable=True))
    op.add_column('companies', sa.Column('bankgiro_number', sa.String(20), nullable=True))
    op.add_column('companies', sa.Column('plusgiro_number', sa.String(20), nullable=True))
    op.add_column('companies', sa.Column('clearing_number', sa.String(10), nullable=True))
    op.add_column('companies', sa.Column('account_number', sa.String(20), nullable=True))
    op.add_column('companies', sa.Column('iban', sa.String(34), nullable=True))
    op.add_column('companies', sa.Column('bic', sa.String(11), nullable=True))

    # Invoices: add all payment fields (snapshot from company, nullable for backwards compatibility)
    op.add_column('invoices', sa.Column('payment_type',
        sa.Enum('bankgiro', 'plusgiro', 'bank_account', name='paymenttype'), nullable=True))
    op.add_column('invoices', sa.Column('bankgiro_number', sa.String(20), nullable=True))
    op.add_column('invoices', sa.Column('plusgiro_number', sa.String(20), nullable=True))
    op.add_column('invoices', sa.Column('clearing_number', sa.String(10), nullable=True))
    op.add_column('invoices', sa.Column('account_number', sa.String(20), nullable=True))
    op.add_column('invoices', sa.Column('iban', sa.String(34), nullable=True))
    op.add_column('invoices', sa.Column('bic', sa.String(11), nullable=True))


def downgrade() -> None:
    # Remove payment fields from invoices
    op.drop_column('invoices', 'bic')
    op.drop_column('invoices', 'iban')
    op.drop_column('invoices', 'account_number')
    op.drop_column('invoices', 'clearing_number')
    op.drop_column('invoices', 'plusgiro_number')
    op.drop_column('invoices', 'bankgiro_number')
    op.drop_column('invoices', 'payment_type')

    # Remove payment fields from companies
    op.drop_column('companies', 'bic')
    op.drop_column('companies', 'iban')
    op.drop_column('companies', 'account_number')
    op.drop_column('companies', 'clearing_number')
    op.drop_column('companies', 'plusgiro_number')
    op.drop_column('companies', 'bankgiro_number')
    op.drop_column('companies', 'payment_type')

    # Drop the enum type
    op.execute('DROP TYPE IF EXISTS paymenttype')
