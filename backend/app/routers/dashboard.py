"""
Dashboard router - provides overview data and KPIs
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_
from datetime import datetime, date, timedelta
from decimal import Decimal
from typing import List, Dict

from app.database import get_db
from app.models.user import User
from app.models.company import Company
from app.models.invoice import Invoice, InvoiceStatus
from app.models.expense import Expense, ExpenseStatus
from app.models.verification import Verification, TransactionLine
from app.models.account import Account, AccountType
from app.dependencies import get_current_active_user, verify_company_access


router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("/overview")
async def get_dashboard_overview(
    company_id: int = Query(..., description="Company ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Get dashboard overview with KPIs and recent activity

    Returns:
    - Current month revenue, expenses, and profit
    - Liquidity (bank account balance)
    - Overdue invoices count and amount
    - Pending expenses count and amount
    - Recent verifications
    - Monthly revenue/expense trend (last 12 months)
    """
    # Verify access
    await verify_company_access(company_id, current_user, db)

    # Current month date range
    today = date.today()
    month_start = date(today.year, today.month, 1)
    if today.month == 12:
        month_end = date(today.year + 1, 1, 1) - timedelta(days=1)
    else:
        month_end = date(today.year, today.month + 1, 1) - timedelta(days=1)

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

    # Calculate revenue this month (credits on revenue accounts)
    revenue_this_month = db.query(
        func.sum(TransactionLine.credit_amount)
    ).join(Verification).filter(
        Verification.company_id == company_id,
        Verification.transaction_date >= month_start,
        Verification.transaction_date <= month_end,
        TransactionLine.account_id.in_(revenue_account_ids)
    ).scalar() or Decimal(0)

    # Calculate expenses this month (debits on expense accounts)
    expenses_this_month = db.query(
        func.sum(TransactionLine.debit_amount)
    ).join(Verification).filter(
        Verification.company_id == company_id,
        Verification.transaction_date >= month_start,
        Verification.transaction_date <= month_end,
        TransactionLine.account_id.in_(expense_account_ids)
    ).scalar() or Decimal(0)

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
        Verification.company_id == company_id
    ).order_by(Verification.transaction_date.desc()).limit(5).all()

    recent_verifications_data = [{
        "id": v.id,
        "verification_number": v.verification_number,
        "series": v.series,
        "transaction_date": v.transaction_date.isoformat(),
        "description": v.description,
        "locked": v.locked
    } for v in recent_verifications]

    # === MONTHLY TREND (Last 12 months) ===

    trend_data = []
    for i in range(11, -1, -1):  # 12 months back to current
        target_date = today.replace(day=1) - timedelta(days=i*30)
        month_start_trend = date(target_date.year, target_date.month, 1)

        if target_date.month == 12:
            month_end_trend = date(target_date.year + 1, 1, 1) - timedelta(days=1)
        else:
            month_end_trend = date(target_date.year, target_date.month + 1, 1) - timedelta(days=1)

        # Revenue for this month
        revenue_month = db.query(
            func.sum(TransactionLine.credit_amount)
        ).join(Verification).filter(
            Verification.company_id == company_id,
            Verification.transaction_date >= month_start_trend,
            Verification.transaction_date <= month_end_trend,
            TransactionLine.account_id.in_(revenue_account_ids)
        ).scalar() or Decimal(0)

        # Expenses for this month
        expenses_month = db.query(
            func.sum(TransactionLine.debit_amount)
        ).join(Verification).filter(
            Verification.company_id == company_id,
            Verification.transaction_date >= month_start_trend,
            Verification.transaction_date <= month_end_trend,
            TransactionLine.account_id.in_(expense_account_ids)
        ).scalar() or Decimal(0)

        trend_data.append({
            "month": month_start_trend.strftime("%Y-%m"),
            "revenue": float(revenue_month),
            "expenses": float(expenses_month),
            "profit": float(revenue_month - expenses_month)
        })

    return {
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
