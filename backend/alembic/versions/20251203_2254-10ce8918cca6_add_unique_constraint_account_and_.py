"""add_unique_constraint_account_and_notnull_verification_fiscal_year

Revision ID: 10ce8918cca6
Revises: 8c3d07e09af6
Create Date: 2025-12-03 22:54:09.947544

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '10ce8918cca6'
down_revision = '8c3d07e09af6'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add unique constraint to prevent duplicate account numbers within the same fiscal year
    op.create_unique_constraint(
        'uq_account_company_fiscal_year_number',
        'accounts',
        ['company_id', 'fiscal_year_id', 'account_number']
    )

    # Make fiscal_year_id NOT NULL on verifications
    # First ensure all verifications have a fiscal_year_id set
    op.execute("""
        UPDATE verifications
        SET fiscal_year_id = (
            SELECT fiscal_years.id
            FROM fiscal_years
            WHERE fiscal_years.company_id = verifications.company_id
              AND verifications.transaction_date BETWEEN fiscal_years.start_date AND fiscal_years.end_date
            LIMIT 1
        )
        WHERE fiscal_year_id IS NULL
    """)

    # For any remaining NULL values, assign to the first fiscal year for that company
    op.execute("""
        UPDATE verifications
        SET fiscal_year_id = (
            SELECT MIN(id)
            FROM fiscal_years
            WHERE fiscal_years.company_id = verifications.company_id
        )
        WHERE fiscal_year_id IS NULL
    """)

    # Now make the column NOT NULL
    op.alter_column('verifications', 'fiscal_year_id',
                    existing_type=sa.INTEGER(),
                    nullable=False)


def downgrade() -> None:
    # Revert fiscal_year_id to nullable
    op.alter_column('verifications', 'fiscal_year_id',
                    existing_type=sa.INTEGER(),
                    nullable=True)

    # Drop unique constraint
    op.drop_constraint('uq_account_company_fiscal_year_number', 'accounts', type_='unique')
