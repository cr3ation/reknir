"""Add restore_log table for tracking backup restore operations

Revision ID: 021
Revises: 020
Create Date: 2026-02-04 12:00:00.000000

Tracks all restore attempts with who performed them, which backup was used,
and whether the restore succeeded or failed.
"""

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "021"
down_revision = "020"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "restore_log",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("backup_id", sa.String(36), nullable=False),
        sa.Column("performed_by", sa.String(255), nullable=False),
        sa.Column("success", sa.Boolean(), nullable=False),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("backup_app_version", sa.String(20), nullable=True),
        sa.Column("backup_schema_version", sa.String(10), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("restore_log")
