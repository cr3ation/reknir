"""add service account fields to users

Revision ID: 027
Revises: 026
Create Date: 2026-04-06 13:00:00.000000

"""

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "027"
down_revision = "026"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("is_service_account", sa.Boolean(), server_default=sa.text("false"), nullable=False))
    op.add_column("users", sa.Column("owner_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True))
    op.add_column("users", sa.Column("api_key_hash", sa.String(255), nullable=True))
    op.create_index("ix_users_api_key_hash", "users", ["api_key_hash"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_users_api_key_hash", table_name="users")
    op.drop_column("users", "api_key_hash")
    op.drop_column("users", "owner_id")
    op.drop_column("users", "is_service_account")
