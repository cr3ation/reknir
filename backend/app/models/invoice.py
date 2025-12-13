import enum

from sqlalchemy import Column, Date, DateTime, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base


class InvoiceStatus(str, enum.Enum):
    """Invoice payment status"""

    DRAFT = "draft"  # Not sent yet
    SENT = "sent"  # Sent to customer
    PAID = "paid"  # Fully paid
    PARTIAL = "partial"  # Partially paid
    OVERDUE = "overdue"  # Past due date
    CANCELLED = "cancelled"  # Cancelled/credited


class Invoice(Base):
    """
    Outgoing invoice (Kundfaktura)
    Creates automatic verification on creation and payment
    """

    __tablename__ = "invoices"

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False)
    customer_id = Column(Integer, ForeignKey("customers.id"), nullable=False)

    # Invoice identity
    invoice_number = Column(Integer, nullable=False, index=True)
    invoice_series = Column(String(10), default="F", nullable=False)  # F for Faktura

    # Dates
    invoice_date = Column(Date, nullable=False, index=True)
    due_date = Column(Date, nullable=False)
    paid_date = Column(Date, nullable=True)

    # Reference
    reference = Column(String, nullable=True)  # Customer reference
    our_reference = Column(String, nullable=True)  # Our reference

    # Amounts (calculated from lines)
    total_amount = Column(Numeric(15, 2), nullable=False)  # Including VAT
    vat_amount = Column(Numeric(15, 2), nullable=False)
    net_amount = Column(Numeric(15, 2), nullable=False)  # Excluding VAT

    # Payment
    status = Column(
        SQLEnum(InvoiceStatus, values_callable=lambda x: [e.value for e in x]),
        default=InvoiceStatus.DRAFT,
        nullable=False,
        index=True,
    )
    paid_amount = Column(Numeric(15, 2), default=0, nullable=False)

    # Notes
    notes = Column(Text, nullable=True)  # Internal notes
    message = Column(Text, nullable=True)  # Message to customer on invoice

    # Related verification (created automatically)
    invoice_verification_id = Column(Integer, ForeignKey("verifications.id"), nullable=True)
    payment_verification_id = Column(Integer, ForeignKey("verifications.id"), nullable=True)

    # PDF
    pdf_path = Column(String, nullable=True)

    # Timestamps
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)
    sent_at = Column(DateTime, nullable=True)

    # Relationships
    company = relationship("Company")
    customer = relationship("Customer", back_populates="invoices")
    invoice_lines = relationship("InvoiceLine", back_populates="invoice", cascade="all, delete-orphan")
    invoice_verification = relationship("Verification", foreign_keys=[invoice_verification_id])
    payment_verification = relationship("Verification", foreign_keys=[payment_verification_id])

    def __repr__(self):
        return f"<Invoice {self.invoice_series}{self.invoice_number}>"


class InvoiceLine(Base):
    """
    Invoice line item (Fakturarad)
    """

    __tablename__ = "invoice_lines"

    id = Column(Integer, primary_key=True, index=True)
    invoice_id = Column(Integer, ForeignKey("invoices.id"), nullable=False)

    # Item details
    description = Column(String, nullable=False)
    quantity = Column(Numeric(10, 2), default=1, nullable=False)
    unit = Column(String(20), default="st", nullable=False)  # st, tim, kg, etc.
    unit_price = Column(Numeric(15, 2), nullable=False)

    # VAT
    vat_rate = Column(Numeric(5, 2), nullable=False)  # 25.00, 12.00, 6.00, 0.00

    # Account for revenue
    account_id = Column(Integer, ForeignKey("accounts.id"), nullable=True)  # Which revenue account

    # Calculated fields
    net_amount = Column(Numeric(15, 2), nullable=False)  # quantity * unit_price
    vat_amount = Column(Numeric(15, 2), nullable=False)  # net_amount * vat_rate / 100
    total_amount = Column(Numeric(15, 2), nullable=False)  # net_amount + vat_amount

    # Relationships
    invoice = relationship("Invoice", back_populates="invoice_lines")
    account = relationship("Account")

    def __repr__(self):
        return f"<InvoiceLine {self.description[:30]}>"


class SupplierInvoice(Base):
    """
    Incoming supplier invoice (Leverantörsfaktura)
    Creates automatic verification on registration and payment
    """

    __tablename__ = "supplier_invoices"

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False)
    supplier_id = Column(Integer, ForeignKey("suppliers.id"), nullable=False)

    # Invoice identity (from supplier)
    supplier_invoice_number = Column(String, nullable=False)
    our_invoice_number = Column(Integer, nullable=True, index=True)  # Our internal tracking number

    # Dates
    invoice_date = Column(Date, nullable=False, index=True)
    due_date = Column(Date, nullable=False)
    paid_date = Column(Date, nullable=True)

    # Amounts
    total_amount = Column(Numeric(15, 2), nullable=False)
    vat_amount = Column(Numeric(15, 2), nullable=False)
    net_amount = Column(Numeric(15, 2), nullable=False)

    # Payment
    status = Column(
        SQLEnum(InvoiceStatus, values_callable=lambda x: [e.value for e in x]),
        default=InvoiceStatus.DRAFT,
        nullable=False,
        index=True,
    )
    paid_amount = Column(Numeric(15, 2), default=0, nullable=False)

    # OCR/Reference
    ocr_number = Column(String, nullable=True)
    reference = Column(String, nullable=True)

    # Notes
    notes = Column(Text, nullable=True)

    # Related verifications
    invoice_verification_id = Column(Integer, ForeignKey("verifications.id"), nullable=True)
    payment_verification_id = Column(Integer, ForeignKey("verifications.id"), nullable=True)

    # Attachment
    attachment_path = Column(String, nullable=True)  # PDF/image of invoice

    # Timestamps
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    company = relationship("Company")
    supplier = relationship("Supplier", back_populates="supplier_invoices")
    supplier_invoice_lines = relationship(
        "SupplierInvoiceLine", back_populates="supplier_invoice", cascade="all, delete-orphan"
    )
    invoice_verification = relationship("Verification", foreign_keys=[invoice_verification_id])
    payment_verification = relationship("Verification", foreign_keys=[payment_verification_id])

    def __repr__(self):
        return f"<SupplierInvoice {self.supplier_invoice_number}>"


class SupplierInvoiceLine(Base):
    """
    Supplier invoice line item (Leverantörsfakturarad)
    """

    __tablename__ = "supplier_invoice_lines"

    id = Column(Integer, primary_key=True, index=True)
    supplier_invoice_id = Column(Integer, ForeignKey("supplier_invoices.id"), nullable=False)

    # Item details
    description = Column(String, nullable=False)
    quantity = Column(Numeric(10, 2), default=1, nullable=False)
    unit_price = Column(Numeric(15, 2), nullable=False)

    # VAT
    vat_rate = Column(Numeric(5, 2), nullable=False)

    # Account for expense
    account_id = Column(Integer, ForeignKey("accounts.id"), nullable=True)  # Which expense account

    # Calculated fields
    net_amount = Column(Numeric(15, 2), nullable=False)
    vat_amount = Column(Numeric(15, 2), nullable=False)
    total_amount = Column(Numeric(15, 2), nullable=False)

    # Relationships
    supplier_invoice = relationship("SupplierInvoice", back_populates="supplier_invoice_lines")
    account = relationship("Account")

    def __repr__(self):
        return f"<SupplierInvoiceLine {self.description[:30]}>"
