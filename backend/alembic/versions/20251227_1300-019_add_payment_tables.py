"""Add payment tables for invoice payment history

Revision ID: 019
Revises: 018
Create Date: 2025-12-27 13:00:00.000000

This migration adds separate payment tables to track individual payments
for both customer invoices and supplier invoices.

Tables created:
- invoice_payments: Payment history for outgoing invoices
- supplier_invoice_payments: Payment history for supplier invoices

Existing data migration:
- Creates payment records from existing paid_amount/paid_date on invoices
"""

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "019"
down_revision = "018"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create invoice_payments table
    op.create_table(
        "invoice_payments",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("invoice_id", sa.Integer(), nullable=False),
        sa.Column("payment_date", sa.Date(), nullable=False),
        sa.Column("amount", sa.Numeric(precision=15, scale=2), nullable=False),
        sa.Column("verification_id", sa.Integer(), nullable=True),
        sa.Column("bank_account_id", sa.Integer(), nullable=True),
        sa.Column("reference", sa.String(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["invoice_id"], ["invoices.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["verification_id"], ["verifications.id"]),
        sa.ForeignKeyConstraint(["bank_account_id"], ["accounts.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_invoice_payments_id"), "invoice_payments", ["id"], unique=False)
    op.create_index(op.f("ix_invoice_payments_invoice_id"), "invoice_payments", ["invoice_id"], unique=False)

    # Create supplier_invoice_payments table
    op.create_table(
        "supplier_invoice_payments",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("supplier_invoice_id", sa.Integer(), nullable=False),
        sa.Column("payment_date", sa.Date(), nullable=False),
        sa.Column("amount", sa.Numeric(precision=15, scale=2), nullable=False),
        sa.Column("verification_id", sa.Integer(), nullable=True),
        sa.Column("bank_account_id", sa.Integer(), nullable=True),
        sa.Column("reference", sa.String(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["supplier_invoice_id"], ["supplier_invoices.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["verification_id"], ["verifications.id"]),
        sa.ForeignKeyConstraint(["bank_account_id"], ["accounts.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_supplier_invoice_payments_id"), "supplier_invoice_payments", ["id"], unique=False
    )
    op.create_index(
        op.f("ix_supplier_invoice_payments_supplier_invoice_id"),
        "supplier_invoice_payments",
        ["supplier_invoice_id"],
        unique=False,
    )

    # Migrate existing data: create payment records from invoices with paid_amount > 0
    op.execute(
        """
        INSERT INTO invoice_payments (invoice_id, payment_date, amount, verification_id, created_at)
        SELECT id, paid_date, paid_amount, payment_verification_id, COALESCE(paid_date, created_at)
        FROM invoices
        WHERE paid_amount > 0 AND paid_date IS NOT NULL
    """
    )

    # Migrate existing data: create payment records from supplier_invoices with paid_amount > 0
    op.execute(
        """
        INSERT INTO supplier_invoice_payments (supplier_invoice_id, payment_date, amount, verification_id, created_at)
        SELECT id, paid_date, paid_amount, payment_verification_id, COALESCE(paid_date, created_at)
        FROM supplier_invoices
        WHERE paid_amount > 0 AND paid_date IS NOT NULL
    """
    )


def downgrade() -> None:
    # Drop supplier_invoice_payments table
    op.drop_index(
        op.f("ix_supplier_invoice_payments_supplier_invoice_id"), table_name="supplier_invoice_payments"
    )
    op.drop_index(op.f("ix_supplier_invoice_payments_id"), table_name="supplier_invoice_payments")
    op.drop_table("supplier_invoice_payments")

    # Drop invoice_payments table
    op.drop_index(op.f("ix_invoice_payments_invoice_id"), table_name="invoice_payments")
    op.drop_index(op.f("ix_invoice_payments_id"), table_name="invoice_payments")
    op.drop_table("invoice_payments")
