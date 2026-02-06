from datetime import date

from pydantic import BaseModel, Field

from app.models.company import AccountingBasis, VATReportingPeriod


class CompanyBase(BaseModel):
    """Base company schema"""

    name: str = Field(..., min_length=1, max_length=200)
    org_number: str = Field(..., pattern=r"^\d{6}-?\d{4}$", description="Swedish org number (XXXXXX-XXXX)")
    address: str | None = None
    postal_code: str | None = None
    city: str | None = None
    phone: str | None = None
    email: str | None = None
    fiscal_year_start: date
    fiscal_year_end: date
    accounting_basis: AccountingBasis = AccountingBasis.ACCRUAL
    vat_reporting_period: VATReportingPeriod = VATReportingPeriod.QUARTERLY
    is_vat_registered: bool = True
    logo_filename: str | None = None


class CompanyCreate(CompanyBase):
    """Schema for creating a company"""

    pass


class CompanyUpdate(BaseModel):
    """Schema for updating a company"""

    name: str | None = None
    address: str | None = None
    postal_code: str | None = None
    city: str | None = None
    phone: str | None = None
    email: str | None = None
    fiscal_year_start: date | None = None
    fiscal_year_end: date | None = None
    accounting_basis: AccountingBasis | None = None
    vat_reporting_period: VATReportingPeriod | None = None
    is_vat_registered: bool | None = None
    logo_filename: str | None = None


class CompanyResponse(CompanyBase):
    """Schema for company response"""

    id: int
    vat_number: str = Field(..., description="Calculated Swedish VAT number (SE + org_number + 01)")

    class Config:
        from_attributes = True
