import enum

from sqlalchemy import Column, Date, Integer, String
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.orm import relationship

from app.database import Base


class AccountingBasis(str, enum.Enum):
    """Accounting basis type"""

    ACCRUAL = "accrual"  # Bokföringsmässiga grunder
    CASH = "cash"  # Kontantmetoden


class VATReportingPeriod(str, enum.Enum):
    """VAT reporting period frequency"""

    MONTHLY = "monthly"  # Månatlig (omsättning > 40M SEK/år)
    QUARTERLY = "quarterly"  # Kvartalsvis (vanligast för små företag)
    YEARLY = "yearly"  # Årlig (omsättning < 1M SEK/år)


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
    fiscal_year_end = Column(Date, nullable=False)  # Räkenskapsår slut

    # Accounting settings
    accounting_basis = Column(
        SQLEnum(AccountingBasis, values_callable=lambda x: [e.value for e in x]),
        default=AccountingBasis.ACCRUAL,
        nullable=False,
    )

    # VAT settings
    vat_reporting_period = Column(
        SQLEnum(VATReportingPeriod, values_callable=lambda x: [e.value for e in x]),
        default=VATReportingPeriod.QUARTERLY,
        nullable=False,
    )

    # Logo
    logo_filename = Column(String, nullable=True)  # Filename of uploaded logo

    # Relationships
    accounts = relationship("Account", back_populates="company", cascade="all, delete-orphan")
    verifications = relationship("Verification", back_populates="company", cascade="all, delete-orphan")
    posting_templates = relationship("PostingTemplate", back_populates="company", cascade="all, delete-orphan")
    default_accounts = relationship("DefaultAccount", back_populates="company", cascade="all, delete-orphan")
    fiscal_years = relationship("FiscalYear", back_populates="company", cascade="all, delete-orphan")
    expenses = relationship("Expense", back_populates="company", cascade="all, delete-orphan")
    users = relationship("CompanyUser", back_populates="company", cascade="all, delete-orphan")
    invitations = relationship("Invitation", back_populates="company", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Company {self.name} ({self.org_number})>"
    
    @property
    def vat_number(self) -> str:
        """
        Calculate Swedish VAT number from organization number.
        Swedish VAT numbers follow the format: SE + 10-digit org_number (without dash) + 01
        Example: 556644-4354 becomes SE5566444354001
        """
        if not self.org_number:
            return ""
        
        # Remove any dashes and spaces from org_number
        clean_org_number = self.org_number.replace('-', '').replace(' ', '')
        
        # Swedish VAT number format: SE + org_number (10 digits) + 01
        if len(clean_org_number) == 10 and clean_org_number.isdigit():
            return f"SE{clean_org_number}01"
        
        return ""
