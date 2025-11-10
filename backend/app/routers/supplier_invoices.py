from fastapi import APIRouter, Depends, HTTPException, status, Query, UploadFile, File
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from sqlalchemy import desc
from typing import List, Optional
from datetime import date
from decimal import Decimal
from pathlib import Path
import shutil
import uuid
from app.database import get_db
from app.models.invoice import SupplierInvoice, SupplierInvoiceLine, InvoiceStatus
from app.models.customer import Supplier
from app.schemas.invoice import (
    SupplierInvoiceCreate,
    SupplierInvoiceResponse,
    SupplierInvoiceUpdate,
    SupplierInvoiceListItem,
    MarkPaidRequest
)
from app.services.invoice_service import create_supplier_invoice_verification, create_supplier_invoice_payment_verification

router = APIRouter()

# Create invoices directory if it doesn't exist
INVOICES_DIR = Path("/app/invoices")
INVOICES_DIR.mkdir(exist_ok=True)


@router.post("/", response_model=SupplierInvoiceResponse, status_code=status.HTTP_201_CREATED)
def create_supplier_invoice(invoice_data: SupplierInvoiceCreate, db: Session = Depends(get_db)):
    """Create a new supplier invoice (register incoming invoice)"""

    # Get next internal tracking number
    last_invoice = db.query(SupplierInvoice).filter(
        SupplierInvoice.company_id == invoice_data.company_id
    ).order_by(desc(SupplierInvoice.our_invoice_number)).first()

    next_number = (last_invoice.our_invoice_number + 1) if last_invoice and last_invoice.our_invoice_number else 1

    # Calculate totals from lines
    total_net = Decimal("0")
    total_vat = Decimal("0")

    invoice_lines_data = []
    for line_data in invoice_data.supplier_invoice_lines:
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

    # Create supplier invoice
    invoice = SupplierInvoice(
        company_id=invoice_data.company_id,
        supplier_id=invoice_data.supplier_id,
        supplier_invoice_number=invoice_data.supplier_invoice_number,
        our_invoice_number=next_number,
        invoice_date=invoice_data.invoice_date,
        due_date=invoice_data.due_date,
        ocr_number=invoice_data.ocr_number,
        reference=invoice_data.reference,
        notes=invoice_data.notes,
        total_amount=total_net + total_vat,
        vat_amount=total_vat,
        net_amount=total_net,
        status=InvoiceStatus.DRAFT
    )
    db.add(invoice)
    db.flush()

    # Create invoice lines
    for line_data in invoice_lines_data:
        invoice_line = SupplierInvoiceLine(
            supplier_invoice_id=invoice.id,
            **line_data
        )
        db.add(invoice_line)

    db.commit()
    db.refresh(invoice)

    return invoice


@router.get("/", response_model=List[SupplierInvoiceListItem])
def list_supplier_invoices(
    company_id: int = Query(..., description="Company ID"),
    supplier_id: Optional[int] = None,
    status: Optional[InvoiceStatus] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    limit: int = Query(100, le=1000),
    offset: int = 0,
    db: Session = Depends(get_db)
):
    """List supplier invoices with filtering"""
    query = db.query(SupplierInvoice, Supplier.name.label("supplier_name")).join(
        Supplier, SupplierInvoice.supplier_id == Supplier.id
    ).filter(SupplierInvoice.company_id == company_id)

    if supplier_id:
        query = query.filter(SupplierInvoice.supplier_id == supplier_id)
    if status:
        query = query.filter(SupplierInvoice.status == status)
    if start_date:
        query = query.filter(SupplierInvoice.invoice_date >= start_date)
    if end_date:
        query = query.filter(SupplierInvoice.invoice_date <= end_date)

    results = query.order_by(
        desc(SupplierInvoice.invoice_date),
        desc(SupplierInvoice.our_invoice_number)
    ).limit(limit).offset(offset).all()

    return [
        SupplierInvoiceListItem(
            id=inv.id,
            our_invoice_number=inv.our_invoice_number,
            supplier_invoice_number=inv.supplier_invoice_number,
            invoice_date=inv.invoice_date,
            due_date=inv.due_date,
            supplier_id=inv.supplier_id,
            supplier_name=supplier_name,
            total_amount=inv.total_amount,
            status=inv.status,
            paid_amount=inv.paid_amount
        )
        for inv, supplier_name in results
    ]


@router.get("/{invoice_id}", response_model=SupplierInvoiceResponse)
def get_supplier_invoice(invoice_id: int, db: Session = Depends(get_db)):
    """Get a specific supplier invoice"""
    invoice = db.query(SupplierInvoice).filter(SupplierInvoice.id == invoice_id).first()
    if not invoice:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Supplier invoice {invoice_id} not found"
        )
    return invoice


@router.patch("/{invoice_id}", response_model=SupplierInvoiceResponse)
def update_supplier_invoice(invoice_id: int, invoice_update: SupplierInvoiceUpdate, db: Session = Depends(get_db)):
    """Update a supplier invoice"""
    invoice = db.query(SupplierInvoice).filter(SupplierInvoice.id == invoice_id).first()
    if not invoice:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Supplier invoice {invoice_id} not found"
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


@router.post("/{invoice_id}/register", response_model=SupplierInvoiceResponse)
def register_supplier_invoice(invoice_id: int, db: Session = Depends(get_db)):
    """
    Register/post supplier invoice and create automatic verification

    Creates accounting entry:
    Debit:  6xxx Expense accounts
    Debit:  2640 Ingående moms (input VAT)
    Credit: 2440 Leverantörsskulder (accounts payable)
    """
    invoice = db.query(SupplierInvoice).filter(SupplierInvoice.id == invoice_id).first()
    if not invoice:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Supplier invoice {invoice_id} not found"
        )

    if invoice.status != InvoiceStatus.DRAFT:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invoice is not in draft status"
        )

    # Create verification
    verification = create_supplier_invoice_verification(db, invoice)

    # Update invoice
    invoice.status = InvoiceStatus.SENT  # Registered/posted
    invoice.invoice_verification_id = verification.id

    db.commit()
    db.refresh(invoice)

    return invoice


@router.post("/{invoice_id}/mark-paid", response_model=SupplierInvoiceResponse)
def mark_supplier_invoice_paid(invoice_id: int, payment: MarkPaidRequest, db: Session = Depends(get_db)):
    """
    Mark supplier invoice as paid and create payment verification

    Creates accounting entry:
    Debit:  2440 Accounts payable
    Credit: 1930 Bank account
    """
    invoice = db.query(SupplierInvoice).filter(SupplierInvoice.id == invoice_id).first()
    if not invoice:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Supplier invoice {invoice_id} not found"
        )

    if invoice.status == InvoiceStatus.PAID:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invoice is already paid"
        )

    # If invoice was draft, register it first
    if invoice.status == InvoiceStatus.DRAFT:
        verification = create_supplier_invoice_verification(db, invoice)
        invoice.invoice_verification_id = verification.id

    # Determine payment amount
    paid_amount = payment.paid_amount if payment.paid_amount else (invoice.total_amount - invoice.paid_amount)

    # Create payment verification
    payment_verification = create_supplier_invoice_payment_verification(
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
def delete_supplier_invoice(invoice_id: int, db: Session = Depends(get_db)):
    """Delete a supplier invoice (only if not registered/paid)"""
    invoice = db.query(SupplierInvoice).filter(SupplierInvoice.id == invoice_id).first()
    if not invoice:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Supplier invoice {invoice_id} not found"
        )

    if invoice.status not in [InvoiceStatus.DRAFT, InvoiceStatus.CANCELLED]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Can only delete draft or cancelled invoices"
        )

    db.delete(invoice)
    db.commit()
    return None


@router.post("/{invoice_id}/upload-attachment", response_model=SupplierInvoiceResponse)
async def upload_attachment(
    invoice_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """Upload an attachment file for a supplier invoice"""
    invoice = db.query(SupplierInvoice).filter(SupplierInvoice.id == invoice_id).first()
    if not invoice:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Supplier invoice {invoice_id} not found"
        )

    # Validate file type (images and PDFs)
    allowed_extensions = {'.jpg', '.jpeg', '.png', '.pdf', '.gif'}
    file_ext = Path(file.filename).suffix.lower()
    if file_ext not in allowed_extensions:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File type {file_ext} not allowed. Allowed types: {', '.join(allowed_extensions)}"
        )

    # Delete old attachment if exists
    if invoice.attachment_path:
        old_path = INVOICES_DIR / invoice.attachment_path
        if old_path.exists():
            old_path.unlink()

    # Generate unique filename
    unique_filename = f"{uuid.uuid4()}{file_ext}"
    file_path = INVOICES_DIR / unique_filename

    # Save file
    with file_path.open("wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    # Update invoice record
    invoice.attachment_path = unique_filename
    db.commit()
    db.refresh(invoice)

    return invoice


@router.get("/{invoice_id}/attachment")
async def download_attachment(invoice_id: int, db: Session = Depends(get_db)):
    """Download the attachment file for a supplier invoice"""
    invoice = db.query(SupplierInvoice).filter(SupplierInvoice.id == invoice_id).first()
    if not invoice:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Supplier invoice {invoice_id} not found"
        )

    if not invoice.attachment_path:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No attachment file found for this invoice"
        )

    file_path = INVOICES_DIR / invoice.attachment_path
    if not file_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Attachment file not found on disk"
        )

    return FileResponse(
        path=str(file_path),
        filename=invoice.attachment_path,
        media_type="application/octet-stream"
    )


@router.delete("/{invoice_id}/attachment", response_model=SupplierInvoiceResponse)
async def delete_attachment(invoice_id: int, db: Session = Depends(get_db)):
    """Delete the attachment file for a supplier invoice"""
    invoice = db.query(SupplierInvoice).filter(SupplierInvoice.id == invoice_id).first()
    if not invoice:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Supplier invoice {invoice_id} not found"
        )

    if not invoice.attachment_path:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No attachment file found for this invoice"
        )

    # Delete file from disk
    file_path = INVOICES_DIR / invoice.attachment_path
    if file_path.exists():
        file_path.unlink()

    # Clear filename from database
    invoice.attachment_path = None
    db.commit()
    db.refresh(invoice)

    return invoice
