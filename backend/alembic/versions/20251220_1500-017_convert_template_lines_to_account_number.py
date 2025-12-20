"""convert posting template lines from account_id to account_number

Revision ID: 017
Revises: 016
Create Date: 2025-12-20 15:00:00.000000

This migration converts posting_template_lines to use account_number instead of account_id.
This makes templates reusable across fiscal years since account_number is the stable
identifier while account_id is fiscal-year-specific.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "017"
down_revision: str | None = "016"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Step 1: Add account_number column
    op.add_column(
        "posting_template_lines",
        sa.Column("account_number", sa.Integer(), nullable=True),
    )

    # Step 2: Populate account_number from the referenced account
    op.execute("""
        UPDATE posting_template_lines ptl
        SET account_number = a.account_number
        FROM accounts a
        WHERE ptl.account_id = a.id
    """)

    # Step 3: Make account_number NOT NULL now that it's populated
    op.alter_column("posting_template_lines", "account_number", nullable=False)

    # Step 4: Drop the foreign key constraint on account_id
    op.drop_constraint(
        "posting_template_lines_account_id_fkey",
        "posting_template_lines",
        type_="foreignkey",
    )

    # Step 5: Drop the account_id column
    op.drop_column("posting_template_lines", "account_id")


def downgrade() -> None:
    # Note: Downgrade will lose data because we can't reliably determine
    # which specific account_id to use (there may be multiple accounts
    # with the same account_number across different fiscal years)

    # Step 1: Add account_id column back
    op.add_column(
        "posting_template_lines",
        sa.Column("account_id", sa.Integer(), nullable=True),
    )

    # Step 2: Try to populate account_id from accounts (using first match)
    # This is a best-effort recovery - we pick the first account with matching number
    op.execute("""
        UPDATE posting_template_lines ptl
        SET account_id = (
            SELECT a.id FROM accounts a
            WHERE a.account_number = ptl.account_number
            LIMIT 1
        )
    """)

    # Step 3: Make account_id NOT NULL
    op.alter_column("posting_template_lines", "account_id", nullable=False)

    # Step 4: Re-add foreign key constraint
    op.create_foreign_key(
        "posting_template_lines_account_id_fkey",
        "posting_template_lines",
        "accounts",
        ["account_id"],
        ["id"],
    )

    # Step 5: Drop account_number column
    op.drop_column("posting_template_lines", "account_number")
