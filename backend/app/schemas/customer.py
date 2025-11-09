from pydantic import BaseModel, Field, EmailStr
from typing import Optional


class CustomerBase(BaseModel):
    """Base customer schema"""
    name: str = Field(..., min_length=1, max_length=200)
    org_number: Optional[str] = Field(None, max_length=15)
    contact_person: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    postal_code: Optional[str] = Field(None, max_length=10)
    city: Optional[str] = None
    country: str = "Sverige"
    payment_terms_days: int = Field(30, ge=0, le=365)


class CustomerCreate(CustomerBase):
    """Schema for creating a customer"""
    company_id: int


class CustomerUpdate(BaseModel):
    """Schema for updating a customer"""
    name: Optional[str] = None
    org_number: Optional[str] = None
    contact_person: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    postal_code: Optional[str] = None
    city: Optional[str] = None
    country: Optional[str] = None
    payment_terms_days: Optional[int] = None
    active: Optional[bool] = None


class CustomerResponse(CustomerBase):
    """Schema for customer response"""
    id: int
    company_id: int
    active: bool

    class Config:
        from_attributes = True


class SupplierBase(BaseModel):
    """Base supplier schema"""
    name: str = Field(..., min_length=1, max_length=200)
    org_number: Optional[str] = Field(None, max_length=15)
    contact_person: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    postal_code: Optional[str] = Field(None, max_length=10)
    city: Optional[str] = None
    country: str = "Sverige"
    payment_terms_days: int = Field(30, ge=0, le=365)
    bank_account: Optional[str] = None
    bank_name: Optional[str] = None


class SupplierCreate(SupplierBase):
    """Schema for creating a supplier"""
    company_id: int


class SupplierUpdate(BaseModel):
    """Schema for updating a supplier"""
    name: Optional[str] = None
    org_number: Optional[str] = None
    contact_person: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    postal_code: Optional[str] = None
    city: Optional[str] = None
    country: Optional[str] = None
    payment_terms_days: Optional[int] = None
    bank_account: Optional[str] = None
    bank_name: Optional[str] = None
    active: Optional[bool] = None


class SupplierResponse(SupplierBase):
    """Schema for supplier response"""
    id: int
    company_id: int
    active: bool

    class Config:
        from_attributes = True
