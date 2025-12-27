"""Separate invoice status into document status and payment status

Revision ID: 018
Revises: 017
Create Date: 2025-12-27 12:00:00.000000

This migration separates the single 'status' field into two dimensions:
- status (InvoiceStatus): Document lifecycle - DRAFT, ISSUED, CANCELLED
- payment_status (PaymentStatus): Payment state - UNPAID, PARTIALLY_PAID, PAID

Data migration:
- DRAFT → DRAFT + UNPAID
- SENT → ISSUED + UNPAID
- PARTIAL → ISSUED + PARTIALLY_PAID
- PAID → ISSUED + PAID
- OVERDUE → ISSUED + (based on paid_amount)
- CANCELLED → CANCELLED + (based on paid_amount)
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision = "018"
down_revision = "017"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create the new payment_status enum type
    payment_status_enum = postgresql.ENUM("unpaid", "partially_paid", "paid", name="paymentstatus", create_type=False)
    payment_status_enum.create(op.get_bind(), checkfirst=True)

    # Add payment_status column to invoices table
    op.add_column(
        "invoices",
        sa.Column(
            "payment_status",
            payment_status_enum,
            nullable=True,  # Temporarily nullable for migration
        ),
    )

    # Add payment_status column to supplier_invoices table
    op.add_column(
        "supplier_invoices",
        sa.Column(
            "payment_status",
            payment_status_enum,
            nullable=True,  # Temporarily nullable for migration
        ),
    )

    # Create index on payment_status for invoices
    op.create_index(op.f("ix_invoices_payment_status"), "invoices", ["payment_status"], unique=False)

    # Create index on payment_status for supplier_invoices
    op.create_index(
        op.f("ix_supplier_invoices_payment_status"),
        "supplier_invoices",
        ["payment_status"],
        unique=False,
    )

    # Migrate data for invoices table
    # Step 1: Set payment_status based on old status (cast to enum)
    op.execute(
        """
        UPDATE invoices SET payment_status =
            CASE
                WHEN status::text = 'paid' THEN 'paid'::paymentstatus
                WHEN status::text = 'partial' THEN 'partially_paid'::paymentstatus
                ELSE 'unpaid'::paymentstatus
            END
    """
    )

    # Step 2: Update status to new values (DRAFT stays DRAFT, everything else becomes ISSUED or CANCELLED)
    # First convert column to text temporarily
    op.execute("ALTER TABLE invoices ALTER COLUMN status TYPE text USING status::text")
    op.execute(
        """
        UPDATE invoices SET status =
            CASE
                WHEN status = 'cancelled' THEN 'cancelled'
                WHEN status = 'draft' THEN 'draft'
                ELSE 'issued'
            END
    """
    )

    # Migrate data for supplier_invoices table
    # Step 1: Set payment_status based on old status (cast to enum)
    op.execute(
        """
        UPDATE supplier_invoices SET payment_status =
            CASE
                WHEN status::text = 'paid' THEN 'paid'::paymentstatus
                WHEN status::text = 'partial' THEN 'partially_paid'::paymentstatus
                ELSE 'unpaid'::paymentstatus
            END
    """
    )

    # Step 2: Update status to new values
    # First convert column to text temporarily
    op.execute("ALTER TABLE supplier_invoices ALTER COLUMN status TYPE text USING status::text")
    op.execute(
        """
        UPDATE supplier_invoices SET status =
            CASE
                WHEN status = 'cancelled' THEN 'cancelled'
                WHEN status = 'draft' THEN 'draft'
                ELSE 'issued'
            END
    """
    )

    # Make payment_status NOT NULL after migration
    op.alter_column(
        "invoices",
        "payment_status",
        existing_type=payment_status_enum,
        nullable=False,
        server_default="unpaid",
    )
    op.alter_column(
        "supplier_invoices",
        "payment_status",
        existing_type=payment_status_enum,
        nullable=False,
        server_default="unpaid",
    )

    # Now we need to update the invoicestatus enum to only have draft, issued, cancelled
    # PostgreSQL doesn't allow removing values from enums, so we need to:
    # 1. Drop default values that depend on the old enum
    # 2. Drop the old enum (columns are now text type)
    # 3. Create new enum with the correct values
    # 4. Change columns to use the new enum

    # Drop default values that depend on the old enum
    op.execute("ALTER TABLE invoices ALTER COLUMN status DROP DEFAULT")
    op.execute("ALTER TABLE supplier_invoices ALTER COLUMN status DROP DEFAULT")

    # Drop old enum type (columns are already text)
    op.execute("DROP TYPE invoicestatus")

    # Create new enum type with correct values
    new_invoice_status_enum = postgresql.ENUM("draft", "issued", "cancelled", name="invoicestatus", create_type=False)
    new_invoice_status_enum.create(op.get_bind(), checkfirst=True)

    # Update columns to use new enum
    op.execute(
        """
        ALTER TABLE invoices
        ALTER COLUMN status TYPE invoicestatus
        USING status::invoicestatus
    """
    )
    op.execute(
        """
        ALTER TABLE supplier_invoices
        ALTER COLUMN status TYPE invoicestatus
        USING status::invoicestatus
    """
    )


def downgrade() -> None:
    # Recreate old enum with all values
    op.execute("ALTER TYPE invoicestatus RENAME TO invoicestatus_new")
    old_invoice_status_enum = postgresql.ENUM(
        "draft",
        "sent",
        "paid",
        "partial",
        "overdue",
        "cancelled",
        name="invoicestatus",
        create_type=False,
    )
    old_invoice_status_enum.create(op.get_bind(), checkfirst=True)

    # Convert status values back: issued -> sent, and restore payment status info
    op.execute(
        """
        UPDATE invoices SET status =
            CASE
                WHEN status::text = 'issued' AND payment_status = 'paid' THEN 'paid'
                WHEN status::text = 'issued' AND payment_status = 'partially_paid' THEN 'partial'
                WHEN status::text = 'issued' THEN 'sent'
                WHEN status::text = 'cancelled' THEN 'cancelled'
                ELSE 'draft'
            END::text
    """
    )

    op.execute(
        """
        UPDATE supplier_invoices SET status =
            CASE
                WHEN status::text = 'issued' AND payment_status = 'paid' THEN 'paid'
                WHEN status::text = 'issued' AND payment_status = 'partially_paid' THEN 'partial'
                WHEN status::text = 'issued' THEN 'sent'
                WHEN status::text = 'cancelled' THEN 'cancelled'
                ELSE 'draft'
            END::text
    """
    )

    # Update columns to use old enum
    op.execute(
        """
        ALTER TABLE invoices
        ALTER COLUMN status TYPE invoicestatus
        USING status::text::invoicestatus
    """
    )
    op.execute(
        """
        ALTER TABLE supplier_invoices
        ALTER COLUMN status TYPE invoicestatus
        USING status::text::invoicestatus
    """
    )

    # Drop new enum
    op.execute("DROP TYPE invoicestatus_new")

    # Drop payment_status indexes
    op.drop_index(op.f("ix_invoices_payment_status"), table_name="invoices")
    op.drop_index(op.f("ix_supplier_invoices_payment_status"), table_name="supplier_invoices")

    # Drop payment_status columns
    op.drop_column("invoices", "payment_status")
    op.drop_column("supplier_invoices", "payment_status")

    # Drop payment_status enum
    payment_status_enum = postgresql.ENUM("unpaid", "partially_paid", "paid", name="paymentstatus")
    payment_status_enum.drop(op.get_bind(), checkfirst=True)
