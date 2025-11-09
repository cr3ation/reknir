from sqlalchemy import Column, Integer, String, Date, Enum as SQLEnum
from sqlalchemy.orm import relationship
from app.database import Base
import enum


class AccountingBasis(str, enum.Enum):
    """Accounting basis type"""
    ACCRUAL = "accrual"  # Bokföringsmässiga grunder
    CASH = "cash"  # Kontantmetoden


class Company(Base):
    """Company/organization information"""
    __tablename__ = "companies"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    org_number = Column(String(10), unique=True, nullable=False, index=True)  # Organisationsnummer

    # Fiscal year
    fiscal_year_start = Column(Date, nullable=False)  # Räkenskapsår start
    fiscal_year_end = Column(Date, nullable=False)    # Räkenskapsår slut

    # Accounting settings
    accounting_basis = Column(
        SQLEnum(AccountingBasis, values_callable=lambda x: [e.value for e in x]),
        default=AccountingBasis.ACCRUAL,
        nullable=False
    )

    # Relationships
    accounts = relationship("Account", back_populates="company", cascade="all, delete-orphan")
    verifications = relationship("Verification", back_populates="company", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Company {self.name} ({self.org_number})>"
