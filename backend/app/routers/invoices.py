import hashlib
import uuid
from datetime import date, datetime
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import FileResponse, Response
from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_active_user, verify_company_access
from app.models.attachment import Attachment, AttachmentLink, AttachmentRole, AttachmentStatus, EntityType
from app.services.attachment_service import ATTACHMENTS_DIR
from app.models.company import AccountingBasis, Company
from app.models.customer import Customer
from app.models.fiscal_year import FiscalYear
from app.models.invoice import Invoice, InvoiceLine, InvoicePayment, InvoiceStatus, PaymentStatus
from app.models.user import User
from app.schemas.attachment import AttachmentLinkCreate, EntityAttachmentItem
from app.schemas.invoice import InvoiceCreate, InvoiceListItem, InvoiceResponse, InvoiceUpdate, MarkPaidRequest
from app.services.invoice_service import create_invoice_payment_verification, create_invoice_verification
from app.services.pdf_service import generate_invoice_pdf

router = APIRouter()


def get_archived_pdf_attachment(db: Session, invoice_id: int) -> Attachment | None:
    """Get archived PDF for an invoice via AttachmentLink."""
    link = (
        db.query(AttachmentLink)
        .filter(
            AttachmentLink.entity_type == EntityType.INVOICE,
            AttachmentLink.entity_id == invoice_id,
            AttachmentLink.role == AttachmentRole.ARCHIVED_PDF,
        )
        .first()
    )
    if link:
        return db.query(Attachment).filter(Attachment.id == link.attachment_id).first()
    return None


@router.post("/", response_model=InvoiceResponse, status_code=status.HTTP_201_CREATED)
async def create_invoice(
    invoice_data: InvoiceCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)
):
    """Create a new outgoing invoice"""
    # Verify user has access to this company
    await verify_company_access(invoice_data.company_id, current_user, db)

    # Get next invoice number
    last_invoice = (
        db.query(Invoice)
        .filter(Invoice.company_id == invoice_data.company_id, Invoice.invoice_series == invoice_data.invoice_series)
        .order_by(desc(Invoice.invoice_number))
        .first()
    )

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

        invoice_lines_data.append(
            {**line_data.model_dump(), "net_amount": net_amount, "vat_amount": vat_amount, "total_amount": total_amount}
        )

    # Get company for payment info snapshot
    company = db.query(Company).filter(Company.id == invoice_data.company_id).first()

    # Validate that company has payment information configured
    if not company or not company.payment_type:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Betalningsuppgifter saknas. Ange betalningstyp i företagsinställningarna innan du skapar fakturor.",
        )

    # Validate that required fields for the payment type are configured
    from app.models.company import PaymentType

    if company.payment_type == PaymentType.BANKGIRO and not company.bankgiro_number:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Bankgironummer saknas. Ange bankgironummer i företagsinställningarna.",
        )
    elif company.payment_type == PaymentType.PLUSGIRO and not company.plusgiro_number:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Plusgironummer saknas. Ange plusgironummer i företagsinställningarna.",
        )
    elif company.payment_type == PaymentType.BANK_ACCOUNT and (not company.clearing_number or not company.account_number):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Clearingnummer och kontonummer saknas. Ange båda i företagsinställningarna.",
        )

    # Create invoice (with payment info snapshot from company)
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
        status=InvoiceStatus.DRAFT,
        payment_type=company.payment_type,
        bankgiro_number=company.bankgiro_number,
        plusgiro_number=company.plusgiro_number,
        clearing_number=company.clearing_number,
        account_number=company.account_number,
        iban=company.iban,
        bic=company.bic,
    )
    db.add(invoice)
    db.flush()

    # Create invoice lines
    for line_data in invoice_lines_data:
        invoice_line = InvoiceLine(invoice_id=invoice.id, **line_data)
        db.add(invoice_line)

    db.commit()
    db.refresh(invoice)

    return invoice


@router.get("/", response_model=list[InvoiceListItem])
async def list_invoices(
    company_id: int = Query(..., description="Company ID"),
    fiscal_year_id: int | None = Query(None, description="Filter by fiscal year"),
    customer_id: int | None = None,
    status: InvoiceStatus | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
    limit: int = Query(100, le=1000),
    offset: int = 0,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """List invoices with filtering"""
    # Verify user has access to this company
    await verify_company_access(company_id, current_user, db)

    query = (
        db.query(Invoice, Customer.name.label("customer_name"))
        .join(Customer, Invoice.customer_id == Customer.id)
        .filter(Invoice.company_id == company_id)
    )

    # Filter by fiscal year date range
    if fiscal_year_id:
        fiscal_year = db.query(FiscalYear).filter(FiscalYear.id == fiscal_year_id).first()
        if fiscal_year:
            query = query.filter(Invoice.invoice_date >= fiscal_year.start_date)
            query = query.filter(Invoice.invoice_date <= fiscal_year.end_date)

    if customer_id:
        query = query.filter(Invoice.customer_id == customer_id)
    if status:
        query = query.filter(Invoice.status == status)
    if start_date:
        query = query.filter(Invoice.invoice_date >= start_date)
    if end_date:
        query = query.filter(Invoice.invoice_date <= end_date)

    results = query.order_by(desc(Invoice.invoice_date), desc(Invoice.invoice_number)).limit(limit).offset(offset).all()

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
            payment_status=inv.payment_status,
            paid_amount=inv.paid_amount,
        )
        for inv, customer_name in results
    ]


@router.get("/{invoice_id}", response_model=InvoiceResponse)
async def get_invoice(
    invoice_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)
):
    """Get a specific invoice"""
    invoice = db.query(Invoice).filter(Invoice.id == invoice_id).first()
    if not invoice:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Invoice {invoice_id} not found")

    # Verify user has access to this company
    await verify_company_access(invoice.company_id, current_user, db)

    return invoice


@router.patch("/{invoice_id}", response_model=InvoiceResponse)
async def update_invoice(
    invoice_id: int,
    invoice_update: InvoiceUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Update an invoice"""
    invoice = db.query(Invoice).filter(Invoice.id == invoice_id).first()
    if not invoice:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Invoice {invoice_id} not found")

    # Verify user has access to this company
    await verify_company_access(invoice.company_id, current_user, db)

    if invoice.payment_status == PaymentStatus.PAID:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cannot modify paid invoice")

    if invoice.status == InvoiceStatus.CANCELLED:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cannot modify cancelled invoice")

    update_data = invoice_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(invoice, field, value)

    db.commit()
    db.refresh(invoice)
    return invoice


@router.post("/{invoice_id}/send", response_model=InvoiceResponse)
async def send_invoice(
    invoice_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)
):
    """
    Mark invoice as sent and create automatic verification (accrual method only).

    Accrual method creates accounting entry:
        Debit:  1510 Kundfordringar
        Credit: 3xxx Revenue accounts
        Credit: 26xx VAT accounts

    Cash method: No verification is created - revenue is recognized on payment.
    """
    invoice = db.query(Invoice).filter(Invoice.id == invoice_id).first()
    if not invoice:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Invoice {invoice_id} not found")

    # Verify user has access to this company
    await verify_company_access(invoice.company_id, current_user, db)

    if invoice.status != InvoiceStatus.DRAFT:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invoice is not in draft status")

    # Get customer and company (needed for PDF)
    customer = db.query(Customer).filter(Customer.id == invoice.customer_id).first()
    company = db.query(Company).filter(Company.id == invoice.company_id).first()

    # Update status BEFORE generating PDF so it shows correct status
    invoice.status = InvoiceStatus.ISSUED
    invoice.sent_at = datetime.now()

    # Generate and archive PDF (immutable snapshot for bookkeeping)
    pdf_bytes = generate_invoice_pdf(invoice, customer, company)
    checksum = hashlib.sha256(pdf_bytes).hexdigest()

    storage_filename = f"{uuid.uuid4()}.pdf"
    file_path = ATTACHMENTS_DIR / storage_filename
    file_path.write_bytes(pdf_bytes)

    # Filename format: faktura_{companyId}_{number}_{YYYYMMDD}.pdf (sortable, no sensitive data)
    issue_date_str = invoice.invoice_date.strftime("%Y%m%d")
    original_filename = f"faktura_{invoice.company_id}_{invoice.invoice_number}_{issue_date_str}.pdf"

    attachment = Attachment(
        company_id=invoice.company_id,
        original_filename=original_filename,
        storage_filename=storage_filename,
        mime_type="application/pdf",
        size_bytes=len(pdf_bytes),
        checksum_sha256=checksum,
        status=AttachmentStatus.READY,
        created_by=current_user.id,
    )
    db.add(attachment)
    db.flush()

    link = AttachmentLink(
        attachment_id=attachment.id,
        entity_type=EntityType.INVOICE,
        entity_id=invoice.id,
        role=AttachmentRole.ARCHIVED_PDF,
        sort_order=0,
    )
    db.add(link)

    # Create verification only for accrual method
    if company.accounting_basis == AccountingBasis.ACCRUAL:
        verification = create_invoice_verification(db, invoice)
        invoice.invoice_verification_id = verification.id

        # Link archived PDF to verification as well (bokföringsunderlag)
        verification_link = AttachmentLink(
            attachment_id=attachment.id,
            entity_type=EntityType.VERIFICATION,
            entity_id=verification.id,
            role=AttachmentRole.ARCHIVED_PDF,
            sort_order=0,
        )
        db.add(verification_link)

    db.commit()
    db.refresh(invoice)

    return invoice


@router.post("/{invoice_id}/mark-paid", response_model=InvoiceResponse)
async def mark_invoice_paid(
    invoice_id: int,
    payment: MarkPaidRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    Mark invoice as paid and create payment verification.

    Accrual method:
        Debit:  1930 Bank account
        Credit: 1510 Customer receivables

    Cash method:
        Debit:  1930 Bank account
        Credit: 3xxx Revenue accounts (proportional)
        Credit: 26xx VAT accounts (proportional)
    """
    invoice = db.query(Invoice).filter(Invoice.id == invoice_id).first()
    if not invoice:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Invoice {invoice_id} not found")

    # Verify user has access to this company
    await verify_company_access(invoice.company_id, current_user, db)

    if invoice.payment_status == PaymentStatus.PAID:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invoice is already paid")

    if invoice.status == InvoiceStatus.CANCELLED:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot pay cancelled invoice")

    if invoice.status == InvoiceStatus.DRAFT:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Fakturan måste vara utfärdad (skickad) innan betalning kan registreras",
        )

    # Get company accounting basis
    company = db.query(Company).filter(Company.id == invoice.company_id).first()

    # Determine payment amount
    paid_amount = payment.paid_amount if payment.paid_amount else (invoice.total_amount - invoice.paid_amount)

    # Create payment verification with appropriate accounting method
    payment_verification = create_invoice_payment_verification(
        db, invoice, payment.paid_date, paid_amount, payment.bank_account_id, company.accounting_basis
    )

    # Link archived PDF to payment verification (bokföringsunderlag)
    archived_pdf = get_archived_pdf_attachment(db, invoice.id)
    if archived_pdf:
        payment_verification_link = AttachmentLink(
            attachment_id=archived_pdf.id,
            entity_type=EntityType.VERIFICATION,
            entity_id=payment_verification.id,
            role=AttachmentRole.ARCHIVED_PDF,
            sort_order=0,
        )
        db.add(payment_verification_link)

    # Create payment record for history
    invoice_payment = InvoicePayment(
        invoice_id=invoice.id,
        payment_date=payment.paid_date,
        amount=paid_amount,
        verification_id=payment_verification.id,
        bank_account_id=payment.bank_account_id,
        reference=payment.reference,
        notes=payment.notes,
    )
    db.add(invoice_payment)

    # Update invoice (cached values for backwards compatibility)
    invoice.paid_amount += paid_amount
    invoice.paid_date = payment.paid_date
    invoice.payment_verification_id = payment_verification.id

    # Update payment status (status stays as ISSUED)
    if invoice.paid_amount >= invoice.total_amount:
        invoice.payment_status = PaymentStatus.PAID
    else:
        invoice.payment_status = PaymentStatus.PARTIALLY_PAID

    db.commit()
    db.refresh(invoice)

    return invoice


@router.get("/{invoice_id}/pdf")
async def download_invoice_pdf(
    invoice_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)
):
    """
    Download invoice as PDF

    Returns a professionally formatted Swedish invoice PDF.
    For ISSUED invoices, returns the archived (immutable) PDF.
    For DRAFT invoices, generates on-demand for preview.
    """
    invoice = db.query(Invoice).filter(Invoice.id == invoice_id).first()
    if not invoice:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Invoice {invoice_id} not found")

    # Verify user has access to this company
    await verify_company_access(invoice.company_id, current_user, db)

    # ISSUED invoice: Return archived PDF (immutable snapshot)
    if invoice.status == InvoiceStatus.ISSUED:
        archived = get_archived_pdf_attachment(db, invoice_id)
        if archived:
            file_path = ATTACHMENTS_DIR / archived.storage_filename
            if file_path.exists():
                return FileResponse(
                    path=str(file_path),
                    filename=archived.original_filename,
                    media_type="application/pdf",
                )

    # DRAFT or missing archived: Generate on-demand (preview)
    customer = db.query(Customer).filter(Customer.id == invoice.customer_id).first()
    company = db.query(Company).filter(Company.id == invoice.company_id).first()

    if not customer or not company:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to load invoice data")

    try:
        pdf_bytes = generate_invoice_pdf(invoice, customer, company)
        # Filename format: faktura_{companyId}_{number}_{YYYYMMDD}.pdf
        issue_date_str = invoice.invoice_date.strftime("%Y%m%d")
        filename = f"faktura_{invoice.company_id}_{invoice.invoice_number}_{issue_date_str}.pdf"
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to generate PDF: {str(e)}"
        ) from e


@router.post("/{invoice_id}/cancel", response_model=InvoiceResponse)
async def cancel_invoice(
    invoice_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)
):
    """
    Cancel an invoice.

    Can only cancel invoices that are:
    - In DRAFT status (no accounting impact)
    - In ISSUED status with UNPAID payment status

    Cannot cancel invoices that have received payments - these should be credited instead.
    """
    invoice = db.query(Invoice).filter(Invoice.id == invoice_id).first()
    if not invoice:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Invoice {invoice_id} not found")

    # Verify user has access to this company
    await verify_company_access(invoice.company_id, current_user, db)

    if invoice.status == InvoiceStatus.CANCELLED:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invoice is already cancelled")

    if invoice.payment_status != PaymentStatus.UNPAID:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot cancel invoice with payments. Create a credit note instead.",
        )

    # TODO: If invoice was ISSUED with accounting entries (accrual method),
    # we should create reversing entries. For now, just mark as cancelled.
    invoice.status = InvoiceStatus.CANCELLED

    db.commit()
    db.refresh(invoice)

    return invoice


@router.delete("/{invoice_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_invoice(
    invoice_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)
):
    """Delete an invoice (only if draft or cancelled)"""
    invoice = db.query(Invoice).filter(Invoice.id == invoice_id).first()
    if not invoice:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Invoice {invoice_id} not found")

    # Verify user has access to this company
    await verify_company_access(invoice.company_id, current_user, db)

    if invoice.status not in [InvoiceStatus.DRAFT, InvoiceStatus.CANCELLED]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Can only delete draft or cancelled invoices")

    db.delete(invoice)
    db.commit()
    return None


# =============================================================================
# Attachment link endpoints
# =============================================================================


@router.post("/{invoice_id}/attachments", response_model=EntityAttachmentItem, status_code=status.HTTP_201_CREATED)
async def link_attachment(
    invoice_id: int,
    link_data: AttachmentLinkCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Link an attachment to an invoice"""
    invoice = db.query(Invoice).filter(Invoice.id == invoice_id).first()
    if not invoice:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Invoice {invoice_id} not found")

    await verify_company_access(invoice.company_id, current_user, db)

    # Check that fiscal year is open
    fiscal_year = (
        db.query(FiscalYear)
        .filter(
            FiscalYear.company_id == invoice.company_id,
            FiscalYear.start_date <= invoice.invoice_date,
            FiscalYear.end_date >= invoice.invoice_date,
        )
        .first()
    )
    if not fiscal_year or fiscal_year.is_closed:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot modify attachments when fiscal year is closed",
        )

    # Verify attachment exists and belongs to same company
    attachment = db.query(Attachment).filter(Attachment.id == link_data.attachment_id).first()
    if not attachment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Attachment {link_data.attachment_id} not found"
        )

    if attachment.company_id != invoice.company_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Attachment belongs to different company")

    # Check if link already exists
    existing_link = (
        db.query(AttachmentLink)
        .filter(
            AttachmentLink.attachment_id == link_data.attachment_id,
            AttachmentLink.entity_type == EntityType.INVOICE,
            AttachmentLink.entity_id == invoice_id,
        )
        .first()
    )
    if existing_link:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Attachment already linked to this invoice")

    # Create link
    link = AttachmentLink(
        attachment_id=link_data.attachment_id,
        entity_type=EntityType.INVOICE,
        entity_id=invoice_id,
        role=link_data.role or AttachmentRole.ORIGINAL,
        sort_order=link_data.sort_order or 0,
    )
    db.add(link)
    db.commit()
    db.refresh(link)

    return EntityAttachmentItem(
        link_id=link.id,
        attachment_id=attachment.id,
        original_filename=attachment.original_filename,
        mime_type=attachment.mime_type,
        size_bytes=attachment.size_bytes,
        status=attachment.status,
        role=link.role,
        sort_order=link.sort_order,
        created_at=attachment.created_at,
    )


@router.get("/{invoice_id}/attachments", response_model=list[EntityAttachmentItem])
async def list_invoice_attachments(
    invoice_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """List all attachments linked to an invoice"""
    invoice = db.query(Invoice).filter(Invoice.id == invoice_id).first()
    if not invoice:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Invoice {invoice_id} not found")

    await verify_company_access(invoice.company_id, current_user, db)

    links = (
        db.query(AttachmentLink)
        .filter(AttachmentLink.entity_type == EntityType.INVOICE, AttachmentLink.entity_id == invoice_id)
        .order_by(AttachmentLink.sort_order)
        .all()
    )

    result = []
    for link in links:
        attachment = db.query(Attachment).filter(Attachment.id == link.attachment_id).first()
        if attachment:
            result.append(
                EntityAttachmentItem(
                    link_id=link.id,
                    attachment_id=attachment.id,
                    original_filename=attachment.original_filename,
                    mime_type=attachment.mime_type,
                    size_bytes=attachment.size_bytes,
                    status=attachment.status,
                    role=link.role,
                    sort_order=link.sort_order,
                    created_at=attachment.created_at,
                )
            )

    return result


@router.delete("/{invoice_id}/attachments/{attachment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def unlink_attachment(
    invoice_id: int,
    attachment_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Unlink an attachment from an invoice"""
    invoice = db.query(Invoice).filter(Invoice.id == invoice_id).first()
    if not invoice:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Invoice {invoice_id} not found")

    await verify_company_access(invoice.company_id, current_user, db)

    # Check that fiscal year is open
    fiscal_year = (
        db.query(FiscalYear)
        .filter(
            FiscalYear.company_id == invoice.company_id,
            FiscalYear.start_date <= invoice.invoice_date,
            FiscalYear.end_date >= invoice.invoice_date,
        )
        .first()
    )
    if not fiscal_year or fiscal_year.is_closed:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot modify attachments when fiscal year is closed",
        )

    link = (
        db.query(AttachmentLink)
        .filter(
            AttachmentLink.attachment_id == attachment_id,
            AttachmentLink.entity_type == EntityType.INVOICE,
            AttachmentLink.entity_id == invoice_id,
        )
        .first()
    )
    if not link:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Attachment not linked to this invoice")

    # ARCHIVED_PDF is ALWAYS immutable (Swedish bookkeeping law)
    if link.role == AttachmentRole.ARCHIVED_PDF:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot remove archived invoice PDF (bookkeeping law)",
        )

    db.delete(link)
    db.commit()
    return None
