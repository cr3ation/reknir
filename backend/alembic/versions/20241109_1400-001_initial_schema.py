"""Initial schema for Swedish bookkeeping

Revision ID: 001
Revises:
Create Date: 2024-11-09 14:00:00.000000

"""

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create companies table
    op.create_table(
        "companies",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("org_number", sa.String(length=10), nullable=False),
        sa.Column("fiscal_year_start", sa.Date(), nullable=False),
        sa.Column("fiscal_year_end", sa.Date(), nullable=False),
        sa.Column("accounting_basis", sa.Enum("accrual", "cash", name="accountingbasis"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_companies_id"), "companies", ["id"], unique=False)
    op.create_index(op.f("ix_companies_org_number"), "companies", ["org_number"], unique=True)

    # Create accounts table
    op.create_table(
        "accounts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("company_id", sa.Integer(), nullable=False),
        sa.Column("account_number", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("description", sa.String(), nullable=True),
        sa.Column(
            "account_type",
            sa.Enum(
                "asset",
                "equity_liability",
                "revenue",
                "cost_goods",
                "cost_local",
                "cost_other",
                "cost_personnel",
                "cost_misc",
                name="accounttype",
            ),
            nullable=False,
        ),
        sa.Column("opening_balance", sa.Numeric(precision=15, scale=2), nullable=False, server_default="0"),
        sa.Column("current_balance", sa.Numeric(precision=15, scale=2), nullable=False, server_default="0"),
        sa.Column("active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("is_bas_account", sa.Boolean(), nullable=False, server_default="true"),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_accounts_id"), "accounts", ["id"], unique=False)
    op.create_index(op.f("ix_accounts_account_number"), "accounts", ["account_number"], unique=False)

    # Create verifications table
    op.create_table(
        "verifications",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("company_id", sa.Integer(), nullable=False),
        sa.Column("verification_number", sa.Integer(), nullable=False),
        sa.Column("series", sa.String(length=10), nullable=False, server_default="A"),
        sa.Column("transaction_date", sa.Date(), nullable=False),
        sa.Column("registration_date", sa.Date(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("locked", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_verifications_id"), "verifications", ["id"], unique=False)
    op.create_index(
        op.f("ix_verifications_verification_number"), "verifications", ["verification_number"], unique=False
    )
    op.create_index(op.f("ix_verifications_transaction_date"), "verifications", ["transaction_date"], unique=False)

    # Create transaction_lines table
    op.create_table(
        "transaction_lines",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("verification_id", sa.Integer(), nullable=False),
        sa.Column("account_id", sa.Integer(), nullable=False),
        sa.Column("debit", sa.Numeric(precision=15, scale=2), nullable=False, server_default="0"),
        sa.Column("credit", sa.Numeric(precision=15, scale=2), nullable=False, server_default="0"),
        sa.Column("description", sa.String(), nullable=True),
        sa.ForeignKeyConstraint(
            ["account_id"],
            ["accounts.id"],
        ),
        sa.ForeignKeyConstraint(["verification_id"], ["verifications.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_transaction_lines_id"), "transaction_lines", ["id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_transaction_lines_id"), table_name="transaction_lines")
    op.drop_table("transaction_lines")
    op.drop_index(op.f("ix_verifications_transaction_date"), table_name="verifications")
    op.drop_index(op.f("ix_verifications_verification_number"), table_name="verifications")
    op.drop_index(op.f("ix_verifications_id"), table_name="verifications")
    op.drop_table("verifications")
    op.drop_index(op.f("ix_accounts_account_number"), table_name="accounts")
    op.drop_index(op.f("ix_accounts_id"), table_name="accounts")
    op.drop_table("accounts")
    op.drop_index(op.f("ix_companies_org_number"), table_name="companies")
    op.drop_index(op.f("ix_companies_id"), table_name="companies")
    op.drop_table("companies")
    op.execute("DROP TYPE accountingbasis")
    op.execute("DROP TYPE accounttype")
