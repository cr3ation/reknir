from fastapi import APIRouter, Depends, HTTPException, status, Query, UploadFile, File
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime, date
from pathlib import Path
import shutil
import uuid
from app.database import get_db
from app.models.expense import Expense, ExpenseStatus
from app.schemas.expense import ExpenseCreate, ExpenseResponse, ExpenseUpdate
from app.services.expense_service import create_expense_verification, create_expense_payment_verification

router = APIRouter()

# Create receipts directory if it doesn't exist
RECEIPTS_DIR = Path("/app/receipts")
RECEIPTS_DIR.mkdir(exist_ok=True)


@router.post("/", response_model=ExpenseResponse, status_code=status.HTTP_201_CREATED)
def create_expense(expense: ExpenseCreate, db: Session = Depends(get_db)):
    """Create a new expense"""
    db_expense = Expense(**expense.model_dump())
    db.add(db_expense)
    db.commit()
    db.refresh(db_expense)
    return db_expense


@router.get("/", response_model=List[ExpenseResponse])
def list_expenses(
    company_id: int = Query(..., description="Company ID"),
    status_filter: Optional[str] = Query(None, description="Filter by status"),
    employee_name: Optional[str] = Query(None, description="Filter by employee name"),
    start_date: Optional[date] = Query(None, description="Filter expenses from this date"),
    end_date: Optional[date] = Query(None, description="Filter expenses until this date"),
    db: Session = Depends(get_db)
):
    """List all expenses for a company with optional filters"""
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
def get_expense(expense_id: int, db: Session = Depends(get_db)):
    """Get a specific expense"""
    expense = db.query(Expense).filter(Expense.id == expense_id).first()
    if not expense:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Expense {expense_id} not found"
        )
    return expense


@router.patch("/{expense_id}", response_model=ExpenseResponse)
def update_expense(expense_id: int, expense_update: ExpenseUpdate, db: Session = Depends(get_db)):
    """Update an expense"""
    expense = db.query(Expense).filter(Expense.id == expense_id).first()
    if not expense:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Expense {expense_id} not found"
        )

    update_data = expense_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(expense, field, value)

    db.commit()
    db.refresh(expense)
    return expense


@router.delete("/{expense_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_expense(expense_id: int, db: Session = Depends(get_db)):
    """Delete an expense"""
    expense = db.query(Expense).filter(Expense.id == expense_id).first()
    if not expense:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Expense {expense_id} not found"
        )

    db.delete(expense)
    db.commit()
    return None


@router.post("/{expense_id}/approve", response_model=ExpenseResponse)
def approve_expense(expense_id: int, db: Session = Depends(get_db)):
    """Approve an expense"""
    expense = db.query(Expense).filter(Expense.id == expense_id).first()
    if not expense:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Expense {expense_id} not found"
        )

    if expense.status not in [ExpenseStatus.DRAFT, ExpenseStatus.SUBMITTED]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot approve expense with status {expense.status}"
        )

    expense.status = ExpenseStatus.APPROVED
    expense.approved_date = datetime.utcnow()

    db.commit()
    db.refresh(expense)
    return expense


@router.post("/{expense_id}/reject", response_model=ExpenseResponse)
def reject_expense(expense_id: int, db: Session = Depends(get_db)):
    """Reject an expense"""
    expense = db.query(Expense).filter(Expense.id == expense_id).first()
    if not expense:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Expense {expense_id} not found"
        )

    if expense.status not in [ExpenseStatus.DRAFT, ExpenseStatus.SUBMITTED]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot reject expense with status {expense.status}"
        )

    expense.status = ExpenseStatus.REJECTED

    db.commit()
    db.refresh(expense)
    return expense


@router.post("/{expense_id}/mark-paid", response_model=ExpenseResponse)
def mark_expense_paid(
    expense_id: int,
    paid_date: date = Query(...),
    bank_account_id: int = Query(..., description="Account ID for bank account (e.g., 1930)"),
    db: Session = Depends(get_db)
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
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Expense {expense_id} not found"
        )

    if expense.status != ExpenseStatus.APPROVED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Can only mark approved expenses as paid (current status: {expense.status})"
        )

    if not expense.verification_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Expense must be booked before marking as paid"
        )

    # Create payment verification
    try:
        payment_verification = create_expense_payment_verification(
            db, expense, paid_date, bank_account_id
        )

        # Update expense status
        expense.status = ExpenseStatus.PAID
        expense.paid_date = datetime.combine(paid_date, datetime.min.time())

        db.commit()
        db.refresh(expense)
        return expense
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.post("/{expense_id}/submit", response_model=ExpenseResponse)
def submit_expense(expense_id: int, db: Session = Depends(get_db)):
    """Submit an expense for approval"""
    expense = db.query(Expense).filter(Expense.id == expense_id).first()
    if not expense:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Expense {expense_id} not found"
        )

    if expense.status != ExpenseStatus.DRAFT:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Can only submit draft expenses (current status: {expense.status})"
        )

    expense.status = ExpenseStatus.SUBMITTED

    db.commit()
    db.refresh(expense)
    return expense


@router.post("/{expense_id}/book", response_model=ExpenseResponse)
def book_expense(
    expense_id: int,
    employee_payable_account_id: int = Query(..., description="Account ID for employee payable (e.g., 2890)"),
    db: Session = Depends(get_db)
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
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Expense {expense_id} not found"
        )

    if expense.status != ExpenseStatus.APPROVED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Can only book approved expenses (current status: {expense.status})"
        )

    if expense.verification_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Expense is already booked"
        )

    if not expense.expense_account_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Expense account must be set before booking"
        )

    if expense.vat_amount > 0 and not expense.vat_account_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="VAT account must be set when expense has VAT"
        )

    # Create verification
    try:
        verification = create_expense_verification(db, expense, employee_payable_account_id)
        expense.verification_id = verification.id
        db.commit()
        db.refresh(expense)
        return expense
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.post("/{expense_id}/upload-receipt", response_model=ExpenseResponse)
async def upload_receipt(
    expense_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """Upload a receipt file for an expense"""
    expense = db.query(Expense).filter(Expense.id == expense_id).first()
    if not expense:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Expense {expense_id} not found"
        )

    # Validate file type (images and PDFs)
    allowed_extensions = {'.jpg', '.jpeg', '.png', '.pdf', '.gif'}
    file_ext = Path(file.filename).suffix.lower()
    if file_ext not in allowed_extensions:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File type {file_ext} not allowed. Allowed types: {', '.join(allowed_extensions)}"
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
async def download_receipt(expense_id: int, db: Session = Depends(get_db)):
    """Download the receipt file for an expense"""
    expense = db.query(Expense).filter(Expense.id == expense_id).first()
    if not expense:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Expense {expense_id} not found"
        )

    if not expense.receipt_filename:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No receipt file found for this expense"
        )

    file_path = RECEIPTS_DIR / expense.receipt_filename
    if not file_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Receipt file not found on disk"
        )

    return FileResponse(
        path=str(file_path),
        filename=expense.receipt_filename,
        media_type="application/octet-stream"
    )


@router.delete("/{expense_id}/receipt", response_model=ExpenseResponse)
async def delete_receipt(expense_id: int, db: Session = Depends(get_db)):
    """Delete the receipt file for an expense"""
    expense = db.query(Expense).filter(Expense.id == expense_id).first()
    if not expense:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Expense {expense_id} not found"
        )

    if not expense.receipt_filename:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No receipt file found for this expense"
        )

    # Delete file from disk
    file_path = RECEIPTS_DIR / expense.receipt_filename
    if file_path.exists():
        file_path.unlink()

    # Clear filename from database
    expense.receipt_filename = None
    db.commit()
    db.refresh(expense)

    return expense
