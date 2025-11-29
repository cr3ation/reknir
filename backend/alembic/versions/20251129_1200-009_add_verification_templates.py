"""add verification templates

Revision ID: 009
Revises: 008
Create Date: 2025-11-29 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '009'
down_revision: Union[str, None] = '008'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create verification_templates table
    op.create_table('verification_templates',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('company_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('description', sa.String(length=255), nullable=False),
        sa.Column('default_series', sa.String(length=10), nullable=True),
        sa.Column('default_journal_text', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['company_id'], ['companies.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_verification_templates_id'), 'verification_templates', ['id'], unique=False)
    op.create_index(op.f('ix_verification_templates_name'), 'verification_templates', ['name'], unique=False)

    # Create verification_template_lines table
    op.create_table('verification_template_lines',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('template_id', sa.Integer(), nullable=False),
        sa.Column('account_id', sa.Integer(), nullable=False),
        sa.Column('formula', sa.String(length=500), nullable=False),
        sa.Column('description', sa.String(length=255), nullable=True),
        sa.Column('sort_order', sa.Integer(), nullable=False, server_default='0'),
        sa.ForeignKeyConstraint(['account_id'], ['accounts.id'], ),
        sa.ForeignKeyConstraint(['template_id'], ['verification_templates.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_verification_template_lines_id'), 'verification_template_lines', ['id'], unique=False)

    # Add unique constraint on company_id + name for verification_templates
    op.create_unique_constraint('uq_verification_templates_company_name', 'verification_templates', ['company_id', 'name'])


def downgrade() -> None:
    # Drop unique constraint
    op.drop_constraint('uq_verification_templates_company_name', 'verification_templates', type_='unique')
    
    # Drop indexes and tables
    op.drop_index(op.f('ix_verification_template_lines_id'), table_name='verification_template_lines')
    op.drop_table('verification_template_lines')
    
    op.drop_index(op.f('ix_verification_templates_name'), table_name='verification_templates')
    op.drop_index(op.f('ix_verification_templates_id'), table_name='verification_templates')
    op.drop_table('verification_templates')