"""add backup_schedule table

Revision ID: 026
Revises: 025
Create Date: 2026-04-06 12:00:00.000000

"""

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "026"
down_revision = "025"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "backup_schedule",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("enabled", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("interval_hours", sa.Integer(), server_default=sa.text("24"), nullable=False),
        sa.Column("max_backups", sa.Integer(), server_default=sa.text("30"), nullable=False),
        sa.Column("last_backup_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("next_backup_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("preferred_time", sa.Time(), server_default=sa.text("'03:00:00'"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    # Insert default row (single-row table)
    op.execute(
        "INSERT INTO backup_schedule (id, enabled, interval_hours, max_backups) "
        "VALUES (1, false, 24, 30)"
    )


def downgrade() -> None:
    op.drop_table("backup_schedule")
