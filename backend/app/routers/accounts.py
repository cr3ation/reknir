from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import date
from app.database import get_db
from app.models.account import Account, AccountType
from app.models.verification import Verification, TransactionLine
from app.schemas.account import AccountCreate, AccountResponse, AccountUpdate, AccountBalance
from pydantic import BaseModel

router = APIRouter()


@router.post("/", response_model=AccountResponse, status_code=status.HTTP_201_CREATED)
def create_account(account: AccountCreate, db: Session = Depends(get_db)):
    """Create a new account"""

    # Check if account number already exists for this company
    existing = db.query(Account).filter(
        Account.company_id == account.company_id,
        Account.account_number == account.account_number
    ).first()

    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Account {account.account_number} already exists for this company"
        )

    # Create account
    db_account = Account(**account.model_dump())
    db_account.current_balance = account.opening_balance
    db.add(db_account)
    db.commit()
    db.refresh(db_account)

    return db_account


@router.get("/", response_model=List[AccountResponse])
def list_accounts(
    company_id: int = Query(..., description="Company ID"),
    account_type: Optional[AccountType] = None,
    active_only: bool = True,
    db: Session = Depends(get_db)
):
    """List all accounts for a company"""
    query = db.query(Account).filter(Account.company_id == company_id)

    if account_type:
        query = query.filter(Account.account_type == account_type)

    if active_only:
        query = query.filter(Account.active == True)

    accounts = query.order_by(Account.account_number).all()
    return accounts


@router.get("/balances", response_model=List[AccountBalance])
def get_account_balances(
    company_id: int = Query(..., description="Company ID"),
    account_type: Optional[AccountType] = None,
    db: Session = Depends(get_db)
):
    """Get account balances"""
    query = db.query(Account).filter(
        Account.company_id == company_id,
        Account.active == True
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
            change=acc.current_balance - acc.opening_balance
        )
        for acc in accounts
    ]


@router.get("/{account_id}", response_model=AccountResponse)
def get_account(account_id: int, db: Session = Depends(get_db)):
    """Get a specific account"""
    account = db.query(Account).filter(Account.id == account_id).first()
    if not account:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Account {account_id} not found"
        )
    return account


@router.patch("/{account_id}", response_model=AccountResponse)
def update_account(account_id: int, account_update: AccountUpdate, db: Session = Depends(get_db)):
    """Update an account"""
    account = db.query(Account).filter(Account.id == account_id).first()
    if not account:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Account {account_id} not found"
        )

    # Update fields
    update_data = account_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(account, field, value)

    db.commit()
    db.refresh(account)
    return account


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
    entries: List[AccountLedgerEntry]


@router.get("/{account_id}/ledger", response_model=AccountLedgerResponse)
def get_account_ledger(
    account_id: int,
    start_date: Optional[date] = Query(None, description="Start date (YYYY-MM-DD)"),
    end_date: Optional[date] = Query(None, description="End date (YYYY-MM-DD)"),
    db: Session = Depends(get_db)
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
            detail=f"Account {account_id} not found"
        )

    # Get all transaction lines for this account
    query = db.query(TransactionLine, Verification).join(
        Verification, TransactionLine.verification_id == Verification.id
    ).filter(
        TransactionLine.account_id == account_id,
        Verification.company_id == account.company_id
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
        Verification.verification_number.asc()
    )

    transactions = query.all()

    # Calculate running balance
    running_balance = account.opening_balance
    entries = []

    for trans_line, verification in transactions:
        # Update running balance (debit increases, credit decreases for asset/expense accounts)
        # For liability/revenue accounts, it's opposite, but we show it the same way
        running_balance += trans_line.debit - trans_line.credit

        entries.append(AccountLedgerEntry(
            verification_id=verification.id,
            verification_number=verification.verification_number,
            series=verification.series,
            transaction_date=verification.transaction_date.isoformat(),
            description=trans_line.description or verification.description or "",
            debit=float(trans_line.debit),
            credit=float(trans_line.credit),
            balance=float(running_balance)
        ))

    return AccountLedgerResponse(
        account_id=account.id,
        account_number=account.account_number,
        account_name=account.name,
        opening_balance=float(account.opening_balance),
        closing_balance=float(running_balance),
        entries=entries
    )
