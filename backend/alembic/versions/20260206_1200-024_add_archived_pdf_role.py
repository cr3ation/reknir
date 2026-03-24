"""add archived_pdf to attachmentrole enum

Revision ID: 024
Revises: 023
Create Date: 2026-02-06 12:00:00.000000

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "024"
down_revision: str | None = "023"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Add ARCHIVED_PDF to AttachmentRole enum (uppercase to match existing values)
    op.execute("ALTER TYPE attachmentrole ADD VALUE 'ARCHIVED_PDF'")


def downgrade() -> None:
    # PostgreSQL does not support removing enum values
    pass
