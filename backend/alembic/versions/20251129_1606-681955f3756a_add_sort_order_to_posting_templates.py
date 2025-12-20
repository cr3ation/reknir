"""add sort_order to posting templates

Revision ID: 681955f3756a
Revises: 010
Create Date: 2025-11-29 16:06:24.538191

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '681955f3756a'
down_revision = '010'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add sort_order column to posting_templates
    op.add_column('posting_templates', sa.Column('sort_order', sa.Integer(), nullable=True))
    
    # Set default sort_order based on current id order
    op.execute("UPDATE posting_templates SET sort_order = id WHERE sort_order IS NULL")
    
    # Make sort_order not null after setting defaults
    op.alter_column('posting_templates', 'sort_order', nullable=False, server_default='999')


def downgrade() -> None:
    op.drop_column('posting_templates', 'sort_order')
