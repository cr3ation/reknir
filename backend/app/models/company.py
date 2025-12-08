from sqlalchemy import Column, Integer, String, Date, Enum as SQLEnum
from sqlalchemy.orm import relationship
from app.database import Base
import enum


class AccountingBasis(str, enum.Enum):
    """Accounting basis type"""
    ACCRUAL = "accrual"  # Bokföringsmässiga grunder
    CASH = "cash"  # Kontantmetoden


class VATReportingPeriod(str, enum.Enum):
    """VAT reporting period frequency"""
    MONTHLY = "monthly"      # Månatlig (omsättning > 40M SEK/år)
    QUARTERLY = "quarterly"  # Kvartalsvis (vanligast för små företag)
    YEARLY = "yearly"        # Årlig (omsättning < 1M SEK/år)


class Company(Base):
    """Company/organization information"""
    __tablename__ = "companies"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    org_number = Column(String(15), unique=True, nullable=False, index=True)  # Organisationsnummer (XXXXXX-XXXX)

    # Contact information (for invoices)
    address = Column(String, nullable=True)
    postal_code = Column(String(10), nullable=True)
    city = Column(String, nullable=True)
    phone = Column(String(20), nullable=True)
    email = Column(String, nullable=True)

    # Fiscal year
    fiscal_year_start = Column(Date, nullable=False)  # Räkenskapsår start
    fiscal_year_end = Column(Date, nullable=False)    # Räkenskapsår slut

    # Accounting settings
    accounting_basis = Column(
        SQLEnum(AccountingBasis, values_callable=lambda x: [e.value for e in x]),
        default=AccountingBasis.ACCRUAL,
        nullable=False
    )

    # VAT settings
    vat_reporting_period = Column(
        SQLEnum(VATReportingPeriod, values_callable=lambda x: [e.value for e in x]),
        default=VATReportingPeriod.QUARTERLY,
        nullable=False
    )

    # Relationships
    accounts = relationship("Account", back_populates="company", cascade="all, delete-orphan")
    verifications = relationship("Verification", back_populates="company", cascade="all, delete-orphan")
    default_accounts = relationship("DefaultAccount", back_populates="company", cascade="all, delete-orphan")
    fiscal_years = relationship("FiscalYear", back_populates="company", cascade="all, delete-orphan")
    expenses = relationship("Expense", back_populates="company", cascade="all, delete-orphan")
    users = relationship("CompanyUser", back_populates="company", cascade="all, delete-orphan")
    invitations = relationship("Invitation", back_populates="company", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Company {self.name} ({self.org_number})>"
