from datetime import date, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_active_user, verify_company_access
from app.models.attachment import Attachment, AttachmentLink, AttachmentRole, EntityType
from app.models.expense import Expense, ExpenseStatus
from app.models.fiscal_year import FiscalYear
from app.models.user import User
from app.schemas.attachment import AttachmentLinkCreate, EntityAttachmentItem
from app.schemas.expense import ExpenseCreate, ExpenseResponse, ExpenseUpdate
from app.services.expense_service import create_expense_payment_verification, create_expense_verification

router = APIRouter()


@router.post("/", response_model=ExpenseResponse, status_code=status.HTTP_201_CREATED)
async def create_expense(
    expense: ExpenseCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)
):
    """Create a new expense"""
    # Verify user has access to this company
    await verify_company_access(expense.company_id, current_user, db)

    db_expense = Expense(**expense.model_dump())
    db.add(db_expense)
    db.commit()
    db.refresh(db_expense)
    return db_expense


@router.get("/", response_model=list[ExpenseResponse])
async def list_expenses(
    company_id: int = Query(..., description="Company ID"),
    status_filter: str | None = Query(None, description="Filter by status"),
    employee_name: str | None = Query(None, description="Filter by employee name"),
    start_date: date | None = Query(None, description="Filter expenses from this date"),
    end_date: date | None = Query(None, description="Filter expenses until this date"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """List all expenses for a company with optional filters"""
    # Verify user has access to this company
    await verify_company_access(company_id, current_user, db)

    query = db.query(Expense).filter(Expense.company_id == company_id)

    if status_filter:
        query = query.filter(Expense.status == status_filter)

    if employee_name:
        query = query.filter(Expense.employee_name.ilike(f"%{employee_name}%"))

    if start_date:
        query = query.filter(Expense.expense_date >= start_date)

    if end_date:
        query = query.filter(Expense.expense_date <= end_date)

    expenses = query.order_by(Expense.expense_date.desc(), Expense.id.desc()).all()
    return expenses


@router.get("/{expense_id}", response_model=ExpenseResponse)
async def get_expense(
    expense_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)
):
    """Get a specific expense"""
    expense = db.query(Expense).filter(Expense.id == expense_id).first()
    if not expense:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Expense {expense_id} not found")

    # Verify user has access to this company
    await verify_company_access(expense.company_id, current_user, db)

    return expense


@router.patch("/{expense_id}", response_model=ExpenseResponse)
async def update_expense(
    expense_id: int,
    expense_update: ExpenseUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Update an expense"""
    expense = db.query(Expense).filter(Expense.id == expense_id).first()
    if not expense:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Expense {expense_id} not found")

    # Verify user has access to this company
    await verify_company_access(expense.company_id, current_user, db)

    update_data = expense_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(expense, field, value)

    db.commit()
    db.refresh(expense)
    return expense


@router.delete("/{expense_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_expense(
    expense_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)
):
    """Delete an expense"""
    expense = db.query(Expense).filter(Expense.id == expense_id).first()
    if not expense:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Expense {expense_id} not found")

    # Verify user has access to this company
    await verify_company_access(expense.company_id, current_user, db)

    db.delete(expense)
    db.commit()
    return None


@router.post("/{expense_id}/approve", response_model=ExpenseResponse)
async def approve_expense(
    expense_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)
):
    """Approve an expense"""
    expense = db.query(Expense).filter(Expense.id == expense_id).first()
    if not expense:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Expense {expense_id} not found")

    # Verify user has access to this company
    await verify_company_access(expense.company_id, current_user, db)

    if expense.status not in [ExpenseStatus.DRAFT, ExpenseStatus.SUBMITTED]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=f"Cannot approve expense with status {expense.status}"
        )

    expense.status = ExpenseStatus.APPROVED
    expense.approved_date = datetime.utcnow()

    db.commit()
    db.refresh(expense)
    return expense


@router.post("/{expense_id}/reject", response_model=ExpenseResponse)
async def reject_expense(
    expense_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)
):
    """Reject an expense"""
    expense = db.query(Expense).filter(Expense.id == expense_id).first()
    if not expense:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Expense {expense_id} not found")

    # Verify user has access to this company
    await verify_company_access(expense.company_id, current_user, db)

    if expense.status not in [ExpenseStatus.DRAFT, ExpenseStatus.SUBMITTED]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=f"Cannot reject expense with status {expense.status}"
        )

    expense.status = ExpenseStatus.REJECTED

    db.commit()
    db.refresh(expense)
    return expense


@router.post("/{expense_id}/mark-paid", response_model=ExpenseResponse)
async def mark_expense_paid(
    expense_id: int,
    paid_date: date = Query(...),
    bank_account_id: int = Query(..., description="Account ID for bank account (e.g., 1930)"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    Mark an expense as paid and create payment verification

    Swedish: Registrera utlägg som betalt

    Creates accounting entry:
    Debit:  Employee payable account (e.g., 2890)
    Credit: Bank account (e.g., 1930)
    """
    expense = db.query(Expense).filter(Expense.id == expense_id).first()
    if not expense:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Expense {expense_id} not found")

    # Verify user has access to this company
    await verify_company_access(expense.company_id, current_user, db)

    if expense.status != ExpenseStatus.APPROVED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Can only mark approved expenses as paid (current status: {expense.status})",
        )

    if not expense.verification_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Expense must be booked before marking as paid"
        )

    # Create payment verification
    try:
        create_expense_payment_verification(db, expense, paid_date, bank_account_id)

        # Update expense status
        expense.status = ExpenseStatus.PAID
        expense.paid_date = datetime.combine(paid_date, datetime.min.time())

        db.commit()
        db.refresh(expense)
        return expense
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e


@router.post("/{expense_id}/submit", response_model=ExpenseResponse)
async def submit_expense(
    expense_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)
):
    """Submit an expense for approval"""
    expense = db.query(Expense).filter(Expense.id == expense_id).first()
    if not expense:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Expense {expense_id} not found")

    # Verify user has access to this company
    await verify_company_access(expense.company_id, current_user, db)

    if expense.status != ExpenseStatus.DRAFT:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Can only submit draft expenses (current status: {expense.status})",
        )

    expense.status = ExpenseStatus.SUBMITTED

    db.commit()
    db.refresh(expense)
    return expense


@router.post("/{expense_id}/book", response_model=ExpenseResponse)
async def book_expense(
    expense_id: int,
    employee_payable_account_id: int = Query(..., description="Account ID for employee payable (e.g., 2890)"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    Book an approved expense and create verification

    Swedish: Bokför utlägg

    Creates accounting entry:
    Debit:  Expense account (e.g., 6540)
    Debit:  VAT incoming account (e.g., 2641)
    Credit: Employee payable account (e.g., 2890)
    """
    expense = db.query(Expense).filter(Expense.id == expense_id).first()
    if not expense:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Expense {expense_id} not found")

    # Verify user has access to this company
    await verify_company_access(expense.company_id, current_user, db)

    if expense.status != ExpenseStatus.APPROVED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Can only book approved expenses (current status: {expense.status})",
        )

    if expense.verification_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Expense is already booked")

    if not expense.expense_account_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Expense account must be set before booking"
        )

    if expense.vat_amount > 0 and not expense.vat_account_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="VAT account must be set when expense has VAT"
        )

    # Create verification
    try:
        verification = create_expense_verification(db, expense, employee_payable_account_id)
        expense.verification_id = verification.id
        db.commit()
        db.refresh(expense)
        return expense
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e


# =============================================================================
# Attachment link endpoints
# =============================================================================


@router.post("/{expense_id}/attachments", response_model=EntityAttachmentItem, status_code=status.HTTP_201_CREATED)
async def link_attachment(
    expense_id: int,
    link_data: AttachmentLinkCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Link an attachment to an expense"""
    expense = db.query(Expense).filter(Expense.id == expense_id).first()
    if not expense:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Expense {expense_id} not found")

    await verify_company_access(expense.company_id, current_user, db)

    # Check that fiscal year is open
    fiscal_year = (
        db.query(FiscalYear)
        .filter(
            FiscalYear.company_id == expense.company_id,
            FiscalYear.start_date <= expense.expense_date,
            FiscalYear.end_date >= expense.expense_date,
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

    if attachment.company_id != expense.company_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Attachment belongs to different company")

    # Check if link already exists
    existing_link = (
        db.query(AttachmentLink)
        .filter(
            AttachmentLink.attachment_id == link_data.attachment_id,
            AttachmentLink.entity_type == EntityType.EXPENSE,
            AttachmentLink.entity_id == expense_id,
        )
        .first()
    )
    if existing_link:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Attachment already linked to this expense")

    # Create link
    link = AttachmentLink(
        attachment_id=link_data.attachment_id,
        entity_type=EntityType.EXPENSE,
        entity_id=expense_id,
        role=link_data.role or AttachmentRole.RECEIPT,
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


@router.get("/{expense_id}/attachments", response_model=list[EntityAttachmentItem])
async def list_expense_attachments(
    expense_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """List all attachments linked to an expense"""
    expense = db.query(Expense).filter(Expense.id == expense_id).first()
    if not expense:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Expense {expense_id} not found")

    await verify_company_access(expense.company_id, current_user, db)

    links = (
        db.query(AttachmentLink)
        .filter(AttachmentLink.entity_type == EntityType.EXPENSE, AttachmentLink.entity_id == expense_id)
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


@router.delete("/{expense_id}/attachments/{attachment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def unlink_attachment(
    expense_id: int,
    attachment_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Unlink an attachment from an expense"""
    expense = db.query(Expense).filter(Expense.id == expense_id).first()
    if not expense:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Expense {expense_id} not found")

    await verify_company_access(expense.company_id, current_user, db)

    # Check that fiscal year is open
    fiscal_year = (
        db.query(FiscalYear)
        .filter(
            FiscalYear.company_id == expense.company_id,
            FiscalYear.start_date <= expense.expense_date,
            FiscalYear.end_date >= expense.expense_date,
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
            AttachmentLink.entity_type == EntityType.EXPENSE,
            AttachmentLink.entity_id == expense_id,
        )
        .first()
    )
    if not link:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Attachment not linked to this expense")

    db.delete(link)
    db.commit()
    return None
