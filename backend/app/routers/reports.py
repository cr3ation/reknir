from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import Dict, List
from decimal import Decimal
from app.database import get_db
from app.models.account import Account, AccountType
from app.models.verification import Verification, TransactionLine

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
    db: Session = Depends(get_db)
):
    """
    Generate VAT Report (Momsrapport)
    Shows outgoing VAT (sales) and incoming VAT (purchases) with net amount to pay/refund
    """

    # Outgoing VAT accounts (from sales) - 2611, 2612, 2613
    outgoing_vat_accounts = db.query(Account).filter(
        Account.company_id == company_id,
        Account.account_number.in_([2611, 2612, 2613]),
        Account.active == True
    ).all()

    # Incoming VAT accounts (from purchases) - 2641, 2642, 2643
    incoming_vat_accounts = db.query(Account).filter(
        Account.company_id == company_id,
        Account.account_number.in_([2641, 2642, 2643]),
        Account.active == True
    ).all()

    outgoing_vat = []
    total_outgoing = Decimal("0")

    for account in outgoing_vat_accounts:
        # Outgoing VAT has negative balance (credit)
        vat_amount = abs(account.current_balance)
        outgoing_vat.append({
            "account_number": account.account_number,
            "name": account.name,
            "amount": float(vat_amount)
        })
        total_outgoing += vat_amount

    incoming_vat = []
    total_incoming = Decimal("0")

    for account in incoming_vat_accounts:
        # Incoming VAT has positive balance (debit)
        vat_amount = account.current_balance
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
