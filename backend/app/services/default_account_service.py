"""Service for managing default account mappings"""

from decimal import Decimal

from sqlalchemy.orm import Session

from app.models.account import Account
from app.models.default_account import DefaultAccount, DefaultAccountType


def get_default_account(db: Session, company_id: int, fiscal_year_id: int, account_type: str) -> Account | None:
    """
    Get the default account for a given account type.
    Returns None if no default is configured.
    """
    default_mapping = (
        db.query(DefaultAccount)
        .filter(DefaultAccount.company_id == company_id, DefaultAccount.account_type == account_type)
        .first()
    )

    if not default_mapping:
        return None

    # Get the stored account to find its account_number
    stored_account = db.query(Account).filter(Account.id == default_mapping.account_id).first()
    if not stored_account:
        return None

    # Find the account with the same number in the target fiscal year
    return (
        db.query(Account)
        .filter(
            Account.company_id == company_id,
            Account.fiscal_year_id == fiscal_year_id,
            Account.account_number == stored_account.account_number,
        )
        .first()
    )


def set_default_account(db: Session, company_id: int, account_type: str, account_id: int) -> DefaultAccount:
    """
    Set or update a default account mapping.
    """
    # Check if mapping already exists
    existing = (
        db.query(DefaultAccount)
        .filter(DefaultAccount.company_id == company_id, DefaultAccount.account_type == account_type)
        .first()
    )

    if existing:
        existing.account_id = account_id
        db.commit()
        db.refresh(existing)
        return existing
    else:
        new_mapping = DefaultAccount(company_id=company_id, account_type=account_type, account_id=account_id)
        db.add(new_mapping)
        db.commit()
        db.refresh(new_mapping)
        return new_mapping


def _year_result_equity_candidates(db: Session, company_id: int) -> list[int]:
    """
    Candidate accounts for the balance sheet side of the year result (Årets resultat).

    A sole trader closes the result against the owner's equity (2019), everyone else
    against 2099. The order matters because the first account that exists wins, so a
    chart containing both must still map to the one matching the company form.
    """
    from app.models.company import Company, CompanyForm

    company = db.query(Company).filter(Company.id == company_id).first()
    if company and company.company_form == CompanyForm.SOLE_TRADER:
        return [2019, 2099]
    return [2099, 2019]


def initialize_default_accounts_from_existing(db: Session, company_id: int, fiscal_year_id: int) -> None:
    """
    Initialize default account mappings based on existing accounts.
    This is useful when importing SIE4 or setting up a new company.

    Tries to detect standard BAS accounts first, then falls back to searching by account number ranges.
    """
    # Map of account types to their common account numbers (BAS 2024 and Bokio variants)
    account_mapping = {
        # Revenue accounts by VAT rate
        DefaultAccountType.REVENUE_25: [3001, 3011],  # BAS uses 3001, some use 3011
        DefaultAccountType.REVENUE_12: [3002, 3012],
        DefaultAccountType.REVENUE_6: [3003, 3013],
        DefaultAccountType.REVENUE_0: [3106],  # Export sales
        # VAT accounts
        DefaultAccountType.VAT_OUTGOING_25: [2611, 2610],
        DefaultAccountType.VAT_OUTGOING_12: [2621, 2612],
        DefaultAccountType.VAT_OUTGOING_6: [2631, 2613],
        DefaultAccountType.VAT_INCOMING_25: [2640],
        DefaultAccountType.VAT_INCOMING_12: [2640],
        DefaultAccountType.VAT_INCOMING_6: [2640],
        # Receivables/Payables
        DefaultAccountType.ACCOUNTS_RECEIVABLE: [1510, 1500],
        DefaultAccountType.ACCOUNTS_PAYABLE: [2440, 2441],
        # Default expense
        DefaultAccountType.EXPENSE_DEFAULT: [6570, 6540],
        # Liquid assets
        DefaultAccountType.BANK: [1930, 1920],
        DefaultAccountType.CASH: [1910],
        # Year-end closing: inventory
        DefaultAccountType.INVENTORY_STOCK: [1460, 1410, 1440],
        DefaultAccountType.INVENTORY_CHANGE: [4990, 4960],
        # Year-end closing: accruals. BAS groups both directions on the same interim
        # accounts, so the asset pair and the liability pair share a number each.
        DefaultAccountType.PREPAID_EXPENSE: [1790, 1710],
        DefaultAccountType.ACCRUED_REVENUE: [1790, 1760],
        DefaultAccountType.ACCRUED_EXPENSE: [2990, 2910],
        DefaultAccountType.PREPAID_REVENUE: [2990, 2970],
        # Year-end closing: tax
        DefaultAccountType.TAX_EXPENSE: [8910],
        DefaultAccountType.TAX_LIABILITY: [2510, 2512],
        # Year-end closing: the result itself
        DefaultAccountType.YEAR_RESULT_EXPENSE: [8999],
        DefaultAccountType.YEAR_RESULT_EQUITY: _year_result_equity_candidates(db, company_id),
    }

    for account_type, possible_numbers in account_mapping.items():
        # Try to find an account with one of the possible numbers
        for account_number in possible_numbers:
            account = (
                db.query(Account)
                .filter(
                    Account.company_id == company_id,
                    Account.fiscal_year_id == fiscal_year_id,
                    Account.account_number == account_number,
                )
                .first()
            )

            if account:
                # Set this as the default
                set_default_account(db, company_id, account_type, account.id)
                break


def get_revenue_account_for_vat_rate(
    db: Session, company_id: int, fiscal_year_id: int, vat_rate: Decimal
) -> Account | None:
    """
    Get the revenue account for a given VAT rate.
    Returns None if no default is configured.
    """
    vat_rate_float = float(vat_rate)

    if vat_rate_float == 25.0:
        return get_default_account(db, company_id, fiscal_year_id, DefaultAccountType.REVENUE_25)
    elif vat_rate_float == 12.0:
        return get_default_account(db, company_id, fiscal_year_id, DefaultAccountType.REVENUE_12)
    elif vat_rate_float == 6.0:
        return get_default_account(db, company_id, fiscal_year_id, DefaultAccountType.REVENUE_6)
    else:
        return get_default_account(db, company_id, fiscal_year_id, DefaultAccountType.REVENUE_0)


def get_vat_outgoing_account_for_rate(
    db: Session, company_id: int, fiscal_year_id: int, vat_rate: Decimal
) -> Account | None:
    """
    Get the outgoing VAT account for a given VAT rate.
    Returns None if no default is configured.
    """
    vat_rate_float = float(vat_rate)

    if vat_rate_float == 25.0:
        return get_default_account(db, company_id, fiscal_year_id, DefaultAccountType.VAT_OUTGOING_25)
    elif vat_rate_float == 12.0:
        return get_default_account(db, company_id, fiscal_year_id, DefaultAccountType.VAT_OUTGOING_12)
    elif vat_rate_float == 6.0:
        return get_default_account(db, company_id, fiscal_year_id, DefaultAccountType.VAT_OUTGOING_6)
    else:
        return None


def get_vat_incoming_account_for_rate(
    db: Session, company_id: int, fiscal_year_id: int, vat_rate: Decimal
) -> Account | None:
    """
    Get the incoming VAT account for a given VAT rate.
    Returns None if no default is configured.
    """
    vat_rate_float = float(vat_rate)

    if vat_rate_float == 25.0:
        return get_default_account(db, company_id, fiscal_year_id, DefaultAccountType.VAT_INCOMING_25)
    elif vat_rate_float == 12.0:
        return get_default_account(db, company_id, fiscal_year_id, DefaultAccountType.VAT_INCOMING_12)
    elif vat_rate_float == 6.0:
        return get_default_account(db, company_id, fiscal_year_id, DefaultAccountType.VAT_INCOMING_6)
    else:
        return None
