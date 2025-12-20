"""update_formula_variable_belopp_to_total

Revision ID: f8d6d475181b
Revises: 681955f3756a
Create Date: 2025-11-29 19:28:31.461737

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'f8d6d475181b'
down_revision = '681955f3756a'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Update all posting template lines to use {total} instead of {belopp}
    op.execute("UPDATE posting_template_lines SET formula = REPLACE(formula, '{belopp}', '{total}') WHERE formula LIKE '%{belopp}%'")


def downgrade() -> None:
    # Revert back to {belopp} from {total}
    op.execute("UPDATE posting_template_lines SET formula = REPLACE(formula, '{total}', '{belopp}') WHERE formula LIKE '%{total}%'")
