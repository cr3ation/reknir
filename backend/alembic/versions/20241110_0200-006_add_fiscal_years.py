"""add fiscal years

Revision ID: 006
Revises: 005
Create Date: 2024-11-10 02:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "006"
down_revision: str | None = "005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Create fiscal_years table
    op.create_table(
        "fiscal_years",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("company_id", sa.Integer(), nullable=False),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("label", sa.String(length=100), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column("is_closed", sa.Boolean(), nullable=False, server_default="false"),
        sa.ForeignKeyConstraint(
            ["company_id"],
            ["companies.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_fiscal_years_id"), "fiscal_years", ["id"], unique=False)
    op.create_index(op.f("ix_fiscal_years_year"), "fiscal_years", ["year"], unique=False)

    # Add fiscal_year_id to verifications table
    op.add_column("verifications", sa.Column("fiscal_year_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_verifications_fiscal_year_id", "verifications", "fiscal_years", ["fiscal_year_id"], ["id"]
    )


def downgrade() -> None:
    # Remove fiscal_year_id from verifications
    op.drop_constraint("fk_verifications_fiscal_year_id", "verifications", type_="foreignkey")
    op.drop_column("verifications", "fiscal_year_id")

    # Drop fiscal_years table
    op.drop_index(op.f("ix_fiscal_years_year"), table_name="fiscal_years")
    op.drop_index(op.f("ix_fiscal_years_id"), table_name="fiscal_years")
    op.drop_table("fiscal_years")
