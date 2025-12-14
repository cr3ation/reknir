import enum
from datetime import datetime

from sqlalchemy import Column, Date, DateTime, ForeignKey, Integer, Numeric, String
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.orm import relationship

from app.database import Base


class ExpenseStatus(str, enum.Enum):
    """Status for expense reports"""

    DRAFT = "draft"
    SUBMITTED = "submitted"
    APPROVED = "approved"
    PAID = "paid"
    REJECTED = "rejected"


class Expense(Base):
    """
    Expense/Outlay model - for tracking employee expenses/receipts
    Swedish: Utlägg
    """

    __tablename__ = "expenses"

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False)

    # Who made the expense
    employee_name = Column(String(200), nullable=False)

    # Expense details
    expense_date = Column(Date, nullable=False)
    description = Column(String(500), nullable=False)
    amount = Column(Numeric(15, 2), nullable=False, default=0)  # Total amount including VAT
    vat_amount = Column(Numeric(15, 2), nullable=False, default=0)  # VAT portion

    # Categorization
    expense_account_id = Column(Integer, ForeignKey("accounts.id"), nullable=True)  # Expense account (e.g., 6540)
    vat_account_id = Column(Integer, ForeignKey("accounts.id"), nullable=True)  # VAT account (usually 2641)

    # Receipt file
    receipt_filename = Column(String(500), nullable=True)

    # Status and workflow
    status = Column(
        SQLEnum(ExpenseStatus, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        default=ExpenseStatus.DRAFT,
    )

    # When approved/paid
    approved_date = Column(DateTime, nullable=True)
    paid_date = Column(DateTime, nullable=True)

    # Link to verification when booked
    verification_id = Column(Integer, ForeignKey("verifications.id"), nullable=True)

    # Timestamps
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    company = relationship("Company", back_populates="expenses")
    expense_account = relationship("Account", foreign_keys=[expense_account_id])
    vat_account = relationship("Account", foreign_keys=[vat_account_id])
    verification = relationship("Verification", foreign_keys=[verification_id])
