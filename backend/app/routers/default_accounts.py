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
