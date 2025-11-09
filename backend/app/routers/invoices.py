from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import desc
from typing import List, Optional
from datetime import date, datetime
from decimal import Decimal
from app.database import get_db
from app.models.invoice import Invoice, InvoiceLine, InvoiceStatus
from app.models.customer import Customer
from app.schemas.invoice import (
    InvoiceCreate,
    InvoiceResponse,
    InvoiceUpdate,
    InvoiceListItem,
    MarkPaidRequest
)
from app.services.invoice_service import create_invoice_verification, create_invoice_payment_verification

router = APIRouter()


@router.post("/", response_model=InvoiceResponse, status_code=status.HTTP_201_CREATED)
def create_invoice(invoice_data: InvoiceCreate, db: Session = Depends(get_db)):
    """Create a new outgoing invoice"""

    # Get next invoice number
    last_invoice = db.query(Invoice).filter(
        Invoice.company_id == invoice_data.company_id,
        Invoice.invoice_series == invoice_data.invoice_series
    ).order_by(desc(Invoice.invoice_number)).first()

    next_number = (last_invoice.invoice_number + 1) if last_invoice else 1

    # Calculate totals from lines
    total_net = Decimal("0")
    total_vat = Decimal("0")

    invoice_lines_data = []
    for line_data in invoice_data.invoice_lines:
        net_amount = line_data.quantity * line_data.unit_price
        vat_amount = net_amount * (line_data.vat_rate / 100)
        total_amount = net_amount + vat_amount

        total_net += net_amount
        total_vat += vat_amount

        invoice_lines_data.append({
            **line_data.model_dump(),
            "net_amount": net_amount,
            "vat_amount": vat_amount,
            "total_amount": total_amount
        })

    # Create invoice
    invoice = Invoice(
        company_id=invoice_data.company_id,
        customer_id=invoice_data.customer_id,
        invoice_number=next_number,
        invoice_series=invoice_data.invoice_series,
        invoice_date=invoice_data.invoice_date,
        due_date=invoice_data.due_date,
        reference=invoice_data.reference,
        our_reference=invoice_data.our_reference,
        notes=invoice_data.notes,
        message=invoice_data.message,
        total_amount=total_net + total_vat,
        vat_amount=total_vat,
        net_amount=total_net,
        status=InvoiceStatus.DRAFT
    )
    db.add(invoice)
    db.flush()

    # Create invoice lines
    for line_data in invoice_lines_data:
        invoice_line = InvoiceLine(
            invoice_id=invoice.id,
            **line_data
        )
        db.add(invoice_line)

    db.commit()
    db.refresh(invoice)

    return invoice


@router.get("/", response_model=List[InvoiceListItem])
def list_invoices(
    company_id: int = Query(..., description="Company ID"),
    customer_id: Optional[int] = None,
    status: Optional[InvoiceStatus] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    limit: int = Query(100, le=1000),
    offset: int = 0,
    db: Session = Depends(get_db)
):
    """List invoices with filtering"""
    query = db.query(Invoice, Customer.name.label("customer_name")).join(
        Customer, Invoice.customer_id == Customer.id
    ).filter(Invoice.company_id == company_id)

    if customer_id:
        query = query.filter(Invoice.customer_id == customer_id)
    if status:
        query = query.filter(Invoice.status == status)
    if start_date:
        query = query.filter(Invoice.invoice_date >= start_date)
    if end_date:
        query = query.filter(Invoice.invoice_date <= end_date)

    results = query.order_by(
        desc(Invoice.invoice_date),
        desc(Invoice.invoice_number)
    ).limit(limit).offset(offset).all()

    return [
        InvoiceListItem(
            id=inv.id,
            invoice_number=inv.invoice_number,
            invoice_series=inv.invoice_series,
            invoice_date=inv.invoice_date,
            due_date=inv.due_date,
            customer_id=inv.customer_id,
            customer_name=customer_name,
            total_amount=inv.total_amount,
            status=inv.status,
            paid_amount=inv.paid_amount
        )
        for inv, customer_name in results
    ]


@router.get("/{invoice_id}", response_model=InvoiceResponse)
def get_invoice(invoice_id: int, db: Session = Depends(get_db)):
    """Get a specific invoice"""
    invoice = db.query(Invoice).filter(Invoice.id == invoice_id).first()
    if not invoice:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Invoice {invoice_id} not found"
        )
    return invoice


@router.patch("/{invoice_id}", response_model=InvoiceResponse)
def update_invoice(invoice_id: int, invoice_update: InvoiceUpdate, db: Session = Depends(get_db)):
    """Update an invoice"""
    invoice = db.query(Invoice).filter(Invoice.id == invoice_id).first()
    if not invoice:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Invoice {invoice_id} not found"
        )

    if invoice.status == InvoiceStatus.PAID:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot modify paid invoice"
        )

    update_data = invoice_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(invoice, field, value)

    db.commit()
    db.refresh(invoice)
    return invoice


@router.post("/{invoice_id}/send", response_model=InvoiceResponse)
def send_invoice(invoice_id: int, db: Session = Depends(get_db)):
    """
    Mark invoice as sent and create automatic verification

    Creates accounting entry:
    Debit:  1510 Kundfordringar
    Credit: 3xxx Revenue accounts
    Credit: 26xx VAT accounts
    """
    invoice = db.query(Invoice).filter(Invoice.id == invoice_id).first()
    if not invoice:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Invoice {invoice_id} not found"
        )

    if invoice.status != InvoiceStatus.DRAFT:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invoice is not in draft status"
        )

    # Create verification
    verification = create_invoice_verification(db, invoice)

    # Update invoice
    invoice.status = InvoiceStatus.SENT
    invoice.sent_at = datetime.now()
    invoice.invoice_verification_id = verification.id

    db.commit()
    db.refresh(invoice)

    return invoice


@router.post("/{invoice_id}/mark-paid", response_model=InvoiceResponse)
def mark_invoice_paid(invoice_id: int, payment: MarkPaidRequest, db: Session = Depends(get_db)):
    """
    Mark invoice as paid and create payment verification

    Creates accounting entry:
    Debit:  1930 Bank account
    Credit: 1510 Customer receivables
    """
    invoice = db.query(Invoice).filter(Invoice.id == invoice_id).first()
    if not invoice:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Invoice {invoice_id} not found"
        )

    if invoice.status == InvoiceStatus.PAID:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invoice is already paid"
        )

    # If invoice was draft, send it first
    if invoice.status == InvoiceStatus.DRAFT:
        verification = create_invoice_verification(db, invoice)
        invoice.invoice_verification_id = verification.id

    # Determine payment amount
    paid_amount = payment.paid_amount if payment.paid_amount else (invoice.total_amount - invoice.paid_amount)

    # Create payment verification
    payment_verification = create_invoice_payment_verification(
        db, invoice, payment.paid_date, paid_amount, payment.bank_account_id
    )

    # Update invoice
    invoice.paid_amount += paid_amount
    invoice.paid_date = payment.paid_date
    invoice.payment_verification_id = payment_verification.id

    if invoice.paid_amount >= invoice.total_amount:
        invoice.status = InvoiceStatus.PAID
    else:
        invoice.status = InvoiceStatus.PARTIAL

    db.commit()
    db.refresh(invoice)

    return invoice


@router.delete("/{invoice_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_invoice(invoice_id: int, db: Session = Depends(get_db)):
    """Delete an invoice (only if not sent/paid)"""
    invoice = db.query(Invoice).filter(Invoice.id == invoice_id).first()
    if not invoice:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Invoice {invoice_id} not found"
        )

    if invoice.status not in [InvoiceStatus.DRAFT, InvoiceStatus.CANCELLED]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Can only delete draft or cancelled invoices"
        )

    db.delete(invoice)
    db.commit()
    return None
