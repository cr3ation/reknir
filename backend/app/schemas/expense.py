from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, Field


class ExpenseBase(BaseModel):
    """Base expense schema"""

    employee_name: str = Field(..., min_length=1, max_length=200)
    expense_date: date
    description: str = Field(..., min_length=1, max_length=500)
    amount: Decimal = Field(..., ge=0)
    vat_amount: Decimal = Field(default=Decimal("0"), ge=0)
    expense_account_id: int | None = None
    vat_account_id: int | None = None


class ExpenseCreate(ExpenseBase):
    """Schema for creating an expense"""

    company_id: int


class ExpenseUpdate(BaseModel):
    """Schema for updating an expense"""

    employee_name: str | None = Field(None, min_length=1, max_length=200)
    expense_date: date | None = None
    description: str | None = Field(None, min_length=1, max_length=500)
    amount: Decimal | None = Field(None, ge=0)
    vat_amount: Decimal | None = Field(None, ge=0)
    expense_account_id: int | None = None
    vat_account_id: int | None = None
    status: str | None = None


class ExpenseResponse(ExpenseBase):
    """Schema for expense response"""

    id: int
    company_id: int
    status: str
    approved_date: datetime | None = None
    paid_date: datetime | None = None
    verification_id: int | None = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
