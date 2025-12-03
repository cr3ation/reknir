from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import desc
from typing import List, Optional
from datetime import date
from decimal import Decimal
from app.database import get_db
from app.models.verification import Verification, TransactionLine
from app.models.account import Account
from app.models.invoice import Invoice, SupplierInvoice
from app.schemas.verification import (
    VerificationCreate,
    VerificationResponse,
    VerificationUpdate,
    VerificationListItem,
    TransactionLineResponse
)
from app.config import settings

router = APIRouter()


def get_next_verification_number(db: Session, company_id: int, series: str) -> int:
    """Helper function to get next verification number for a series"""
    last_ver = db.query(Verification).filter(
        Verification.company_id == company_id,
        Verification.series == series
    ).order_by(desc(Verification.verification_number)).first()

    return (last_ver.verification_number + 1) if last_ver else 1


@router.post("/", response_model=VerificationResponse, status_code=status.HTTP_201_CREATED)
def create_verification(verification: VerificationCreate, db: Session = Depends(get_db)):
    """Create a new verification (verifikation)"""

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
        registration_date=date.today()
    )
    db.add(db_verification)
    db.flush()  # Get verification ID

    # Create transaction lines and update account balances
    for line in verification.transaction_lines:
        # Verify account exists
        account = db.query(Account).filter(Account.id == line.account_id).first()
        if not account:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Account {line.account_id} not found"
            )

        # Create transaction line
        db_line = TransactionLine(
            verification_id=db_verification.id,
            account_id=line.account_id,
            debit=line.debit,
            credit=line.credit,
            description=line.description
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


@router.get("/", response_model=List[VerificationListItem])
def list_verifications(
    company_id: int = Query(..., description="Company ID"),
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    series: Optional[str] = None,
    limit: int = Query(100, le=1000),
    offset: int = 0,
    db: Session = Depends(get_db)
):
    """List verifications with filtering"""
    query = db.query(Verification).filter(Verification.company_id == company_id)

    if start_date:
        query = query.filter(Verification.transaction_date >= start_date)
    if end_date:
        query = query.filter(Verification.transaction_date <= end_date)
    if series:
        query = query.filter(Verification.series == series)

    verifications = query.order_by(
        desc(Verification.transaction_date),
        desc(Verification.verification_number)
    ).limit(limit).offset(offset).all()

    return [
        VerificationListItem(
            id=v.id,
            verification_number=v.verification_number,
            series=v.series,
            transaction_date=v.transaction_date,
            description=v.description,
            total_amount=Decimal(str(v.total_amount)),
            locked=v.locked
        )
        for v in verifications
    ]


@router.get("/{verification_id}", response_model=VerificationResponse)
def get_verification(verification_id: int, db: Session = Depends(get_db)):
    """Get a specific verification"""
    verification = db.query(Verification).filter(Verification.id == verification_id).first()
    if not verification:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Verification {verification_id} not found"
        )

    # Populate transaction lines with account info
    response = VerificationResponse.model_validate(verification)
    for i, line in enumerate(response.transaction_lines):
        account = db.query(Account).filter(Account.id == verification.transaction_lines[i].account_id).first()
        line.account_number = account.account_number
        line.account_name = account.name

    return response


@router.patch("/{verification_id}", response_model=VerificationResponse)
def update_verification(
    verification_id: int,
    verification_update: VerificationUpdate,
    db: Session = Depends(get_db)
):
    """Update a verification (only if not locked)"""
    verification = db.query(Verification).filter(Verification.id == verification_id).first()
    if not verification:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Verification {verification_id} not found"
        )

    if verification.locked:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot modify locked verification"
        )

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
def delete_verification(verification_id: int, db: Session = Depends(get_db)):
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
            detail="Radering av verifikationer är inte tillåtet i produktionsläge. Använd istället korrigerande verifikationer."
        )

    verification = db.query(Verification).filter(Verification.id == verification_id).first()
    if not verification:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Verification {verification_id} not found"
        )

    if verification.locked:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot delete locked verification"
        )

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
    supplier_invoices_to_reset = db.query(SupplierInvoice).filter(
        SupplierInvoice.invoice_verification_id == verification_id
    ).all()
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
