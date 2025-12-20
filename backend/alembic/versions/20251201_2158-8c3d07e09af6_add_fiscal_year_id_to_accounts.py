"""add_fiscal_year_id_to_accounts

Revision ID: 8c3d07e09af6
Revises: 6b60dd14b9bb
Create Date: 2025-12-01 21:58:39.559120

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '8c3d07e09af6'
down_revision = '6b60dd14b9bb'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Step 1: Add fiscal_year_id column as nullable
    op.add_column('accounts', sa.Column('fiscal_year_id', sa.Integer(), nullable=True))

    # Step 2: For each existing account, set fiscal_year_id to the first fiscal year for that company
    # This uses a subquery to find the minimum fiscal year id for each company
    op.execute("""
        UPDATE accounts
        SET fiscal_year_id = (
            SELECT MIN(id)
            FROM fiscal_years
            WHERE fiscal_years.company_id = accounts.company_id
        )
        WHERE fiscal_year_id IS NULL
    """)

    # Step 3: Make fiscal_year_id NOT NULL now that all accounts have a value
    op.alter_column('accounts', 'fiscal_year_id',
               existing_type=sa.Integer(),
               nullable=False)

    # Step 4: Add foreign key constraint
    op.create_foreign_key('accounts_fiscal_year_id_fkey', 'accounts', 'fiscal_years', ['fiscal_year_id'], ['id'])


def downgrade() -> None:
    # Drop foreign key constraint
    op.drop_constraint('accounts_fiscal_year_id_fkey', 'accounts', type_='foreignkey')

    # Drop fiscal_year_id column
    op.drop_column('accounts', 'fiscal_year_id')
