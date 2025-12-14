from decimal import Decimal

from pydantic import BaseModel, Field

from app.models.account import AccountType


class AccountBase(BaseModel):
    """Base account schema"""

    account_number: int = Field(..., ge=1000, le=8999, description="BAS account number")
    name: str = Field(..., min_length=1, max_length=200)
    description: str | None = None
    account_type: AccountType


class AccountCreate(AccountBase):
    """Schema for creating an account"""

    company_id: int
    opening_balance: Decimal = Decimal("0.00")
    is_bas_account: bool = True


class AccountUpdate(BaseModel):
    """Schema for updating an account"""

    name: str | None = None
    description: str | None = None
    active: bool | None = None


class AccountResponse(AccountBase):
    """Schema for account response"""

    id: int
    company_id: int
    opening_balance: Decimal
    current_balance: Decimal
    active: bool
    is_bas_account: bool

    class Config:
        from_attributes = True
        json_encoders = {Decimal: float}


class AccountBalance(BaseModel):
    """Schema for account balance"""

    account_number: int
    name: str
    account_type: AccountType
    opening_balance: Decimal
    current_balance: Decimal
    change: Decimal

    class Config:
        from_attributes = True
        json_encoders = {Decimal: float}
