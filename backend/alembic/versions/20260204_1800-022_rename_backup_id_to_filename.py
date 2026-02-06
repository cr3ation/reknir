"""Rename backup_id to backup_filename in restore_log

Revision ID: 022
Revises: 021
Create Date: 2026-02-04 18:00:00.000000

The backup_id field was renamed to backup_filename to better reflect
that we use the archive filename as the identifier for backups.
"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "022"
down_revision = "021"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "restore_log",
        "backup_id",
        new_column_name="backup_filename",
    )


def downgrade() -> None:
    op.alter_column(
        "restore_log",
        "backup_filename",
        new_column_name="backup_id",
    )
