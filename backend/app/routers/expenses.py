from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime, date
from app.database import get_db
from app.models.expense import Expense, ExpenseStatus
from app.schemas.expense import ExpenseCreate, ExpenseResponse, ExpenseUpdate

router = APIRouter()


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
def mark_expense_paid(expense_id: int, paid_date: date = Query(...), db: Session = Depends(get_db)):
    """Mark an expense as paid"""
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

    expense.status = ExpenseStatus.PAID
    expense.paid_date = datetime.combine(paid_date, datetime.min.time())

    db.commit()
    db.refresh(expense)
    return expense


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
