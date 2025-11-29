"""remove_cost_center_project_from_template_lines

Revision ID: cc54b3343630
Revises: 009
Create Date: 2025-11-29 11:17:02.075461

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'cc54b3343630'
down_revision = '009'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Remove cost_center and project columns from verification_template_lines
    op.drop_column('verification_template_lines', 'cost_center')
    op.drop_column('verification_template_lines', 'project')


def downgrade() -> None:
    # Add back cost_center and project columns
    op.add_column('verification_template_lines', sa.Column('cost_center', sa.String(length=50), nullable=True))
    op.add_column('verification_template_lines', sa.Column('project', sa.String(length=50), nullable=True))
