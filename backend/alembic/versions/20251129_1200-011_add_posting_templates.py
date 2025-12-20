"""add posting templates

Revision ID: 011
Revises: 010
Create Date: 2025-11-29 12:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "011"
down_revision: str | None = "010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Create posting_templates table
    op.create_table(
        "posting_templates",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("company_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("description", sa.String(length=255), nullable=False),
        sa.Column("default_series", sa.String(length=10), nullable=True),
        sa.Column("default_journal_text", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["company_id"],
            ["companies.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_posting_templates_id"), "posting_templates", ["id"], unique=False)
    op.create_index(op.f("ix_posting_templates_name"), "posting_templates", ["name"], unique=False)

    # Create posting_template_lines table
    op.create_table(
        "posting_template_lines",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("template_id", sa.Integer(), nullable=False),
        sa.Column("account_id", sa.Integer(), nullable=False),
        sa.Column("formula", sa.String(length=500), nullable=False),
        sa.Column("description", sa.String(length=255), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.ForeignKeyConstraint(
            ["account_id"],
            ["accounts.id"],
        ),
        sa.ForeignKeyConstraint(
            ["template_id"],
            ["posting_templates.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_posting_template_lines_id"), "posting_template_lines", ["id"], unique=False)

    # Add unique constraint on company_id + name for posting_templates
    op.create_unique_constraint("uq_posting_templates_company_name", "posting_templates", ["company_id", "name"])


def downgrade() -> None:
    # Drop unique constraint
    op.drop_constraint("uq_posting_templates_company_name", "posting_templates", type_="unique")

    # Drop indexes and tables
    op.drop_index(op.f("ix_posting_template_lines_id"), table_name="posting_template_lines")
    op.drop_table("posting_template_lines")

    op.drop_index(op.f("ix_posting_templates_name"), table_name="posting_templates")
    op.drop_index(op.f("ix_posting_templates_id"), table_name="posting_templates")
    op.drop_table("posting_templates")
