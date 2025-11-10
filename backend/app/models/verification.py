from sqlalchemy import Column, Integer, String, Date, Boolean, ForeignKey, Numeric, DateTime, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base


class Verification(Base):
    """
    Verification/Transaction (Verifikation)
    A verification contains one or more transaction lines that must balance
    """
    __tablename__ = "verifications"

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False)
    fiscal_year_id = Column(Integer, ForeignKey("fiscal_years.id"), nullable=True)  # Nullable for backwards compatibility

    # Verification identity
    verification_number = Column(Integer, nullable=False, index=True)  # Löpnummer
    series = Column(String(10), default="A", nullable=False)  # Serie (A, B, C, etc.)

    # Dates
    transaction_date = Column(Date, nullable=False, index=True)  # Transaktionsdatum
    registration_date = Column(Date, nullable=False, default=func.current_date())  # Registreringsdatum

    # Description
    description = Column(Text, nullable=False)  # Verifikationstext

    # Status
    locked = Column(Boolean, default=False, nullable=False)  # Locked after period close

    # Audit trail
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    company = relationship("Company", back_populates="verifications")
    fiscal_year = relationship("FiscalYear", back_populates="verifications")
    transaction_lines = relationship(
        "TransactionLine",
        back_populates="verification",
        cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<Verification {self.series}{self.verification_number} - {self.description[:30]}>"

    @property
    def is_balanced(self) -> bool:
        """Check if debit equals credit (required for Swedish bookkeeping)"""
        total_debit = sum(line.debit for line in self.transaction_lines)
        total_credit = sum(line.credit for line in self.transaction_lines)
        return abs(total_debit - total_credit) < 0.01  # Allow for rounding errors

    @property
    def total_amount(self) -> float:
        """Total amount (debit side)"""
        return sum(line.debit for line in self.transaction_lines)


class TransactionLine(Base):
    """
    Individual transaction line (Transaktionsrad)
    Part of a verification, represents debit or credit to an account
    """
    __tablename__ = "transaction_lines"

    id = Column(Integer, primary_key=True, index=True)
    verification_id = Column(Integer, ForeignKey("verifications.id"), nullable=False)
    account_id = Column(Integer, ForeignKey("accounts.id"), nullable=False)

    # Amounts (always use debit/credit, never negative numbers)
    debit = Column(Numeric(15, 2), default=0, nullable=False)   # Debet
    credit = Column(Numeric(15, 2), default=0, nullable=False)  # Kredit

    # Optional details
    description = Column(String, nullable=True)  # Line-specific description

    # Relationships
    verification = relationship("Verification", back_populates="transaction_lines")
    account = relationship("Account", back_populates="transaction_lines")

    def __repr__(self):
        return f"<TransactionLine Account:{self.account_id} D:{self.debit} C:{self.credit}>"

    @property
    def amount(self) -> float:
        """Net amount (debit - credit)"""
        return float(self.debit - self.credit)
