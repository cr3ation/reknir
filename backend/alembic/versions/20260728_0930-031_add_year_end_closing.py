"""add year end closing tables

Revision ID: 031
Revises: 030
Create Date: 2026-07-28 09:30:00.000000

The year-end closing stores the user's answers, not draft verifications. The
postings are recomputed from (answers, ledger) on every read and only reach the
ledger when the closing is completed, so there is nothing here that mirrors the
verification tables.

year_end_closings is one row per fiscal year (unique FK), year_end_adjustments
holds the answers from the adjustments step, and year_end_closing_events is the
audit trail for completing and reopening.
"""

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "031"
down_revision = "030"
branch_labels = None
depends_on = None

CLOSING_STATUS_VALUES = ("in_progress", "completed")
CLOSING_STEP_VALUES = ("preparation", "adjustments", "tax", "review")
ADJUSTMENT_TYPE_VALUES = (
    "stock",
    "depreciation",
    "accrued_expense",
    "prepaid_expense",
    "accrued_revenue",
    "prepaid_revenue",
)
CLOSING_EVENT_TYPE_VALUES = ("completed", "reopened")


def upgrade() -> None:
    # The enum types are created by op.create_table itself, which emits CREATE TYPE for
    # every sa.Enum column. Creating them up front the way migration 025 does would
    # collide with that — 025 gets away with it because op.add_column does not.
    # Each type below is used by exactly one table, so no type is created twice.
    op.create_table(
        "year_end_closings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("company_id", sa.Integer(), nullable=False),
        sa.Column("fiscal_year_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.Enum(*CLOSING_STATUS_VALUES, name="closingstatus"), nullable=False),
        sa.Column("current_step", sa.Enum(*CLOSING_STEP_VALUES, name="closingstep"), nullable=False),
        sa.Column("preparation_confirmed", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("bank_statement_balance", sa.Numeric(15, 2), nullable=True),
        sa.Column("acknowledged_warnings", sa.JSON(), nullable=False),
        sa.Column("tax_amount_override", sa.Numeric(15, 2), nullable=True),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("completed_by", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"]),
        sa.ForeignKeyConstraint(["fiscal_year_id"], ["fiscal_years.id"]),
        sa.ForeignKeyConstraint(["completed_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_year_end_closings_id"), "year_end_closings", ["id"])
    op.create_index(op.f("ix_year_end_closings_company_id"), "year_end_closings", ["company_id"])
    op.create_index(op.f("ix_year_end_closings_fiscal_year_id"), "year_end_closings", ["fiscal_year_id"], unique=True)

    op.create_table(
        "year_end_adjustments",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("closing_id", sa.Integer(), nullable=False),
        sa.Column("adjustment_type", sa.Enum(*ADJUSTMENT_TYPE_VALUES, name="adjustmenttype"), nullable=False),
        sa.Column("amount", sa.Numeric(15, 2), nullable=False),
        sa.Column("balance_account_id", sa.Integer(), nullable=True),
        sa.Column("result_account_id", sa.Integer(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["closing_id"], ["year_end_closings.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["balance_account_id"], ["accounts.id"]),
        sa.ForeignKeyConstraint(["result_account_id"], ["accounts.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_year_end_adjustments_id"), "year_end_adjustments", ["id"])
    op.create_index(op.f("ix_year_end_adjustments_closing_id"), "year_end_adjustments", ["closing_id"])

    op.create_table(
        "year_end_closing_events",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("closing_id", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.Enum(*CLOSING_EVENT_TYPE_VALUES, name="closingeventtype"), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["closing_id"], ["year_end_closings.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_year_end_closing_events_id"), "year_end_closing_events", ["id"])
    op.create_index(op.f("ix_year_end_closing_events_closing_id"), "year_end_closing_events", ["closing_id"])


def downgrade() -> None:
    bind = op.get_bind()

    op.drop_table("year_end_closing_events")
    op.drop_table("year_end_adjustments")
    op.drop_table("year_end_closings")

    for name in ("closingeventtype", "adjustmenttype", "closingstep", "closingstatus"):
        sa.Enum(name=name).drop(bind, checkfirst=True)
