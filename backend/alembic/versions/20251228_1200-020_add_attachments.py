"""Add unified attachments system

Revision ID: 020
Revises: 019
Create Date: 2025-12-28 12:00:00.000000

This migration creates a unified attachment system:
- attachments: Standalone file resources with metadata
- attachment_links: Links attachments to entities (supplier_invoice, invoice, expense, verification)

Also removes old attachment columns:
- supplier_invoices.attachment_path
- expenses.receipt_filename
"""

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "020"
down_revision = "019"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create attachments table
    op.create_table(
        "attachments",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("company_id", sa.Integer(), nullable=False),
        sa.Column("original_filename", sa.String(length=500), nullable=False),
        sa.Column("storage_filename", sa.String(length=500), nullable=False),
        sa.Column("mime_type", sa.String(length=100), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("checksum_sha256", sa.String(length=64), nullable=True),
        sa.Column(
            "status",
            sa.Enum("CREATED", "UPLOADED", "PROCESSING", "READY", "REJECTED", name="attachmentstatus"),
            nullable=False,
            server_default="UPLOADED",
        ),
        sa.Column("rejection_reason", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_by", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"]),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_attachments_id"), "attachments", ["id"], unique=False)
    op.create_index(op.f("ix_attachments_company_id"), "attachments", ["company_id"], unique=False)
    op.create_index(op.f("ix_attachments_storage_filename"), "attachments", ["storage_filename"], unique=True)

    # Create attachment_links table
    op.create_table(
        "attachment_links",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("attachment_id", sa.Integer(), nullable=False),
        sa.Column(
            "entity_type",
            sa.Enum("SUPPLIER_INVOICE", "INVOICE", "EXPENSE", "VERIFICATION", name="entitytype"),
            nullable=False,
        ),
        sa.Column("entity_id", sa.Integer(), nullable=False),
        sa.Column(
            "role",
            sa.Enum("ORIGINAL", "RECEIPT", "SUPPORTING", "CONTRACT", name="attachmentrole"),
            nullable=False,
            server_default="ORIGINAL",
        ),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["attachment_id"], ["attachments.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("attachment_id", "entity_type", "entity_id", name="uq_attachment_entity"),
    )
    op.create_index(op.f("ix_attachment_links_id"), "attachment_links", ["id"], unique=False)
    op.create_index("ix_attachment_links_entity", "attachment_links", ["entity_type", "entity_id"], unique=False)

    # Drop old attachment columns
    op.drop_column("supplier_invoices", "attachment_path")
    op.drop_column("expenses", "receipt_filename")


def downgrade() -> None:
    # Restore old attachment columns
    op.add_column("expenses", sa.Column("receipt_filename", sa.String(length=500), nullable=True))
    op.add_column("supplier_invoices", sa.Column("attachment_path", sa.String(), nullable=True))

    # Drop attachment_links table
    op.drop_index("ix_attachment_links_entity", table_name="attachment_links")
    op.drop_index(op.f("ix_attachment_links_id"), table_name="attachment_links")
    op.drop_table("attachment_links")

    # Drop attachments table
    op.drop_index(op.f("ix_attachments_storage_filename"), table_name="attachments")
    op.drop_index(op.f("ix_attachments_company_id"), table_name="attachments")
    op.drop_index(op.f("ix_attachments_id"), table_name="attachments")
    op.drop_table("attachments")

    # Drop enum types
    op.execute("DROP TYPE IF EXISTS attachmentrole")
    op.execute("DROP TYPE IF EXISTS entitytype")
    op.execute("DROP TYPE IF EXISTS attachmentstatus")
