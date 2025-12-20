from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_active_user, get_user_company_ids, verify_company_access
from app.models.account import Account, AccountType
from app.models.user import User
from app.models.verification import TransactionLine, Verification
from app.schemas.account import AccountBalance, AccountCreate, AccountResponse, AccountUpdate

router = APIRouter()


@router.post("/", response_model=AccountResponse, status_code=status.HTTP_201_CREATED)
def create_account(
    account: AccountCreate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Create a new account"""
    # Verify user has access to this company
    company_ids = get_user_company_ids(current_user, db)
    if account.company_id not in company_ids:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"You don't have access to company {account.company_id}",
        )

    # Check if account number already exists for this fiscal year
    existing = (
        db.query(Account)
        .filter(
            Account.fiscal_year_id == account.fiscal_year_id,
            Account.account_number == account.account_number,
        )
        .first()
    )

    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Account {account.account_number} already exists for this fiscal year",
        )

    # Create account
    db_account = Account(**account.model_dump())
    db_account.current_balance = account.opening_balance
    db.add(db_account)
    db.commit()
    db.refresh(db_account)

    return db_account


@router.get("/", response_model=list[AccountResponse])
def list_accounts(
    company_id: int = Query(..., description="Company ID"),
    fiscal_year_id: int = Query(..., description="Fiscal Year ID"),
    account_type: AccountType | None = None,
    active_only: bool = True,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
    _: None = Depends(verify_company_access),
):
    """List all accounts for a company and fiscal year"""
    query = db.query(Account).filter(
        Account.company_id == company_id,
        Account.fiscal_year_id == fiscal_year_id,
    )

    if account_type:
        query = query.filter(Account.account_type == account_type)

    if active_only:
        query = query.filter(Account.active.is_(True))

    accounts = query.order_by(Account.account_number).all()
    return accounts


@router.get("/balances", response_model=list[AccountBalance])
def get_account_balances(
    company_id: int = Query(..., description="Company ID"),
    fiscal_year_id: int = Query(..., description="Fiscal Year ID"),
    account_type: AccountType | None = None,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
    _: None = Depends(verify_company_access),
):
    """Get account balances for a company and fiscal year"""
    query = db.query(Account).filter(
        Account.company_id == company_id,
        Account.fiscal_year_id == fiscal_year_id,
        Account.active.is_(True),
    )

    if account_type:
        query = query.filter(Account.account_type == account_type)

    accounts = query.order_by(Account.account_number).all()

    return [
        AccountBalance(
            account_number=acc.account_number,
            name=acc.name,
            account_type=acc.account_type,
            opening_balance=acc.opening_balance,
            current_balance=acc.current_balance,
            change=acc.current_balance - acc.opening_balance,
        )
        for acc in accounts
    ]


@router.get("/{account_id}", response_model=AccountResponse)
def get_account(
    account_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Get a specific account"""
    account = db.query(Account).filter(Account.id == account_id).first()
    if not account:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Account {account_id} not found",
        )

    # Verify user has access to this account's company
    company_ids = get_user_company_ids(current_user, db)
    if account.company_id not in company_ids:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have access to this account",
        )

    return account


@router.patch("/{account_id}", response_model=AccountResponse)
def update_account(
    account_id: int,
    account_update: AccountUpdate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Update an account"""
    account = db.query(Account).filter(Account.id == account_id).first()
    if not account:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Account {account_id} not found",
        )

    # Verify user has access to this account's company
    company_ids = get_user_company_ids(current_user, db)
    if account.company_id not in company_ids:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have access to this account",
        )

    # Update fields
    update_data = account_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(account, field, value)

    db.commit()
    db.refresh(account)
    return account


@router.delete("/{account_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_account(
    account_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """
    Delete an account.
    - If account has transactions: returns 400 error (most restrictive - cannot delete)
    - If account is used in posting templates: returns 400 error
    - If account is used as default account: returns 400 error
    - If none of above: deletes account completely

    Note: Accounts with transactions must remain active in the system.
    Manual deactivation can be done via PATCH endpoint if needed in the future.
    """
    account = db.query(Account).filter(Account.id == account_id).first()
    if not account:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Account {account_id} not found",
        )

    # Verify user has access to this account's company
    company_ids = get_user_company_ids(current_user, db)
    if account.company_id not in company_ids:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have access to this account",
        )

    # Check if account has any transaction lines (MOST RESTRICTIVE - check first)
    transaction_count = db.query(TransactionLine).filter(TransactionLine.account_id == account_id).count()

    if transaction_count > 0:
        # Cannot delete - account has transactions
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Kontot kan inte raderas eftersom det har {transaction_count} bokförda transaktioner för detta räkenskapsår. Kontot måste vara tomt för att kunna raderas.",
        )

    # Check if account is used in posting templates
    from app.models.posting_template import PostingTemplate, PostingTemplateLine

    template_line = db.query(PostingTemplateLine).filter(PostingTemplateLine.account_id == account_id).first()

    if template_line:
        # Get template name for better error message
        template = db.query(PostingTemplate).filter(PostingTemplate.id == template_line.template_id).first()
        template_name = template.name if template else "okänd mall"

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Kan inte ta bort konto som används i konteringsmall '{template_name}'. Ta bort eller redigera mallen först.",
        )

    # Check if account is used in default accounts
    from app.models.default_account import DefaultAccount

    default_account = db.query(DefaultAccount).filter(DefaultAccount.account_id == account_id).first()

    if default_account:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Kan inte ta bort konto som används som standardkonto ({default_account.account_type}). Ändra standardkontomappningen först.",
        )

    # Safe to delete - no transactions or default account references
    db.delete(account)
    db.commit()
    return None


# Account Ledger models
class AccountLedgerEntry(BaseModel):
    """Single entry in account ledger"""

    verification_id: int
    verification_number: int
    series: str
    transaction_date: str
    description: str
    debit: float
    credit: float
    balance: float


class AccountLedgerResponse(BaseModel):
    """Account ledger response"""

    account_id: int
    account_number: int
    account_name: str
    opening_balance: float
    closing_balance: float
    entries: list[AccountLedgerEntry]


@router.get("/{account_id}/ledger", response_model=AccountLedgerResponse)
def get_account_ledger(
    account_id: int,
    start_date: date | None = Query(None, description="Start date (YYYY-MM-DD)"),
    end_date: date | None = Query(None, description="End date (YYYY-MM-DD)"),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """
    Get account ledger showing all transactions for a specific account.
    Returns chronological list of all debit/credit entries with running balance.
    """
    # Get account
    account = db.query(Account).filter(Account.id == account_id).first()
    if not account:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Account {account_id} not found",
        )

    # Verify user has access to this account's company
    company_ids = get_user_company_ids(current_user, db)
    if account.company_id not in company_ids:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have access to this account",
        )

    # Get all transaction lines for this account
    query = (
        db.query(TransactionLine, Verification)
        .join(Verification, TransactionLine.verification_id == Verification.id)
        .filter(
            TransactionLine.account_id == account_id,
            Verification.company_id == account.company_id,
        )
    )

    # Apply date filters
    if start_date:
        query = query.filter(Verification.transaction_date >= start_date)
    if end_date:
        query = query.filter(Verification.transaction_date <= end_date)

    # Order by date and verification number
    query = query.order_by(
        Verification.transaction_date.asc(),
        Verification.series.asc(),
        Verification.verification_number.asc(),
    )

    transactions = query.all()

    # Calculate running balance
    running_balance = account.opening_balance
    entries = []

    for trans_line, verification in transactions:
        # Update running balance (debit increases, credit decreases for asset/expense accounts)
        # For liability/revenue accounts, it's opposite, but we show it the same way
        running_balance += trans_line.debit - trans_line.credit

        entries.append(
            AccountLedgerEntry(
                verification_id=verification.id,
                verification_number=verification.verification_number,
                series=verification.series,
                transaction_date=verification.transaction_date.isoformat(),
                description=trans_line.description or verification.description or "",
                debit=float(trans_line.debit),
                credit=float(trans_line.credit),
                balance=float(running_balance),
            )
        )

    return AccountLedgerResponse(
        account_id=account.id,
        account_number=account.account_number,
        account_name=account.name,
        opening_balance=float(account.opening_balance),
        closing_balance=float(running_balance),
        entries=entries,
    )
