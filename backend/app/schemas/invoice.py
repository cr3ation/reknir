from pydantic import BaseModel, Field, field_validator
from datetime import date, datetime
from decimal import Decimal
from typing import List, Optional
from app.models.invoice import InvoiceStatus


class InvoiceLineBase(BaseModel):
    """Base invoice line schema"""
    description: str = Field(..., min_length=1)
    quantity: Decimal = Field(Decimal("1.00"), ge=0)
    unit: str = "st"
    unit_price: Decimal = Field(..., ge=0)
    vat_rate: Decimal = Field(..., ge=0, le=100)  # 0, 6, 12, 25
    account_id: Optional[int] = None


class InvoiceLineCreate(InvoiceLineBase):
    """Schema for creating an invoice line"""
    pass


class InvoiceLineResponse(InvoiceLineBase):
    """Schema for invoice line response"""
    id: int
    invoice_id: int
    net_amount: Decimal
    vat_amount: Decimal
    total_amount: Decimal

    class Config:
        from_attributes = True
        json_encoders = {
            Decimal: float
        }


class InvoiceBase(BaseModel):
    """Base invoice schema"""
    invoice_series: str = Field("F", max_length=10)
    invoice_date: date
    due_date: date
    reference: Optional[str] = None
    our_reference: Optional[str] = None
    notes: Optional[str] = None
    message: Optional[str] = None


class InvoiceCreate(InvoiceBase):
    """Schema for creating an invoice"""
    company_id: int
    customer_id: int
    invoice_lines: List[InvoiceLineCreate] = Field(..., min_length=1)

    @field_validator('invoice_lines')
    @classmethod
    def validate_lines(cls, lines):
        """Ensure at least one line"""
        if not lines:
            raise ValueError("Invoice must have at least one line")
        return lines


class InvoiceUpdate(BaseModel):
    """Schema for updating an invoice"""
    due_date: Optional[date] = None
    reference: Optional[str] = None
    our_reference: Optional[str] = None
    notes: Optional[str] = None
    message: Optional[str] = None
    status: Optional[InvoiceStatus] = None


class InvoiceResponse(InvoiceBase):
    """Schema for invoice response"""
    id: int
    company_id: int
    customer_id: int
    invoice_number: int
    total_amount: Decimal
    vat_amount: Decimal
    net_amount: Decimal
    status: InvoiceStatus
    paid_amount: Decimal
    paid_date: Optional[date]
    invoice_verification_id: Optional[int]
    payment_verification_id: Optional[int]
    pdf_path: Optional[str]
    created_at: datetime
    updated_at: datetime
    sent_at: Optional[datetime]
    invoice_lines: List[InvoiceLineResponse]

    class Config:
        from_attributes = True
        json_encoders = {
            Decimal: float
        }


class InvoiceListItem(BaseModel):
    """Simplified invoice for list views"""
    id: int
    invoice_number: int
    invoice_series: str
    invoice_date: date
    due_date: date
    customer_id: int
    customer_name: str = ""  # Populated from join
    total_amount: Decimal
    status: InvoiceStatus
    paid_amount: Decimal

    class Config:
        from_attributes = True
        json_encoders = {
            Decimal: float
        }


class SupplierInvoiceLineBase(BaseModel):
    """Base supplier invoice line schema"""
    description: str = Field(..., min_length=1)
    quantity: Decimal = Field(Decimal("1.00"), ge=0)
    unit_price: Decimal = Field(..., ge=0)
    vat_rate: Decimal = Field(..., ge=0, le=100)
    account_id: Optional[int] = None


class SupplierInvoiceLineCreate(SupplierInvoiceLineBase):
    """Schema for creating a supplier invoice line"""
    pass


class SupplierInvoiceLineResponse(SupplierInvoiceLineBase):
    """Schema for supplier invoice line response"""
    id: int
    supplier_invoice_id: int
    net_amount: Decimal
    vat_amount: Decimal
    total_amount: Decimal

    class Config:
        from_attributes = True
        json_encoders = {
            Decimal: float
        }


class SupplierInvoiceBase(BaseModel):
    """Base supplier invoice schema"""
    supplier_invoice_number: str
    invoice_date: date
    due_date: date
    ocr_number: Optional[str] = None
    reference: Optional[str] = None
    notes: Optional[str] = None


class SupplierInvoiceCreate(SupplierInvoiceBase):
    """Schema for creating a supplier invoice"""
    company_id: int
    supplier_id: int
    supplier_invoice_lines: List[SupplierInvoiceLineCreate] = Field(..., min_length=1)

    @field_validator('supplier_invoice_lines')
    @classmethod
    def validate_lines(cls, lines):
        """Ensure at least one line"""
        if not lines:
            raise ValueError("Supplier invoice must have at least one line")
        return lines


class SupplierInvoiceUpdate(BaseModel):
    """Schema for updating a supplier invoice"""
    due_date: Optional[date] = None
    ocr_number: Optional[str] = None
    reference: Optional[str] = None
    notes: Optional[str] = None
    status: Optional[InvoiceStatus] = None


class SupplierInvoiceResponse(SupplierInvoiceBase):
    """Schema for supplier invoice response"""
    id: int
    company_id: int
    supplier_id: int
    our_invoice_number: Optional[int]
    total_amount: Decimal
    vat_amount: Decimal
    net_amount: Decimal
    status: InvoiceStatus
    paid_amount: Decimal
    paid_date: Optional[date]
    invoice_verification_id: Optional[int]
    payment_verification_id: Optional[int]
    attachment_path: Optional[str]
    created_at: datetime
    updated_at: datetime
    supplier_invoice_lines: List[SupplierInvoiceLineResponse]

    class Config:
        from_attributes = True
        json_encoders = {
            Decimal: float
        }


class SupplierInvoiceListItem(BaseModel):
    """Simplified supplier invoice for list views"""
    id: int
    our_invoice_number: Optional[int]
    supplier_invoice_number: str
    invoice_date: date
    due_date: date
    supplier_id: int
    supplier_name: str = ""  # Populated from join
    total_amount: Decimal
    status: InvoiceStatus
    paid_amount: Decimal

    class Config:
        from_attributes = True
        json_encoders = {
            Decimal: float
        }


class MarkPaidRequest(BaseModel):
    """Schema for marking invoice as paid"""
    paid_date: date
    paid_amount: Optional[Decimal] = None  # If not provided, uses remaining amount
    bank_account_id: Optional[int] = None  # Which bank account (default: 1930)
