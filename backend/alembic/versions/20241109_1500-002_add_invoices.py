"""Add invoice management tables

Revision ID: 002
Revises: 001
Create Date: 2024-11-09 15:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '002'
down_revision = '001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create invoice status enum (if it doesn't exist)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE invoicestatus AS ENUM ('draft', 'sent', 'paid', 'partial', 'overdue', 'cancelled');
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
    """)

    # Create customers table
    op.create_table(
        'customers',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('company_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('org_number', sa.String(length=15), nullable=True),
        sa.Column('contact_person', sa.String(), nullable=True),
        sa.Column('email', sa.String(), nullable=True),
        sa.Column('phone', sa.String(), nullable=True),
        sa.Column('address', sa.String(), nullable=True),
        sa.Column('postal_code', sa.String(length=10), nullable=True),
        sa.Column('city', sa.String(), nullable=True),
        sa.Column('country', sa.String(), nullable=False, server_default='Sverige'),
        sa.Column('payment_terms_days', sa.Integer(), nullable=False, server_default='30'),
        sa.Column('active', sa.Boolean(), nullable=False, server_default='true'),
        sa.ForeignKeyConstraint(['company_id'], ['companies.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_customers_id'), 'customers', ['id'], unique=False)

    # Create suppliers table
    op.create_table(
        'suppliers',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('company_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('org_number', sa.String(length=15), nullable=True),
        sa.Column('contact_person', sa.String(), nullable=True),
        sa.Column('email', sa.String(), nullable=True),
        sa.Column('phone', sa.String(), nullable=True),
        sa.Column('address', sa.String(), nullable=True),
        sa.Column('postal_code', sa.String(length=10), nullable=True),
        sa.Column('city', sa.String(), nullable=True),
        sa.Column('country', sa.String(), nullable=False, server_default='Sverige'),
        sa.Column('payment_terms_days', sa.Integer(), nullable=False, server_default='30'),
        sa.Column('bank_account', sa.String(), nullable=True),
        sa.Column('bank_name', sa.String(), nullable=True),
        sa.Column('active', sa.Boolean(), nullable=False, server_default='true'),
        sa.ForeignKeyConstraint(['company_id'], ['companies.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_suppliers_id'), 'suppliers', ['id'], unique=False)

    # Create invoices table
    op.create_table(
        'invoices',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('company_id', sa.Integer(), nullable=False),
        sa.Column('customer_id', sa.Integer(), nullable=False),
        sa.Column('invoice_number', sa.Integer(), nullable=False),
        sa.Column('invoice_series', sa.String(length=10), nullable=False, server_default='F'),
        sa.Column('invoice_date', sa.Date(), nullable=False),
        sa.Column('due_date', sa.Date(), nullable=False),
        sa.Column('paid_date', sa.Date(), nullable=True),
        sa.Column('reference', sa.String(), nullable=True),
        sa.Column('our_reference', sa.String(), nullable=True),
        sa.Column('total_amount', sa.Numeric(precision=15, scale=2), nullable=False),
        sa.Column('vat_amount', sa.Numeric(precision=15, scale=2), nullable=False),
        sa.Column('net_amount', sa.Numeric(precision=15, scale=2), nullable=False),
        sa.Column('status', sa.Enum('draft', 'sent', 'paid', 'partial', 'overdue', 'cancelled', name='invoicestatus'), nullable=False, server_default='draft'),
        sa.Column('paid_amount', sa.Numeric(precision=15, scale=2), nullable=False, server_default='0'),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('message', sa.Text(), nullable=True),
        sa.Column('invoice_verification_id', sa.Integer(), nullable=True),
        sa.Column('payment_verification_id', sa.Integer(), nullable=True),
        sa.Column('pdf_path', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('sent_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['company_id'], ['companies.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['customer_id'], ['customers.id'], ),
        sa.ForeignKeyConstraint(['invoice_verification_id'], ['verifications.id'], ),
        sa.ForeignKeyConstraint(['payment_verification_id'], ['verifications.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_invoices_id'), 'invoices', ['id'], unique=False)
    op.create_index(op.f('ix_invoices_invoice_number'), 'invoices', ['invoice_number'], unique=False)
    op.create_index(op.f('ix_invoices_invoice_date'), 'invoices', ['invoice_date'], unique=False)
    op.create_index(op.f('ix_invoices_status'), 'invoices', ['status'], unique=False)

    # Create invoice_lines table
    op.create_table(
        'invoice_lines',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('invoice_id', sa.Integer(), nullable=False),
        sa.Column('description', sa.String(), nullable=False),
        sa.Column('quantity', sa.Numeric(precision=10, scale=2), nullable=False, server_default='1'),
        sa.Column('unit', sa.String(length=20), nullable=False, server_default='st'),
        sa.Column('unit_price', sa.Numeric(precision=15, scale=2), nullable=False),
        sa.Column('vat_rate', sa.Numeric(precision=5, scale=2), nullable=False),
        sa.Column('account_id', sa.Integer(), nullable=True),
        sa.Column('net_amount', sa.Numeric(precision=15, scale=2), nullable=False),
        sa.Column('vat_amount', sa.Numeric(precision=15, scale=2), nullable=False),
        sa.Column('total_amount', sa.Numeric(precision=15, scale=2), nullable=False),
        sa.ForeignKeyConstraint(['account_id'], ['accounts.id'], ),
        sa.ForeignKeyConstraint(['invoice_id'], ['invoices.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_invoice_lines_id'), 'invoice_lines', ['id'], unique=False)

    # Create supplier_invoices table
    op.create_table(
        'supplier_invoices',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('company_id', sa.Integer(), nullable=False),
        sa.Column('supplier_id', sa.Integer(), nullable=False),
        sa.Column('supplier_invoice_number', sa.String(), nullable=False),
        sa.Column('our_invoice_number', sa.Integer(), nullable=True),
        sa.Column('invoice_date', sa.Date(), nullable=False),
        sa.Column('due_date', sa.Date(), nullable=False),
        sa.Column('paid_date', sa.Date(), nullable=True),
        sa.Column('total_amount', sa.Numeric(precision=15, scale=2), nullable=False),
        sa.Column('vat_amount', sa.Numeric(precision=15, scale=2), nullable=False),
        sa.Column('net_amount', sa.Numeric(precision=15, scale=2), nullable=False),
        sa.Column('status', sa.Enum('draft', 'sent', 'paid', 'partial', 'overdue', 'cancelled', name='invoicestatus'), nullable=False, server_default='draft'),
        sa.Column('paid_amount', sa.Numeric(precision=15, scale=2), nullable=False, server_default='0'),
        sa.Column('ocr_number', sa.String(), nullable=True),
        sa.Column('reference', sa.String(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('invoice_verification_id', sa.Integer(), nullable=True),
        sa.Column('payment_verification_id', sa.Integer(), nullable=True),
        sa.Column('attachment_path', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['company_id'], ['companies.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['supplier_id'], ['suppliers.id'], ),
        sa.ForeignKeyConstraint(['invoice_verification_id'], ['verifications.id'], ),
        sa.ForeignKeyConstraint(['payment_verification_id'], ['verifications.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_supplier_invoices_id'), 'supplier_invoices', ['id'], unique=False)
    op.create_index(op.f('ix_supplier_invoices_our_invoice_number'), 'supplier_invoices', ['our_invoice_number'], unique=False)
    op.create_index(op.f('ix_supplier_invoices_invoice_date'), 'supplier_invoices', ['invoice_date'], unique=False)
    op.create_index(op.f('ix_supplier_invoices_status'), 'supplier_invoices', ['status'], unique=False)

    # Create supplier_invoice_lines table
    op.create_table(
        'supplier_invoice_lines',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('supplier_invoice_id', sa.Integer(), nullable=False),
        sa.Column('description', sa.String(), nullable=False),
        sa.Column('quantity', sa.Numeric(precision=10, scale=2), nullable=False, server_default='1'),
        sa.Column('unit_price', sa.Numeric(precision=15, scale=2), nullable=False),
        sa.Column('vat_rate', sa.Numeric(precision=5, scale=2), nullable=False),
        sa.Column('account_id', sa.Integer(), nullable=True),
        sa.Column('net_amount', sa.Numeric(precision=15, scale=2), nullable=False),
        sa.Column('vat_amount', sa.Numeric(precision=15, scale=2), nullable=False),
        sa.Column('total_amount', sa.Numeric(precision=15, scale=2), nullable=False),
        sa.ForeignKeyConstraint(['account_id'], ['accounts.id'], ),
        sa.ForeignKeyConstraint(['supplier_invoice_id'], ['supplier_invoices.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_supplier_invoice_lines_id'), 'supplier_invoice_lines', ['id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_supplier_invoice_lines_id'), table_name='supplier_invoice_lines')
    op.drop_table('supplier_invoice_lines')
    op.drop_index(op.f('ix_supplier_invoices_status'), table_name='supplier_invoices')
    op.drop_index(op.f('ix_supplier_invoices_invoice_date'), table_name='supplier_invoices')
    op.drop_index(op.f('ix_supplier_invoices_our_invoice_number'), table_name='supplier_invoices')
    op.drop_index(op.f('ix_supplier_invoices_id'), table_name='supplier_invoices')
    op.drop_table('supplier_invoices')
    op.drop_index(op.f('ix_invoice_lines_id'), table_name='invoice_lines')
    op.drop_table('invoice_lines')
    op.drop_index(op.f('ix_invoices_status'), table_name='invoices')
    op.drop_index(op.f('ix_invoices_invoice_date'), table_name='invoices')
    op.drop_index(op.f('ix_invoices_invoice_number'), table_name='invoices')
    op.drop_index(op.f('ix_invoices_id'), table_name='invoices')
    op.drop_table('invoices')
    op.drop_index(op.f('ix_suppliers_id'), table_name='suppliers')
    op.drop_table('suppliers')
    op.drop_index(op.f('ix_customers_id'), table_name='customers')
    op.drop_table('customers')
    op.execute('DROP TYPE invoicestatus')
