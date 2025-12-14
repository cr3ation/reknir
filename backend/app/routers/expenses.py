import shutil
import uuid
from datetime import date, datetime
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_active_user, verify_company_access
from app.models.expense import Expense, ExpenseStatus
from app.models.user import User
from app.schemas.expense import ExpenseCreate, ExpenseResponse, ExpenseUpdate
from app.services.expense_service import create_expense_payment_verification, create_expense_verification

router = APIRouter()

# Create receipts directory if it doesn't exist
RECEIPTS_DIR = Path("/app/receipts")
RECEIPTS_DIR.mkdir(exist_ok=True)


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


@router.post("/{expense_id}/upload-receipt", response_model=ExpenseResponse)
async def upload_receipt(
    expense_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Upload a receipt file for an expense"""
    expense = db.query(Expense).filter(Expense.id == expense_id).first()
    if not expense:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Expense {expense_id} not found")

    # Verify user has access to this company
    await verify_company_access(expense.company_id, current_user, db)

    # Validate file type (images and PDFs)
    allowed_extensions = {".jpg", ".jpeg", ".png", ".pdf", ".gif"}
    file_ext = Path(file.filename).suffix.lower()
    if file_ext not in allowed_extensions:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File type {file_ext} not allowed. Allowed types: {', '.join(allowed_extensions)}",
        )

    # Delete old receipt if exists
    if expense.receipt_filename:
        old_path = RECEIPTS_DIR / expense.receipt_filename
        if old_path.exists():
            old_path.unlink()

    # Generate unique filename
    unique_filename = f"{uuid.uuid4()}{file_ext}"
    file_path = RECEIPTS_DIR / unique_filename

    # Save file
    with file_path.open("wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    # Update expense record
    expense.receipt_filename = unique_filename
    db.commit()
    db.refresh(expense)

    return expense


@router.get("/{expense_id}/receipt")
async def download_receipt(
    expense_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)
):
    """Download the receipt file for an expense"""
    expense = db.query(Expense).filter(Expense.id == expense_id).first()
    if not expense:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Expense {expense_id} not found")

    # Verify user has access to this company
    await verify_company_access(expense.company_id, current_user, db)

    if not expense.receipt_filename:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No receipt file found for this expense")

    file_path = RECEIPTS_DIR / expense.receipt_filename
    if not file_path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Receipt file not found on disk")

    return FileResponse(path=str(file_path), filename=expense.receipt_filename, media_type="application/octet-stream")


@router.delete("/{expense_id}/receipt", response_model=ExpenseResponse)
async def delete_receipt(
    expense_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)
):
    """Delete the receipt file for an expense"""
    expense = db.query(Expense).filter(Expense.id == expense_id).first()
    if not expense:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Expense {expense_id} not found")

    # Verify user has access to this company
    await verify_company_access(expense.company_id, current_user, db)

    if not expense.receipt_filename:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No receipt file found for this expense")

    # Delete file from disk
    file_path = RECEIPTS_DIR / expense.receipt_filename
    if file_path.exists():
        file_path.unlink()

    # Clear filename from database
    expense.receipt_filename = None
    db.commit()
    db.refresh(expense)

    return expense
