import enum

from sqlalchemy import JSON, Boolean, Column, DateTime, ForeignKey, Integer, Numeric, Text
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base


class ClosingStatus(str, enum.Enum):
    """Lifecycle of a year-end closing"""

    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"


class ClosingStep(str, enum.Enum):
    """
    The wizard steps, in order.

    The server owns which step is reachable; the frontend renders what it is told.
    """

    PREPARATION = "preparation"  # Förberedelser och avstämning
    ADJUSTMENTS = "adjustments"  # Bokslutsjusteringar
    TAX = "tax"  # Skatt och årets resultat
    REVIEW = "review"  # Granska och slutför


class AdjustmentType(str, enum.Enum):
    """
    Kind of year-end adjustment (bokslutsjustering).

    DEPRECIATION is reserved but deliberately not offered by the wizard: proposing a
    depreciation amount requires a fixed asset register, which reknir does not have.
    The value exists so adding it later does not need an ALTER TYPE migration.
    """

    STOCK = "stock"  # Varulager
    DEPRECIATION = "depreciation"  # Avskrivning — reserved, not exposed in the wizard
    ACCRUED_EXPENSE = "accrued_expense"  # Upplupen kostnad
    PREPAID_EXPENSE = "prepaid_expense"  # Förutbetald kostnad
    ACCRUED_REVENUE = "accrued_revenue"  # Upplupen intäkt
    PREPAID_REVENUE = "prepaid_revenue"  # Förutbetald intäkt


class ClosingEventType(str, enum.Enum):
    """Auditable transitions of a closing"""

    COMPLETED = "completed"
    REOPENED = "reopened"


class YearEndClosing(Base):
    """
    Year-end closing (bokslut) for one fiscal year.

    Stores the user's answers, never draft verifications. The postings are a pure
    function of (answers, ledger) and are recomputed on every read, so changing an
    answer needs no reconciliation and burns no verification numbers. Nothing reaches
    the ledger until the closing is completed.
    """

    __tablename__ = "year_end_closings"

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False, index=True)
    fiscal_year_id = Column(Integer, ForeignKey("fiscal_years.id"), nullable=False, unique=True, index=True)

    status = Column(
        SQLEnum(ClosingStatus, values_callable=lambda x: [e.value for e in x]),
        default=ClosingStatus.IN_PROGRESS,
        nullable=False,
    )
    current_step = Column(
        SQLEnum(ClosingStep, values_callable=lambda x: [e.value for e in x]),
        default=ClosingStep.PREPARATION,
        nullable=False,
    )

    # Step 1: the user confirms the bookkeeping is complete and types the balance their
    # bank actually showed on the last day of the year. reknir has no bank feed, so this
    # is the only way to reconcile.
    preparation_confirmed = Column(Boolean, default=False, nullable=False)
    bank_statement_balance = Column(Numeric(15, 2), nullable=True)

    # Yellow checks the user has explicitly accepted, stored as a list of check codes.
    acknowledged_warnings = Column(JSON, default=list, nullable=False)

    # Step 3: tax. Computed by the service, but the user may override it.
    tax_amount_override = Column(Numeric(15, 2), nullable=True)

    completed_at = Column(DateTime, nullable=True)
    completed_by = Column(Integer, ForeignKey("users.id"), nullable=True)

    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)

    company = relationship("Company")
    fiscal_year = relationship("FiscalYear")
    adjustments = relationship(
        "YearEndAdjustment",
        back_populates="closing",
        cascade="all, delete-orphan",
        order_by="YearEndAdjustment.id",
    )
    events = relationship(
        "YearEndClosingEvent",
        back_populates="closing",
        cascade="all, delete-orphan",
        order_by="YearEndClosingEvent.id",
    )

    def __repr__(self):
        return f"<YearEndClosing fiscal_year={self.fiscal_year_id} status={self.status}>"


class YearEndAdjustment(Base):
    """
    One answer the user gave in the adjustments step.

    Every kind of adjustment is a row here rather than its own table, so a new kind
    costs an enum value instead of a schema change. Each row resolves to exactly one
    balanced posting: the balance account against the result account.
    """

    __tablename__ = "year_end_adjustments"

    id = Column(Integer, primary_key=True, index=True)
    closing_id = Column(Integer, ForeignKey("year_end_closings.id", ondelete="CASCADE"), nullable=False, index=True)

    adjustment_type = Column(
        SQLEnum(AdjustmentType, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
    )
    amount = Column(Numeric(15, 2), nullable=False)

    # Optional overrides. When null the service resolves the accounts from the company's
    # default account mapping, creating them in this fiscal year if they do not exist.
    balance_account_id = Column(Integer, ForeignKey("accounts.id"), nullable=True)
    result_account_id = Column(Integer, ForeignKey("accounts.id"), nullable=True)

    description = Column(Text, nullable=True)

    closing = relationship("YearEndClosing", back_populates="adjustments")
    balance_account = relationship("Account", foreign_keys=[balance_account_id])
    result_account = relationship("Account", foreign_keys=[result_account_id])

    def __repr__(self):
        return f"<YearEndAdjustment {self.adjustment_type} {self.amount}>"


class YearEndClosingEvent(Base):
    """
    Audit trail for the irreversible transitions.

    Bokföringslagen expects a closed period to stay closed; when it is reopened anyway
    the reason and the person responsible must remain visible afterwards.
    """

    __tablename__ = "year_end_closing_events"

    id = Column(Integer, primary_key=True, index=True)
    closing_id = Column(Integer, ForeignKey("year_end_closings.id", ondelete="CASCADE"), nullable=False, index=True)

    event_type = Column(
        SQLEnum(ClosingEventType, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
    )
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    reason = Column(Text, nullable=True)  # Required for REOPENED, enforced in the schema

    created_at = Column(DateTime, server_default=func.now(), nullable=False)

    closing = relationship("YearEndClosing", back_populates="events")
    user = relationship("User")

    def __repr__(self):
        return f"<YearEndClosingEvent {self.event_type} closing={self.closing_id}>"
