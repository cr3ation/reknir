"""Default Accounts Router"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.default_account import DefaultAccount
from app.models.account import Account
from pydantic import BaseModel
from typing import List

router = APIRouter(prefix="/api/default-accounts", tags=["Default Accounts"])


class DefaultAccountResponse(BaseModel):
    """Response model for default account"""
    id: int
    company_id: int
    account_type: str
    account_id: int
    account_number: int
    account_name: str

    class Config:
        from_attributes = True


@router.get("/", response_model=List[DefaultAccountResponse])
def list_default_accounts(company_id: int, db: Session = Depends(get_db)):
    """List all default account mappings for a company"""
    defaults = db.query(DefaultAccount).filter(
        DefaultAccount.company_id == company_id
    ).all()

    # Enrich with account details
    result = []
    for default in defaults:
        account = db.query(Account).filter(Account.id == default.account_id).first()
        if account:
            result.append(DefaultAccountResponse(
                id=default.id,
                company_id=default.company_id,
                account_type=default.account_type,
                account_id=default.account_id,
                account_number=account.account_number,
                account_name=account.name
            ))

    return result


class DefaultAccountUpdate(BaseModel):
    """Request model for updating a default account"""
    account_id: int


@router.patch("/{default_account_id}", response_model=DefaultAccountResponse)
def update_default_account(
    default_account_id: int,
    update: DefaultAccountUpdate,
    db: Session = Depends(get_db)
):
    """Update a default account mapping"""
    # Find the default account
    default = db.query(DefaultAccount).filter(DefaultAccount.id == default_account_id).first()
    if not default:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Default account {default_account_id} not found"
        )

    # Verify the new account exists and belongs to the same company
    account = db.query(Account).filter(Account.id == update.account_id).first()
    if not account:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Account {update.account_id} not found"
        )

    if account.company_id != default.company_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Account must belong to the same company"
        )

    # Update the default account
    default.account_id = update.account_id
    db.commit()
    db.refresh(default)

    # Return enriched response
    return DefaultAccountResponse(
        id=default.id,
        company_id=default.company_id,
        account_type=default.account_type,
        account_id=default.account_id,
        account_number=account.account_number,
        account_name=account.name
    )
