"""Service for managing default account mappings"""
from decimal import Decimal
from sqlalchemy.orm import Session
from app.models.account import Account
from app.models.default_account import DefaultAccount, DefaultAccountType
from app.models.fiscal_year import FiscalYear
from datetime import date


def get_default_account(db: Session, company_id: int, fiscal_year_id: int, account_type: str) -> Account | None:
    """
    Get the default account for a given account type in a specific fiscal year.
    Returns None if no default is configured.

    Args:
        db: Database session
        company_id: Company ID
        fiscal_year_id: Fiscal year ID
        account_type: Type of default account (from DefaultAccountType)

    Returns:
        Account object or None if not found
    """
    # Get the default mapping for this company and account type
    default_mapping = db.query(DefaultAccount).filter(
        DefaultAccount.company_id == company_id,
        DefaultAccount.account_type == account_type
    ).first()

    if not default_mapping:
        return None

    # Get the account from the default mapping
    default_account = db.query(Account).filter(Account.id == default_mapping.account_id).first()

    if not default_account:
        return None

    # Find the equivalent account in the specified fiscal year (same account number)
    account = db.query(Account).filter(
        Account.company_id == company_id,
        Account.fiscal_year_id == fiscal_year_id,
        Account.account_number == default_account.account_number
    ).first()

    return account


def set_default_account(db: Session, company_id: int, account_type: str, account_id: int) -> DefaultAccount:
    """
    Set or update a default account mapping.
    """
    # Check if mapping already exists
    existing = db.query(DefaultAccount).filter(
        DefaultAccount.company_id == company_id,
        DefaultAccount.account_type == account_type
    ).first()

    if existing:
        existing.account_id = account_id
        db.commit()
        db.refresh(existing)
        return existing
    else:
        new_mapping = DefaultAccount(
            company_id=company_id,
            account_type=account_type,
            account_id=account_id
        )
        db.add(new_mapping)
        db.commit()
        db.refresh(new_mapping)
        return new_mapping


def initialize_default_accounts_from_existing(db: Session, company_id: int, fiscal_year_id: int) -> None:
    """
    Initialize default account mappings based on existing accounts in a fiscal year.
    This is useful when importing SIE4 or setting up a new company.

    Tries to detect standard BAS accounts first, then falls back to searching by account number ranges.

    Args:
        db: Database session
        company_id: Company ID
        fiscal_year_id: Fiscal year ID to search for accounts in
    """
    # Map of account types to their common account numbers (BAS 2024 and Bokio variants)
    account_mapping = {
        # Revenue accounts by VAT rate
        DefaultAccountType.REVENUE_25: [3001, 3011],  # BAS uses 3001, some use 3011
        DefaultAccountType.REVENUE_12: [3002, 3012],
        DefaultAccountType.REVENUE_6: [3003, 3013],
        DefaultAccountType.REVENUE_0: [3106],  # Export sales

        # VAT accounts
        DefaultAccountType.VAT_OUTGOING_25: [2611, 2630],
        DefaultAccountType.VAT_OUTGOING_12: [2612, 2631],
        DefaultAccountType.VAT_OUTGOING_6: [2613, 2632],
        DefaultAccountType.VAT_INCOMING_25: [2641, 2645],
        DefaultAccountType.VAT_INCOMING_12: [2642, 2646],
        DefaultAccountType.VAT_INCOMING_6: [2643, 2647],

        # Receivables/Payables
        DefaultAccountType.ACCOUNTS_RECEIVABLE: [1510, 1500],
        DefaultAccountType.ACCOUNTS_PAYABLE: [2440, 2441],

        # Default expense
        DefaultAccountType.EXPENSE_DEFAULT: [6570, 6540],
    }

    for account_type, possible_numbers in account_mapping.items():
        # Try to find an account with one of the possible numbers in this fiscal year
        for account_number in possible_numbers:
            account = db.query(Account).filter(
                Account.company_id == company_id,
                Account.fiscal_year_id == fiscal_year_id,
                Account.account_number == account_number
            ).first()

            if account:
                # Set this as the default
                set_default_account(db, company_id, account_type, account.id)
                break


def get_revenue_account_for_vat_rate(db: Session, company_id: int, fiscal_year_id: int, vat_rate: Decimal) -> Account | None:
    """
    Get the revenue account for a given VAT rate in a specific fiscal year.
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


def get_vat_outgoing_account_for_rate(db: Session, company_id: int, fiscal_year_id: int, vat_rate: Decimal) -> Account | None:
    """
    Get the outgoing VAT account for a given VAT rate in a specific fiscal year.
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


def get_vat_incoming_account_for_rate(db: Session, company_id: int, fiscal_year_id: int, vat_rate: Decimal) -> Account | None:
    """
    Get the incoming VAT account for a given VAT rate in a specific fiscal year.
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
