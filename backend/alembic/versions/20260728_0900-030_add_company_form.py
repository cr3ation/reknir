"""add company form

Revision ID: 030
Revises: 029
Create Date: 2026-07-28 09:00:00.000000

The year-end closing posts the result differently depending on the company form:
a limited company books corporate income tax (8910/2510) and closes the result
against 2099, while a sole trader books no company-level tax at all and closes
against the owner's equity (2019). Nothing in the schema recorded which form a
company has, so the column is added here.

Nullable on purpose: existing companies predate the column and the closing asks
for the form rather than assuming one.
"""

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "030"
down_revision = "029"
branch_labels = None
depends_on = None

COMPANY_FORM_VALUES = (
    "limited_company",
    "sole_trader",
    "trading_partnership",
    "limited_partnership",
    "economic_association",
)


def upgrade() -> None:
    companyform_enum = sa.Enum(*COMPANY_FORM_VALUES, name="companyform")
    companyform_enum.create(op.get_bind(), checkfirst=True)

    op.add_column(
        "companies",
        sa.Column("company_form", sa.Enum(*COMPANY_FORM_VALUES, name="companyform"), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("companies", "company_form")

    companyform_enum = sa.Enum(*COMPANY_FORM_VALUES, name="companyform")
    companyform_enum.drop(op.get_bind(), checkfirst=True)
