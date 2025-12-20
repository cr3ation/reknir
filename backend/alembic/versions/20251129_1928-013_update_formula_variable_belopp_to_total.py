"""update_formula_variable_belopp_to_total

Revision ID: 013
Revises: 012
Create Date: 2025-11-29 19:28:31.461737

"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "013"
down_revision = "012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Update all posting template lines to use {total} instead of {belopp}
    op.execute(
        "UPDATE posting_template_lines SET formula = REPLACE(formula, '{belopp}', '{total}') WHERE formula LIKE '%{belopp}%'"
    )


def downgrade() -> None:
    # Revert back to {belopp} from {total}
    op.execute(
        "UPDATE posting_template_lines SET formula = REPLACE(formula, '{total}', '{belopp}') WHERE formula LIKE '%{total}%'"
    )
