from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import Dict, List, Optional
from decimal import Decimal
from datetime import date, datetime, timedelta
from app.database import get_db
from app.models.account import Account, AccountType
from app.models.verification import Verification, TransactionLine
from app.models.company import Company, VATReportingPeriod

router = APIRouter()


@router.get("/balance-sheet")
def get_balance_sheet(
    company_id: int = Query(..., description="Company ID"),
    db: Session = Depends(get_db)
):
    """
    Generate Balance Sheet (Balansräkning)
    Assets = Liabilities + Equity
    """

    # Get all accounts with balances
    accounts = db.query(Account).filter(
        Account.company_id == company_id,
        Account.active == True
    ).all()

    # Group by account type
    assets = []
    liabilities = []
    equity = []

    for account in accounts:
        item = {
            "account_number": account.account_number,
            "name": account.name,
            "balance": float(account.current_balance)
        }

        if account.account_type == AccountType.ASSET:
            assets.append(item)
        elif account.account_type == AccountType.EQUITY_LIABILITY:
            # Determine if equity or liability based on account number
            # 2000-2999: Equity (Eget kapital)
            # 2100-2999: Liabilities (Skulder)
            if 2000 <= account.account_number < 2100:
                equity.append(item)
            else:
                liabilities.append(item)

    total_assets = sum(a["balance"] for a in assets)
    total_liabilities = sum(l["balance"] for l in liabilities)
    total_equity = sum(e["balance"] for e in equity)

    return {
        "company_id": company_id,
        "report_type": "balance_sheet",
        "assets": {
            "accounts": assets,
            "total": total_assets
        },
        "liabilities": {
            "accounts": liabilities,
            "total": total_liabilities
        },
        "equity": {
            "accounts": equity,
            "total": total_equity
        },
        "total_liabilities_and_equity": total_liabilities + total_equity,
        "balanced": abs(total_assets - (total_liabilities + total_equity)) < 0.01
    }


@router.get("/income-statement")
def get_income_statement(
    company_id: int = Query(..., description="Company ID"),
    db: Session = Depends(get_db)
):
    """
    Generate Income Statement (Resultaträkning)
    Revenue - Expenses = Profit/Loss
    """

    # Get all revenue and expense accounts
    accounts = db.query(Account).filter(
        Account.company_id == company_id,
        Account.active == True,
        Account.account_type.in_([
            AccountType.REVENUE,
            AccountType.COST_GOODS,
            AccountType.COST_LOCAL,
            AccountType.COST_OTHER,
            AccountType.COST_PERSONNEL,
            AccountType.COST_MISC
        ])
    ).all()

    revenue = []
    expenses = []

    for account in accounts:
        item = {
            "account_number": account.account_number,
            "name": account.name,
            "balance": float(account.current_balance)
        }

        if account.account_type == AccountType.REVENUE:
            revenue.append(item)
        else:
            expenses.append(item)

    total_revenue = sum(r["balance"] for r in revenue)
    total_expenses = sum(e["balance"] for e in expenses)
    profit_loss = total_revenue - total_expenses

    return {
        "company_id": company_id,
        "report_type": "income_statement",
        "revenue": {
            "accounts": revenue,
            "total": total_revenue
        },
        "expenses": {
            "accounts": expenses,
            "total": total_expenses
        },
        "profit_loss": profit_loss
    }


@router.get("/trial-balance")
def get_trial_balance(
    company_id: int = Query(..., description="Company ID"),
    db: Session = Depends(get_db)
):
    """
    Generate Trial Balance (Råbalans/RAR)
    Shows all accounts with opening balance, changes, and closing balance
    """

    accounts = db.query(Account).filter(
        Account.company_id == company_id,
        Account.active == True
    ).order_by(Account.account_number).all()

    trial_balance = []
    total_debit = Decimal("0")
    total_credit = Decimal("0")

    for account in accounts:
        change = account.current_balance - account.opening_balance

        item = {
            "account_number": account.account_number,
            "name": account.name,
            "account_type": account.account_type.value,
            "opening_balance": float(account.opening_balance),
            "change": float(change),
            "closing_balance": float(account.current_balance)
        }

        trial_balance.append(item)

        # Sum debits and credits
        if account.current_balance > 0:
            total_debit += account.current_balance
        else:
            total_credit += abs(account.current_balance)

    return {
        "company_id": company_id,
        "report_type": "trial_balance",
        "accounts": trial_balance,
        "total_debit": float(total_debit),
        "total_credit": float(total_credit),
        "balanced": abs(total_debit - total_credit) < 0.01
    }


@router.get("/vat-report")
def get_vat_report(
    company_id: int = Query(..., description="Company ID"),
    start_date: Optional[date] = Query(None, description="Start date for VAT period (YYYY-MM-DD)"),
    end_date: Optional[date] = Query(None, description="End date for VAT period (YYYY-MM-DD)"),
    db: Session = Depends(get_db)
):
    """
    Generate VAT Report (Momsrapport) for a specific period
    Shows outgoing VAT (sales) and incoming VAT (purchases) with net amount to pay/refund

    If no dates provided, shows all-time totals.
    """

    # Get all VAT accounts according to Swedish BAS account plan:
    # - Outgoing VAT (from sales): 2610-2619
    # - Incoming VAT (from purchases): 2640-2649
    vat_accounts = db.query(Account).filter(
        Account.company_id == company_id,
        Account.active == True,
        (
            # Outgoing VAT accounts
            ((Account.account_number >= 2610) & (Account.account_number <= 2619)) |
            # Incoming VAT accounts
            ((Account.account_number >= 2640) & (Account.account_number <= 2649))
        )
    ).all()

    # Categorize accounts
    outgoing_vat_accounts = [acc for acc in vat_accounts if 2610 <= acc.account_number <= 2619]
    incoming_vat_accounts = [acc for acc in vat_accounts if 2640 <= acc.account_number <= 2649]

    # Create lookup dict
    accounts_by_number = {acc.account_number: acc for acc in vat_accounts}

    # Build query for transactions
    query = db.query(
        TransactionLine.account_id,
        func.sum(TransactionLine.debit).label('total_debit'),
        func.sum(TransactionLine.credit).label('total_credit')
    ).join(
        Verification, TransactionLine.verification_id == Verification.id
    ).filter(
        Verification.company_id == company_id,
        TransactionLine.account_id.in_([acc.id for acc in vat_accounts])
    )

    # Apply date filters if provided
    if start_date:
        query = query.filter(Verification.transaction_date >= start_date)
    if end_date:
        query = query.filter(Verification.transaction_date <= end_date)

    query = query.group_by(TransactionLine.account_id)

    transactions = query.all()

    # Process outgoing VAT (credit balance = sales tax collected)
    outgoing_vat = []
    total_outgoing = Decimal("0")

    for account in outgoing_vat_accounts:
        # Find transactions for this account
        trans = next((t for t in transactions if t.account_id == account.id), None)

        if trans:
            # Outgoing VAT is credit (negative), so credit - debit gives positive amount
            vat_amount = (trans.total_credit or Decimal("0")) - (trans.total_debit or Decimal("0"))

            if vat_amount != 0:
                outgoing_vat.append({
                    "account_number": account.account_number,
                    "name": account.name,
                    "amount": float(vat_amount)
                })
                total_outgoing += vat_amount

    # Process incoming VAT (debit balance = purchase tax paid)
    incoming_vat = []
    total_incoming = Decimal("0")

    for account in incoming_vat_accounts:
        # Find transactions for this account
        trans = next((t for t in transactions if t.account_id == account.id), None)

        if trans:
            # Incoming VAT is debit (positive), so debit - credit gives positive amount
            vat_amount = (trans.total_debit or Decimal("0")) - (trans.total_credit or Decimal("0"))

            if vat_amount != 0:
                incoming_vat.append({
                    "account_number": account.account_number,
                    "name": account.name,
                    "amount": float(vat_amount)
                })
                total_incoming += vat_amount

    # Net VAT = Outgoing - Incoming
    # Positive = Pay to Skatteverket
    # Negative = Refund from Skatteverket
    net_vat = total_outgoing - total_incoming

    return {
        "company_id": company_id,
        "report_type": "vat_report",
        "start_date": start_date.isoformat() if start_date else None,
        "end_date": end_date.isoformat() if end_date else None,
        "outgoing_vat": {
            "accounts": outgoing_vat,
            "total": float(total_outgoing)
        },
        "incoming_vat": {
            "accounts": incoming_vat,
            "total": float(total_incoming)
        },
        "net_vat": float(net_vat),
        "pay_or_refund": "pay" if net_vat > 0 else "refund" if net_vat < 0 else "zero"
    }


@router.get("/vat-periods")
def get_vat_periods(
    company_id: int = Query(..., description="Company ID"),
    year: int = Query(..., description="Year to generate periods for (e.g., 2024)"),
    db: Session = Depends(get_db)
):
    """
    Get all VAT reporting periods for a company in a specific year.
    Returns periods based on company's vat_reporting_period setting (monthly/quarterly/yearly).
    """
    company = db.query(Company).filter(Company.id == company_id).first()
    if not company:
        return {"error": "Company not found", "periods": []}

    periods = []

    if company.vat_reporting_period == VATReportingPeriod.MONTHLY:
        # Generate 12 monthly periods
        for month in range(1, 13):
            # Start date: first day of month
            start = date(year, month, 1)
            # End date: last day of month
            if month == 12:
                end = date(year, 12, 31)
            else:
                end = date(year, month + 1, 1) - timedelta(days=1)

            periods.append({
                "name": f"{year}-{month:02d} (Månad {month})",
                "start_date": start.isoformat(),
                "end_date": end.isoformat(),
                "period_type": "monthly"
            })

    elif company.vat_reporting_period == VATReportingPeriod.QUARTERLY:
        # Generate 4 quarterly periods
        quarters = [
            ("Q1", 1, 3),
            ("Q2", 4, 6),
            ("Q3", 7, 9),
            ("Q4", 10, 12)
        ]

        for quarter_name, start_month, end_month in quarters:
            start = date(year, start_month, 1)
            # End date: last day of last month in quarter
            if end_month == 12:
                end = date(year, 12, 31)
            else:
                end = date(year, end_month + 1, 1) - timedelta(days=1)

            periods.append({
                "name": f"{year} {quarter_name}",
                "start_date": start.isoformat(),
                "end_date": end.isoformat(),
                "period_type": "quarterly"
            })

    elif company.vat_reporting_period == VATReportingPeriod.YEARLY:
        # Generate 1 yearly period
        periods.append({
            "name": f"{year} (Helår)",
            "start_date": date(year, 1, 1).isoformat(),
            "end_date": date(year, 12, 31).isoformat(),
            "period_type": "yearly"
        })

    return {
        "company_id": company_id,
        "year": year,
        "reporting_period": company.vat_reporting_period.value,
        "periods": periods
    }
