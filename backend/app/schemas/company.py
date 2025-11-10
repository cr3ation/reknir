from pydantic import BaseModel, Field
from datetime import date
from typing import Optional
from app.models.company import AccountingBasis, VATReportingPeriod


class CompanyBase(BaseModel):
    """Base company schema"""
    name: str = Field(..., min_length=1, max_length=200)
    org_number: str = Field(..., pattern=r'^\d{6}-?\d{4}$', description="Swedish org number (XXXXXX-XXXX)")
    fiscal_year_start: date
    fiscal_year_end: date
    accounting_basis: AccountingBasis = AccountingBasis.ACCRUAL
    vat_reporting_period: VATReportingPeriod = VATReportingPeriod.QUARTERLY


class CompanyCreate(CompanyBase):
    """Schema for creating a company"""
    pass


class CompanyUpdate(BaseModel):
    """Schema for updating a company"""
    name: Optional[str] = None
    fiscal_year_start: Optional[date] = None
    fiscal_year_end: Optional[date] = None
    accounting_basis: Optional[AccountingBasis] = None
    vat_reporting_period: Optional[VATReportingPeriod] = None


class CompanyResponse(CompanyBase):
    """Schema for company response"""
    id: int

    class Config:
        from_attributes = True
