from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.dependencies import get_current_active_user, verify_company_access
from app.models.account import Account
from app.models.attachment import Attachment, AttachmentLink, AttachmentRole, EntityType
from app.models.fiscal_year import FiscalYear
from app.models.invoice import Invoice, SupplierInvoice
from app.models.user import User
from app.models.verification import TransactionLine, Verification
from app.schemas.attachment import AttachmentLinkCreate, EntityAttachmentItem
from app.schemas.verification import (
    VerificationCreate,
    VerificationListItem,
    VerificationResponse,
    VerificationUpdate,
)

router = APIRouter()


def get_next_verification_number(db: Session, company_id: int, series: str) -> int:
    """Helper function to get next verification number for a series"""
    last_ver = (
        db.query(Verification)
        .filter(Verification.company_id == company_id, Verification.series == series)
        .order_by(desc(Verification.verification_number))
        .first()
    )

    return (last_ver.verification_number + 1) if last_ver else 1


@router.post("/", response_model=VerificationResponse, status_code=status.HTTP_201_CREATED)
async def create_verification(
    verification: VerificationCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Create a new verification (verifikation)"""
    # Verify user has access to this company
    await verify_company_access(verification.company_id, current_user, db)

    # Get next verification number for this series
    next_number = get_next_verification_number(db, verification.company_id, verification.series)

    # Create verification
    db_verification = Verification(
        company_id=verification.company_id,
        fiscal_year_id=verification.fiscal_year_id,
        verification_number=next_number,
        series=verification.series,
        transaction_date=verification.transaction_date,
        description=verification.description,
        registration_date=date.today(),
    )
    db.add(db_verification)
    db.flush()  # Get verification ID

    # Create transaction lines and update account balances
    for line in verification.transaction_lines:
        # Verify account exists
        account = db.query(Account).filter(Account.id == line.account_id).first()
        if not account:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Account {line.account_id} not found")

        # Create transaction line
        db_line = TransactionLine(
            verification_id=db_verification.id,
            account_id=line.account_id,
            debit=line.debit,
            credit=line.credit,
            description=line.description,
        )
        db.add(db_line)

        # Update account balance
        # Debit increases assets/expenses, decreases liabilities/equity/revenue
        # Credit increases liabilities/equity/revenue, decreases assets/expenses
        net_change = line.debit - line.credit
        account.current_balance += net_change

    db.commit()
    db.refresh(db_verification)

    # Populate transaction lines with account info
    response = VerificationResponse.model_validate(db_verification)
    for i, line in enumerate(response.transaction_lines):
        account = db.query(Account).filter(Account.id == db_verification.transaction_lines[i].account_id).first()
        line.account_number = account.account_number
        line.account_name = account.name

    return response


@router.get("/", response_model=list[VerificationListItem])
async def list_verifications(
    company_id: int = Query(..., description="Company ID"),
    fiscal_year_id: int | None = Query(None, description="Fiscal Year ID"),
    start_date: date | None = None,
    end_date: date | None = None,
    series: str | None = None,
    limit: int = Query(100, le=1000),
    offset: int = 0,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """List verifications with filtering"""
    # Verify user has access to this company
    await verify_company_access(company_id, current_user, db)

    query = db.query(Verification).filter(Verification.company_id == company_id)

    if fiscal_year_id:
        query = query.filter(Verification.fiscal_year_id == fiscal_year_id)
    if start_date:
        query = query.filter(Verification.transaction_date >= start_date)
    if end_date:
        query = query.filter(Verification.transaction_date <= end_date)
    if series:
        query = query.filter(Verification.series == series)

    verifications = (
        query.order_by(desc(Verification.transaction_date), desc(Verification.verification_number))
        .limit(limit)
        .offset(offset)
        .all()
    )

    return [
        VerificationListItem(
            id=v.id,
            verification_number=v.verification_number,
            series=v.series,
            transaction_date=v.transaction_date,
            description=v.description,
            total_amount=Decimal(str(v.total_amount)),
            locked=v.locked,
        )
        for v in verifications
    ]


@router.get("/{verification_id}", response_model=VerificationResponse)
async def get_verification(
    verification_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)
):
    """Get a specific verification"""
    verification = db.query(Verification).filter(Verification.id == verification_id).first()
    if not verification:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Verification {verification_id} not found")

    # Verify user has access to this company
    await verify_company_access(verification.company_id, current_user, db)

    # Populate transaction lines with account info
    response = VerificationResponse.model_validate(verification)
    for i, line in enumerate(response.transaction_lines):
        account = db.query(Account).filter(Account.id == verification.transaction_lines[i].account_id).first()
        line.account_number = account.account_number
        line.account_name = account.name

    return response


@router.patch("/{verification_id}", response_model=VerificationResponse)
async def update_verification(
    verification_id: int,
    verification_update: VerificationUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Update a verification (only if not locked)"""
    verification = db.query(Verification).filter(Verification.id == verification_id).first()
    if not verification:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Verification {verification_id} not found")

    # Verify user has access to this company
    await verify_company_access(verification.company_id, current_user, db)

    if verification.locked:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cannot modify locked verification")

    # Update fields
    update_data = verification_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(verification, field, value)

    db.commit()
    db.refresh(verification)

    # Populate transaction lines with account info
    response = VerificationResponse.model_validate(verification)
    for i, line in enumerate(response.transaction_lines):
        account = db.query(Account).filter(Account.id == verification.transaction_lines[i].account_id).first()
        line.account_number = account.account_number
        line.account_name = account.name

    return response


@router.delete("/{verification_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_verification(
    verification_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)
):
    """
    Delete a verification (only allowed in development mode)

    WARNING: In production, verifications should NEVER be deleted.
    Instead, use correcting entries (reversal verifications).
    This endpoint is only available when DEBUG=True for development/testing.
    """
    # Only allow deletion in debug mode
    if not settings.debug:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Radering av verifikationer är inte tillåtet i produktionsläge. Använd istället korrigerande verifikationer.",
        )

    verification = db.query(Verification).filter(Verification.id == verification_id).first()
    if not verification:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Verification {verification_id} not found")

    # Verify user has access to this company
    await verify_company_access(verification.company_id, current_user, db)

    if verification.locked:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cannot delete locked verification")

    # Reverse account balance changes
    for line in verification.transaction_lines:
        account = db.query(Account).filter(Account.id == line.account_id).first()
        net_change = line.debit - line.credit
        account.current_balance -= net_change

    # Remove foreign key references from invoices before deletion
    # Customer invoices - reset to DRAFT if this was the invoice verification
    from app.models.invoice import InvoiceStatus

    invoices_to_reset = db.query(Invoice).filter(Invoice.invoice_verification_id == verification_id).all()
    for inv in invoices_to_reset:
        inv.invoice_verification_id = None
        inv.status = InvoiceStatus.DRAFT
        inv.sent_at = None

    # Customer invoices - remove payment verification reference
    db.query(Invoice).filter(Invoice.payment_verification_id == verification_id).update(
        {"payment_verification_id": None}
    )

    # Supplier invoices - reset to DRAFT if this was the invoice verification
    supplier_invoices_to_reset = (
        db.query(SupplierInvoice).filter(SupplierInvoice.invoice_verification_id == verification_id).all()
    )
    for inv in supplier_invoices_to_reset:
        inv.invoice_verification_id = None
        inv.status = InvoiceStatus.DRAFT

    # Supplier invoices - remove payment verification reference
    db.query(SupplierInvoice).filter(SupplierInvoice.payment_verification_id == verification_id).update(
        {"payment_verification_id": None}
    )

    # Delete verification (cascade will delete lines)
    db.delete(verification)
    db.commit()
    return None


# =============================================================================
# Attachment link endpoints
# =============================================================================


@router.post("/{verification_id}/attachments", response_model=EntityAttachmentItem, status_code=status.HTTP_201_CREATED)
async def link_attachment(
    verification_id: int,
    link_data: AttachmentLinkCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Link an attachment to a verification"""
    verification = db.query(Verification).filter(Verification.id == verification_id).first()
    if not verification:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Verification {verification_id} not found")

    await verify_company_access(verification.company_id, current_user, db)

    # Check that fiscal year is open
    fiscal_year = db.query(FiscalYear).filter(FiscalYear.id == verification.fiscal_year_id).first()
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

    if attachment.company_id != verification.company_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Attachment belongs to different company")

    # Check if link already exists
    existing_link = (
        db.query(AttachmentLink)
        .filter(
            AttachmentLink.attachment_id == link_data.attachment_id,
            AttachmentLink.entity_type == EntityType.VERIFICATION,
            AttachmentLink.entity_id == verification_id,
        )
        .first()
    )
    if existing_link:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Attachment already linked to this verification"
        )

    # Create link
    link = AttachmentLink(
        attachment_id=link_data.attachment_id,
        entity_type=EntityType.VERIFICATION,
        entity_id=verification_id,
        role=link_data.role or AttachmentRole.SUPPORTING,
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


@router.get("/{verification_id}/attachments", response_model=list[EntityAttachmentItem])
async def list_verification_attachments(
    verification_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """List all attachments linked to a verification"""
    verification = db.query(Verification).filter(Verification.id == verification_id).first()
    if not verification:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Verification {verification_id} not found")

    await verify_company_access(verification.company_id, current_user, db)

    links = (
        db.query(AttachmentLink)
        .filter(AttachmentLink.entity_type == EntityType.VERIFICATION, AttachmentLink.entity_id == verification_id)
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


@router.delete("/{verification_id}/attachments/{attachment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def unlink_attachment(
    verification_id: int,
    attachment_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Unlink an attachment from a verification"""
    verification = db.query(Verification).filter(Verification.id == verification_id).first()
    if not verification:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Verification {verification_id} not found")

    await verify_company_access(verification.company_id, current_user, db)

    # Check that fiscal year is open
    fiscal_year = db.query(FiscalYear).filter(FiscalYear.id == verification.fiscal_year_id).first()
    if not fiscal_year or fiscal_year.is_closed:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot modify attachments when fiscal year is closed",
        )

    link = (
        db.query(AttachmentLink)
        .filter(
            AttachmentLink.attachment_id == attachment_id,
            AttachmentLink.entity_type == EntityType.VERIFICATION,
            AttachmentLink.entity_id == verification_id,
        )
        .first()
    )
    if not link:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Attachment not linked to this verification")

    db.delete(link)
    db.commit()
    return None
