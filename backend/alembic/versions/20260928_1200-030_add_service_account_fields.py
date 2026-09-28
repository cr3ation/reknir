"""add service account fields to users

Revision ID: 030
Revises: 029
Create Date: 2026-09-28 12:00:00.000000

This migration first shipped as an uncommitted "027" on the production host,
where the columns therefore already exist. Every step checks before acting so
the migration is safe both there and on a fresh database.
"""

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "030"
down_revision = "029"
branch_labels = None
depends_on = None


def _columns() -> set[str]:
    inspector = sa.inspect(op.get_bind())
    return {c["name"] for c in inspector.get_columns("users")}


def _indexes() -> set[str]:
    inspector = sa.inspect(op.get_bind())
    return {i["name"] for i in inspector.get_indexes("users")}


def upgrade() -> None:
    existing = _columns()
    if "is_service_account" not in existing:
        op.add_column(
            "users",
            sa.Column("is_service_account", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        )
    if "owner_id" not in existing:
        op.add_column(
            "users",
            sa.Column("owner_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        )
    if "api_key_hash" not in existing:
        op.add_column("users", sa.Column("api_key_hash", sa.String(255), nullable=True))
    if "ix_users_api_key_hash" not in _indexes():
        op.create_index("ix_users_api_key_hash", "users", ["api_key_hash"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_users_api_key_hash", table_name="users")
    op.drop_column("users", "api_key_hash")
    op.drop_column("users", "owner_id")
    op.drop_column("users", "is_service_account")
