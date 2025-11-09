from sqlalchemy import Column, Integer, String, Boolean, Enum as SQLEnum, ForeignKey, Numeric
from sqlalchemy.orm import relationship
from app.database import Base
import enum


class AccountType(str, enum.Enum):
    """Swedish BAS account types"""
    ASSET = "asset"              # Tillgång (1xxx)
    EQUITY_LIABILITY = "equity_liability"  # Eget kapital och skuld (2xxx)
    REVENUE = "revenue"          # Intäkt (3xxx)
    COST_GOODS = "cost_goods"    # Kostnad varor/material (4xxx)
    COST_LOCAL = "cost_local"    # Kostnad lokaler (5xxx)
    COST_OTHER = "cost_other"    # Övriga kostnader (6xxx)
    COST_PERSONNEL = "cost_personnel"  # Personalkostnad (7xxx)
    COST_MISC = "cost_misc"      # Diverse kostnader (8xxx)


class Account(Base):
    """Chart of accounts (Kontoplan) - Based on BAS 2024"""
    __tablename__ = "accounts"

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False)

    # Account details
    account_number = Column(Integer, nullable=False, index=True)  # 1000-8999
    name = Column(String, nullable=False)  # Account name in Swedish
    description = Column(String, nullable=True)  # Optional detailed description

    # Account classification
    account_type = Column(SQLEnum(AccountType, values_callable=lambda x: [e.value for e in x]), nullable=False)

    # Balance tracking
    opening_balance = Column(Numeric(15, 2), default=0, nullable=False)  # Ingående balans (IB)
    current_balance = Column(Numeric(15, 2), default=0, nullable=False)  # Current balance

    # Status
    active = Column(Boolean, default=True, nullable=False)
    is_bas_account = Column(Boolean, default=True)  # True if from BAS kontoplan

    # Relationships
    company = relationship("Company", back_populates="accounts")
    transaction_lines = relationship("TransactionLine", back_populates="account")

    def __repr__(self):
        return f"<Account {self.account_number} - {self.name}>"

    @property
    def balance(self):
        """Current account balance"""
        return self.current_balance
