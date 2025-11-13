"""
Dashboard router - provides overview data and KPIs
"""
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_
from datetime import datetime, date, timedelta
from decimal import Decimal
from typing import List, Dict, Optional

from app.database import get_db
from app.models.user import User
from app.models.company import Company
from app.models.invoice import Invoice, InvoiceStatus
from app.models.expense import Expense, ExpenseStatus
from app.models.verification import Verification, TransactionLine
from app.models.account import Account, AccountType
from app.models.fiscal_year import FiscalYear
from app.dependencies import get_current_active_user, verify_company_access


router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("/overview")
async def get_dashboard_overview(
    company_id: int = Query(..., description="Company ID"),
    fiscal_year_id: Optional[int] = Query(None, description="Fiscal Year ID (defaults to current fiscal year)"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Get dashboard overview with KPIs and recent activity

    Returns:
    - Current month revenue, expenses, and profit (within fiscal year)
    - Liquidity (bank account balance)
    - Overdue invoices count and amount
    - Pending expenses count and amount
    - Recent verifications
    - Monthly revenue/expense trend (for the fiscal year)
    """
    # Verify access
    await verify_company_access(company_id, current_user, db)

    # Get fiscal year
    if fiscal_year_id:
        fiscal_year = db.query(FiscalYear).filter(
            FiscalYear.id == fiscal_year_id,
            FiscalYear.company_id == company_id
        ).first()
        if not fiscal_year:
            raise HTTPException(status_code=404, detail="Fiscal year not found")
    else:
        # Get current active fiscal year
        fiscal_year = db.query(FiscalYear).filter(
            FiscalYear.company_id == company_id,
            FiscalYear.start_date <= date.today(),
            FiscalYear.end_date >= date.today()
        ).first()
        if not fiscal_year:
            raise HTTPException(status_code=404, detail="No active fiscal year found. Please create a fiscal year first.")

    # Current month date range (within fiscal year)
    today = date.today()
    # Ensure today is within fiscal year, otherwise use fiscal year boundaries
    if today < fiscal_year.start_date:
        today = fiscal_year.start_date
    elif today > fiscal_year.end_date:
        today = fiscal_year.end_date

    month_start = date(today.year, today.month, 1)
    if today.month == 12:
        month_end = date(today.year + 1, 1, 1) - timedelta(days=1)
    else:
        month_end = date(today.year, today.month + 1, 1) - timedelta(days=1)

    # Clamp to fiscal year boundaries
    if month_start < fiscal_year.start_date:
        month_start = fiscal_year.start_date
    if month_end > fiscal_year.end_date:
        month_end = fiscal_year.end_date

    # === CURRENT MONTH KPIs ===

    # Get revenue accounts (3xxx)
    revenue_accounts = db.query(Account.id).filter(
        Account.company_id == company_id,
        Account.account_number >= 3000,
        Account.account_number < 4000
    ).all()
    revenue_account_ids = [acc[0] for acc in revenue_accounts]

    # Get expense accounts (4xxx-8xxx)
    expense_accounts = db.query(Account.id).filter(
        Account.company_id == company_id,
        Account.account_number >= 4000,
        Account.account_number < 9000
    ).all()
    expense_account_ids = [acc[0] for acc in expense_accounts]

    # Calculate revenue this month (credit - debit on revenue accounts)
    revenue_credits = db.query(
        func.sum(TransactionLine.credit)
    ).join(Verification).filter(
        Verification.company_id == company_id,
        Verification.transaction_date >= month_start,
        Verification.transaction_date <= month_end,
        TransactionLine.account_id.in_(revenue_account_ids)
    ).scalar() or Decimal(0)

    revenue_debits = db.query(
        func.sum(TransactionLine.debit)
    ).join(Verification).filter(
        Verification.company_id == company_id,
        Verification.transaction_date >= month_start,
        Verification.transaction_date <= month_end,
        TransactionLine.account_id.in_(revenue_account_ids)
    ).scalar() or Decimal(0)

    revenue_this_month = revenue_credits - revenue_debits

    # Calculate expenses this month (debit - credit on expense accounts)
    expenses_debits = db.query(
        func.sum(TransactionLine.debit)
    ).join(Verification).filter(
        Verification.company_id == company_id,
        Verification.transaction_date >= month_start,
        Verification.transaction_date <= month_end,
        TransactionLine.account_id.in_(expense_account_ids)
    ).scalar() or Decimal(0)

    expenses_credits = db.query(
        func.sum(TransactionLine.credit)
    ).join(Verification).filter(
        Verification.company_id == company_id,
        Verification.transaction_date >= month_start,
        Verification.transaction_date <= month_end,
        TransactionLine.account_id.in_(expense_account_ids)
    ).scalar() or Decimal(0)

    expenses_this_month = expenses_debits - expenses_credits

    # Profit this month
    profit_this_month = revenue_this_month - expenses_this_month

    # === LIQUIDITY ===

    # Get bank account (1930)
    bank_account = db.query(Account).filter(
        Account.company_id == company_id,
        Account.account_number == 1930
    ).first()

    liquidity = float(bank_account.balance) if bank_account else 0.0

    # === OVERDUE INVOICES ===

    overdue_invoices = db.query(Invoice).filter(
        Invoice.company_id == company_id,
        Invoice.status.in_([InvoiceStatus.SENT, InvoiceStatus.PARTIAL]),
        Invoice.due_date < today
    ).all()

    overdue_count = len(overdue_invoices)
    overdue_amount = sum(float(inv.total_amount) for inv in overdue_invoices)

    # === PENDING EXPENSES ===

    pending_expenses = db.query(Expense).filter(
        Expense.company_id == company_id,
        Expense.status.in_([ExpenseStatus.SUBMITTED, ExpenseStatus.APPROVED])
    ).all()

    pending_expenses_count = len(pending_expenses)
    pending_expenses_amount = sum(float(exp.total_amount) for exp in pending_expenses)

    # === RECENT VERIFICATIONS ===

    recent_verifications = db.query(Verification).filter(
        Verification.company_id == company_id,
        Verification.fiscal_year_id == fiscal_year.id
    ).order_by(Verification.transaction_date.desc()).limit(5).all()

    recent_verifications_data = [{
        "id": v.id,
        "verification_number": v.verification_number,
        "series": v.series,
        "transaction_date": v.transaction_date.isoformat(),
        "description": v.description,
        "locked": v.locked
    } for v in recent_verifications]

    # === MONTHLY TREND (All months in fiscal year) ===

    trend_data = []
    # Generate all months within the fiscal year
    current_month_start = fiscal_year.start_date.replace(day=1)
    fiscal_year_end = fiscal_year.end_date

    while current_month_start <= fiscal_year_end:
        # Calculate month end
        if current_month_start.month == 12:
            month_end_trend = date(current_month_start.year + 1, 1, 1) - timedelta(days=1)
        else:
            month_end_trend = date(current_month_start.year, current_month_start.month + 1, 1) - timedelta(days=1)

        # Clamp to fiscal year end
        if month_end_trend > fiscal_year_end:
            month_end_trend = fiscal_year_end

        # Revenue for this month (credit - debit)
        revenue_credits_month = db.query(
            func.sum(TransactionLine.credit)
        ).join(Verification).filter(
            Verification.company_id == company_id,
            Verification.fiscal_year_id == fiscal_year.id,
            Verification.transaction_date >= current_month_start,
            Verification.transaction_date <= month_end_trend,
            TransactionLine.account_id.in_(revenue_account_ids)
        ).scalar() or Decimal(0)

        revenue_debits_month = db.query(
            func.sum(TransactionLine.debit)
        ).join(Verification).filter(
            Verification.company_id == company_id,
            Verification.fiscal_year_id == fiscal_year.id,
            Verification.transaction_date >= current_month_start,
            Verification.transaction_date <= month_end_trend,
            TransactionLine.account_id.in_(revenue_account_ids)
        ).scalar() or Decimal(0)

        revenue_month = revenue_credits_month - revenue_debits_month

        # Expenses for this month (debit - credit)
        expenses_debits_month = db.query(
            func.sum(TransactionLine.debit)
        ).join(Verification).filter(
            Verification.company_id == company_id,
            Verification.fiscal_year_id == fiscal_year.id,
            Verification.transaction_date >= current_month_start,
            Verification.transaction_date <= month_end_trend,
            TransactionLine.account_id.in_(expense_account_ids)
        ).scalar() or Decimal(0)

        expenses_credits_month = db.query(
            func.sum(TransactionLine.credit)
        ).join(Verification).filter(
            Verification.company_id == company_id,
            Verification.fiscal_year_id == fiscal_year.id,
            Verification.transaction_date >= current_month_start,
            Verification.transaction_date <= month_end_trend,
            TransactionLine.account_id.in_(expense_account_ids)
        ).scalar() or Decimal(0)

        expenses_month = expenses_debits_month - expenses_credits_month

        trend_data.append({
            "month": current_month_start.strftime("%Y-%m"),
            "revenue": float(revenue_month),
            "expenses": float(expenses_month),
            "profit": float(revenue_month - expenses_month)
        })

        # Move to next month
        if current_month_start.month == 12:
            current_month_start = date(current_month_start.year + 1, 1, 1)
        else:
            current_month_start = date(current_month_start.year, current_month_start.month + 1, 1)

    return {
        "fiscal_year": {
            "id": fiscal_year.id,
            "label": fiscal_year.label,
            "start_date": fiscal_year.start_date.isoformat(),
            "end_date": fiscal_year.end_date.isoformat(),
            "is_closed": fiscal_year.is_closed
        },
        "current_month": {
            "revenue": float(revenue_this_month),
            "expenses": float(expenses_this_month),
            "profit": float(profit_this_month),
            "month_label": month_start.strftime("%B %Y")
        },
        "liquidity": liquidity,
        "overdue_invoices": {
            "count": overdue_count,
            "amount": overdue_amount
        },
        "pending_expenses": {
            "count": pending_expenses_count,
            "amount": pending_expenses_amount
        },
        "recent_verifications": recent_verifications_data,
        "monthly_trend": trend_data
    }
