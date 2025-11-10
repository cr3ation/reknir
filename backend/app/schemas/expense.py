from pydantic import BaseModel, Field
from typing import Optional
from datetime import date, datetime
from decimal import Decimal


class ExpenseBase(BaseModel):
    """Base expense schema"""
    employee_name: str = Field(..., min_length=1, max_length=200)
    expense_date: date
    description: str = Field(..., min_length=1, max_length=500)
    amount: Decimal = Field(..., ge=0, decimal_places=2)
    vat_amount: Decimal = Field(default=Decimal("0"), ge=0, decimal_places=2)
    expense_account_id: Optional[int] = None
    vat_account_id: Optional[int] = None
    receipt_filename: Optional[str] = None


class ExpenseCreate(ExpenseBase):
    """Schema for creating an expense"""
    company_id: int


class ExpenseUpdate(BaseModel):
    """Schema for updating an expense"""
    employee_name: Optional[str] = Field(None, min_length=1, max_length=200)
    expense_date: Optional[date] = None
    description: Optional[str] = Field(None, min_length=1, max_length=500)
    amount: Optional[Decimal] = Field(None, ge=0, decimal_places=2)
    vat_amount: Optional[Decimal] = Field(None, ge=0, decimal_places=2)
    expense_account_id: Optional[int] = None
    vat_account_id: Optional[int] = None
    receipt_filename: Optional[str] = None
    status: Optional[str] = None


class ExpenseResponse(ExpenseBase):
    """Schema for expense response"""
    id: int
    company_id: int
    status: str
    approved_date: Optional[datetime] = None
    paid_date: Optional[datetime] = None
    verification_id: Optional[int] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
