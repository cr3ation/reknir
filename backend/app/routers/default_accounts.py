"""Default Accounts Router"""

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_active_user, get_user_company_ids
from app.models.account import Account
from app.models.default_account import DefaultAccount
from app.models.user import User

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


@router.get("/", response_model=list[DefaultAccountResponse])
def list_default_accounts(
    company_id: int, current_user: User = Depends(get_current_active_user), db: Session = Depends(get_db)
):
    """List all default account mappings for a company"""
    # Verify access
    company_ids = get_user_company_ids(current_user, db)
    if company_id not in company_ids:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You don't have access to this company")

    defaults = db.query(DefaultAccount).filter(DefaultAccount.company_id == company_id).all()

    # Enrich with account details
    result = []
    for default in defaults:
        account = db.query(Account).filter(Account.id == default.account_id).first()
        if account:
            result.append(
                DefaultAccountResponse(
                    id=default.id,
                    company_id=default.company_id,
                    account_type=default.account_type,
                    account_id=default.account_id,
                    account_number=account.account_number,
                    account_name=account.name,
                )
            )

    return result
