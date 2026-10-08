"""period locks, gap explanations, audit log, verification reversal links

Revision ID: 032
Revises: 031
Create Date: 2026-10-04 12:00:00.000000
"""

import sqlalchemy as sa

from alembic import op

revision = "032"
down_revision = "031"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "verifications",
        sa.Column("reverses_verification_id", sa.Integer(), sa.ForeignKey("verifications.id"), nullable=True),
    )
    op.add_column(
        "verifications",
        sa.Column("reversed_by_verification_id", sa.Integer(), sa.ForeignKey("verifications.id"), nullable=True),
    )
    op.create_table(
        "period_locks",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("company_id", sa.Integer(), sa.ForeignKey("companies.id", ondelete="CASCADE"), nullable=False),
        sa.Column("locked_through", sa.Date(), nullable=False),
        sa.Column("note", sa.String(255), nullable=True),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_period_locks_company_id", "period_locks", ["company_id"])
    op.create_table(
        "verification_gap_explanations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("company_id", sa.Integer(), sa.ForeignKey("companies.id", ondelete="CASCADE"), nullable=False),
        sa.Column("fiscal_year_id", sa.Integer(), sa.ForeignKey("fiscal_years.id", ondelete="CASCADE"), nullable=False),
        sa.Column("series", sa.String(10), nullable=False),
        sa.Column("verification_number", sa.Integer(), nullable=False),
        sa.Column("explanation", sa.Text(), nullable=False),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("company_id", "fiscal_year_id", "series", "verification_number", name="uq_gap_explanation"),
    )
    op.create_index("ix_verification_gap_explanations_company_id", "verification_gap_explanations", ["company_id"])
    op.create_table(
        "audit_log",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("company_id", sa.Integer(), nullable=True),
        sa.Column("user_email", sa.String(255), nullable=True),
        sa.Column("action", sa.String(10), nullable=False),
        sa.Column("table_name", sa.String(64), nullable=False),
        sa.Column("record_id", sa.Integer(), nullable=True),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("changes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_audit_log_company_id", "audit_log", ["company_id"])
    op.create_index("ix_audit_log_table_name", "audit_log", ["table_name"])
    op.create_index("ix_audit_log_record_id", "audit_log", ["record_id"])
    op.create_index("ix_audit_log_created_at", "audit_log", ["created_at"])


def downgrade() -> None:
    op.drop_table("audit_log")
    op.drop_table("verification_gap_explanations")
    op.drop_table("period_locks")
    op.drop_column("verifications", "reversed_by_verification_id")
    op.drop_column("verifications", "reverses_verification_id")
