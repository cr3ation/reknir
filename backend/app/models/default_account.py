from sqlalchemy import Column, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import relationship

from app.database import Base


class DefaultAccountType(str):
    """Types of default accounts that can be configured"""

    # Revenue accounts by VAT rate
    REVENUE_25 = "revenue_25"  # Försäljning 25% moms
    REVENUE_12 = "revenue_12"  # Försäljning 12% moms
    REVENUE_6 = "revenue_6"  # Försäljning 6% moms
    REVENUE_0 = "revenue_0"  # Försäljning 0% moms (export)

    # VAT accounts
    VAT_OUTGOING_25 = "vat_outgoing_25"  # Utgående moms 25%
    VAT_OUTGOING_12 = "vat_outgoing_12"  # Utgående moms 12%
    VAT_OUTGOING_6 = "vat_outgoing_6"  # Utgående moms 6%
    VAT_INCOMING_25 = "vat_incoming_25"  # Ingående moms 25%
    VAT_INCOMING_12 = "vat_incoming_12"  # Ingående moms 12%
    VAT_INCOMING_6 = "vat_incoming_6"  # Ingående moms 6%

    # Receivables/Payables
    ACCOUNTS_RECEIVABLE = "accounts_receivable"  # Kundfordringar (1510)
    ACCOUNTS_PAYABLE = "accounts_payable"  # Leverantörsskulder (2440)

    # Default expense account
    EXPENSE_DEFAULT = "expense_default"  # Övriga externa tjänster (6570)

    # Liquid assets
    BANK = "bank"  # Företagskonto/bankgiro (1930)
    CASH = "cash"  # Kassa (1910)

    # Year-end closing: inventory (varulager)
    INVENTORY_STOCK = "inventory_stock"  # Lager av handelsvaror (1460)
    INVENTORY_CHANGE = "inventory_change"  # Förändring av lager (4990)

    # Year-end closing: accruals (periodiseringar)
    PREPAID_EXPENSE = "prepaid_expense"  # Förutbetald kostnad, interim asset (1790)
    ACCRUED_REVENUE = "accrued_revenue"  # Upplupen intäkt, interim asset (1790)
    ACCRUED_EXPENSE = "accrued_expense"  # Upplupen kostnad, interim liability (2990)
    PREPAID_REVENUE = "prepaid_revenue"  # Förutbetald intäkt, interim liability (2990)

    # Year-end closing: tax (only posted for a limited company)
    TAX_EXPENSE = "tax_expense"  # Skatt på årets resultat (8910)
    TAX_LIABILITY = "tax_liability"  # Skatteskulder (2510)

    # Year-end closing: the result itself
    YEAR_RESULT_EXPENSE = "year_result_expense"  # Årets resultat, income statement side (8999)
    YEAR_RESULT_EQUITY = "year_result_equity"  # Årets resultat, balance sheet side (2099 AB / 2019 EF)


class DefaultAccount(Base):
    """
    Maps default account types to actual accounts for a company.
    This allows different companies to use different chart of accounts (BAS, Bokio, custom)
    while the system can still automatically select the correct accounts for bookkeeping.
    """

    __tablename__ = "default_accounts"

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False)

    # The type of default account (e.g., "revenue_25", "vat_outgoing_25")
    account_type = Column(String, nullable=False)

    # The actual account to use for this type
    account_id = Column(Integer, ForeignKey("accounts.id"), nullable=False)

    # Relationships
    company = relationship("Company", back_populates="default_accounts")
    account = relationship("Account")

    # Ensure one mapping per type per company
    __table_args__ = (UniqueConstraint("company_id", "account_type", name="unique_company_account_type"),)

    def __repr__(self):
        return f"<DefaultAccount {self.account_type} -> Account {self.account_id}>"
