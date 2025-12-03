from fastapi import APIRouter, Depends, Query, Response, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import Dict, List, Optional
from decimal import Decimal
from datetime import date, datetime, timedelta
import xml.etree.ElementTree as ET
from app.database import get_db
from app.models.account import Account, AccountType
from app.models.verification import Verification, TransactionLine
from app.models.company import Company, VATReportingPeriod

router = APIRouter()


@router.get("/balance-sheet")
def get_balance_sheet(
    company_id: int = Query(..., description="Company ID"),
    fiscal_year_id: int = Query(..., description="Fiscal Year ID"),
    db: Session = Depends(get_db)
):
    """
    Generate Balance Sheet (Balansräkning) for a specific fiscal year
    Assets = Liabilities + Equity + Current Year Result
    """

    # Get all accounts with balances for this fiscal year
    accounts = db.query(Account).filter(
        Account.company_id == company_id,
        Account.fiscal_year_id == fiscal_year_id,
        Account.active == True
    ).all()

    # Group by account type
    assets = []
    liabilities = []
    equity = []
    revenue_accounts = []
    cost_accounts = []

    for account in accounts:
        balance = float(account.current_balance)

        item = {
            "account_number": account.account_number,
            "name": account.name,
            "balance": balance
        }

        if account.account_type == AccountType.ASSET:
            assets.append(item)
        elif account.account_type == AccountType.EQUITY_LIABILITY:
            # 2000-2099: Equity, 2100-2999: Liabilities
            if 2000 <= account.account_number < 2100:
                equity.append(item)
            else:
                liabilities.append(item)
        elif account.account_type == AccountType.REVENUE:
            revenue_accounts.append(account)
        elif account.account_type in [
            AccountType.COST_GOODS,
            AccountType.COST_LOCAL,
            AccountType.COST_OTHER,
            AccountType.COST_PERSONNEL,
            AccountType.COST_MISC
        ]:
            cost_accounts.append(account)

    # Calculate current year result
    total_revenue = sum(abs(float(acc.current_balance)) for acc in revenue_accounts)
    total_costs = sum(float(acc.current_balance) for acc in cost_accounts)
    current_year_result = total_revenue - total_costs

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
        "current_year_result": current_year_result,
        "total_liabilities_and_equity": total_liabilities + total_equity + current_year_result,
        "balanced": abs(total_assets - (total_liabilities + total_equity + current_year_result)) < 0.01
    }


@router.get("/income-statement")
def get_income_statement(
    company_id: int = Query(..., description="Company ID"),
    fiscal_year_id: int = Query(..., description="Fiscal Year ID"),
    db: Session = Depends(get_db)
):
    """
    Generate Income Statement (Resultaträkning) for a specific fiscal year
    Revenue - Expenses = Profit/Loss
    """

    # Get all revenue and expense accounts for this fiscal year
    accounts = db.query(Account).filter(
        Account.company_id == company_id,
        Account.fiscal_year_id == fiscal_year_id,
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
        balance = float(account.current_balance)

        item = {
            "account_number": account.account_number,
            "name": account.name,
            # Revenue stored as negative (credit), show as positive
            "balance": abs(balance) if account.account_type == AccountType.REVENUE else balance
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
    fiscal_year_id: int = Query(..., description="Fiscal Year ID"),
    db: Session = Depends(get_db)
):
    """
    Generate Trial Balance (Råbalans/RAR) for a specific fiscal year
    Shows all accounts with opening balance, changes, and closing balance
    """

    accounts = db.query(Account).filter(
        Account.company_id == company_id,
        Account.fiscal_year_id == fiscal_year_id,
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
    fiscal_year_id: int = Query(..., description="Fiscal Year ID"),
    start_date: Optional[date] = Query(None, description="Start date for VAT period (YYYY-MM-DD)"),
    end_date: Optional[date] = Query(None, description="End date for VAT period (YYYY-MM-DD)"),
    exclude_vat_settlements: bool = Query(False, description="Exclude VAT settlement/declaration entries"),
    db: Session = Depends(get_db)
):
    """
    Generate VAT Report (Momsrapport) for a specific fiscal year and period
    Shows outgoing VAT (sales) and incoming VAT (purchases) with net amount to pay/refund

    If no dates provided, shows all-time totals for the fiscal year.
    If exclude_vat_settlements is True, filters out verifications that appear to be VAT settlements
    (e.g., entries that zero out VAT accounts when filing declarations).
    """

    # Get all VAT accounts according to Swedish BAS account plan:
    # - Outgoing VAT (from sales): 2610-2619
    # - Incoming VAT (from purchases): 2640-2649
    # Note: We don't filter on active=True because we want to include inactive accounts
    # that still have transactions (e.g., from imported historical data)
    vat_accounts = db.query(Account).filter(
        Account.company_id == company_id,
        Account.fiscal_year_id == fiscal_year_id,
        (
            # Outgoing VAT accounts
            ((Account.account_number >= 2610) & (Account.account_number <= 2619)) |
            # Incoming VAT accounts
            ((Account.account_number >= 2640) & (Account.account_number <= 2649))
        )
    ).all()

    # Debug logging
    import logging
    logger = logging.getLogger(__name__)
    logger.info(f"VAT Report - Found {len(vat_accounts)} VAT accounts for company {company_id}")
    for acc in vat_accounts:
        logger.info(f"  VAT Account: {acc.account_number} - {acc.name}")

    # Categorize accounts
    outgoing_vat_accounts = [acc for acc in vat_accounts if 2610 <= acc.account_number <= 2619]
    incoming_vat_accounts = [acc for acc in vat_accounts if 2640 <= acc.account_number <= 2649]

    logger.info(f"VAT Report - {len(outgoing_vat_accounts)} outgoing, {len(incoming_vat_accounts)} incoming")
    logger.info(f"VAT Report - Date filter: {start_date} to {end_date}")

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

    # Exclude VAT settlement verifications if requested
    if exclude_vat_settlements:
        # Filter out verifications that appear to be VAT settlements/declarations
        # Strategy: Exclude verifications that contain BOTH VAT accounts (2610-2649)
        # AND VAT receivable/payable accounts (2650, 2660)
        # These are typically used when settling VAT with Skatteverket

        # Find verification IDs that contain settlement accounts
        settlement_accounts = db.query(Account.id).filter(
            Account.company_id == company_id,
            Account.fiscal_year_id == fiscal_year_id,
            Account.account_number.in_([2650, 2660])  # Momsfordran, Momsskuld
        ).all()

        if settlement_accounts:
            settlement_account_ids = [acc.id for acc in settlement_accounts]

            # Find verifications that have transactions to settlement accounts
            settlement_verification_ids = db.query(TransactionLine.verification_id).filter(
                TransactionLine.account_id.in_(settlement_account_ids)
            ).distinct().all()

            settlement_ver_ids = [v.verification_id for v in settlement_verification_ids]

            if settlement_ver_ids:
                # Exclude these verifications from our query
                query = query.filter(~Verification.id.in_(settlement_ver_ids))
                logger.info(f"VAT Report - Excluding {len(settlement_ver_ids)} settlement verifications")

    query = query.group_by(TransactionLine.account_id)

    transactions = query.all()

    logger.info(f"VAT Report - Found {len(transactions)} transaction groups")

    # Get account details for all transactions (even those not in our VAT ranges)
    all_account_ids = [t.account_id for t in transactions]
    all_trans_accounts = db.query(Account).filter(Account.id.in_(all_account_ids)).all()
    trans_accounts_by_id = {acc.id: acc for acc in all_trans_accounts}

    for trans in transactions:
        acc = trans_accounts_by_id.get(trans.account_id)
        if acc:
            logger.info(f"  Account {acc.account_number} ({acc.name}): Debit={trans.total_debit}, Credit={trans.total_credit}")

    # Process outgoing VAT (credit balance = sales tax collected)
    outgoing_vat = []
    total_outgoing = Decimal("0")

    # Track by VAT rate for SKV 3800 form
    outgoing_by_rate = {
        "25": {"vat": Decimal("0"), "accounts": []},
        "12": {"vat": Decimal("0"), "accounts": []},
        "6": {"vat": Decimal("0"), "accounts": []}
    }

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

                # Categorize by VAT rate based on account number
                # 2611: 25%, 2621: 12%, 2631/2615: 6%
                if account.account_number == 2611:
                    outgoing_by_rate["25"]["vat"] += vat_amount
                    outgoing_by_rate["25"]["accounts"].append(account.account_number)
                elif account.account_number == 2621:
                    outgoing_by_rate["12"]["vat"] += vat_amount
                    outgoing_by_rate["12"]["accounts"].append(account.account_number)
                elif account.account_number in [2631, 2615]:
                    outgoing_by_rate["6"]["vat"] += vat_amount
                    outgoing_by_rate["6"]["accounts"].append(account.account_number)

    # Process incoming VAT (debit balance = purchase tax paid)
    incoming_vat = []
    total_incoming = Decimal("0")

    # Track by VAT rate
    incoming_by_rate = {
        "25": {"vat": Decimal("0"), "accounts": []},
        "12": {"vat": Decimal("0"), "accounts": []},
        "6": {"vat": Decimal("0"), "accounts": []}
    }

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

                # Categorize by VAT rate based on account number
                # 2641: 25%, 2645: 12%, 2647: 6%
                if account.account_number == 2641:
                    incoming_by_rate["25"]["vat"] += vat_amount
                    incoming_by_rate["25"]["accounts"].append(account.account_number)
                elif account.account_number == 2645:
                    incoming_by_rate["12"]["vat"] += vat_amount
                    incoming_by_rate["12"]["accounts"].append(account.account_number)
                elif account.account_number == 2647:
                    incoming_by_rate["6"]["vat"] += vat_amount
                    incoming_by_rate["6"]["accounts"].append(account.account_number)

    # Net VAT = Outgoing - Incoming
    # Positive = Pay to Skatteverket
    # Negative = Refund from Skatteverket
    net_vat = total_outgoing - total_incoming

    # Prepare SKV 3800 form data (Swedish VAT declaration form)
    skv_3800 = {
        "outgoing_25": {
            "vat": float(outgoing_by_rate["25"]["vat"]),
            "sales": float(outgoing_by_rate["25"]["vat"] / Decimal("0.25")) if outgoing_by_rate["25"]["vat"] != 0 else 0.0,
            "box_sales": "05",  # Ruta för försäljning
            "box_vat": "06"     # Ruta för moms
        },
        "outgoing_12": {
            "vat": float(outgoing_by_rate["12"]["vat"]),
            "sales": float(outgoing_by_rate["12"]["vat"] / Decimal("0.12")) if outgoing_by_rate["12"]["vat"] != 0 else 0.0,
            "box_sales": "07",
            "box_vat": "08"
        },
        "outgoing_6": {
            "vat": float(outgoing_by_rate["6"]["vat"]),
            "sales": float(outgoing_by_rate["6"]["vat"] / Decimal("0.06")) if outgoing_by_rate["6"]["vat"] != 0 else 0.0,
            "box_sales": "09",
            "box_vat": "10"
        },
        "incoming_total": {
            "vat": float(total_incoming),
            "box": "30"  # Ruta för ingående moms
        },
        "net_vat": {
            "amount": float(net_vat),
            "box": "48"  # Ruta för moms att betala/få tillbaka
        }
    }

    # Fetch detailed verifications for debug purposes
    verification_details = []
    if transactions:
        # Get all unique verification IDs from our filtered transactions
        verification_ids = db.query(TransactionLine.verification_id).join(
            Verification, TransactionLine.verification_id == Verification.id
        ).filter(
            Verification.company_id == company_id,
            TransactionLine.account_id.in_([acc.id for acc in vat_accounts])
        )

        # Apply same filters as main query
        if start_date:
            verification_ids = verification_ids.filter(Verification.transaction_date >= start_date)
        if end_date:
            verification_ids = verification_ids.filter(Verification.transaction_date <= end_date)

        # Apply settlement exclusion
        if exclude_vat_settlements:
            settlement_accounts = db.query(Account.id).filter(
                Account.company_id == company_id,
                Account.account_number.in_([2650, 2660])
            ).all()

            if settlement_accounts:
                settlement_account_ids = [acc.id for acc in settlement_accounts]
                settlement_verification_ids = db.query(TransactionLine.verification_id).filter(
                    TransactionLine.account_id.in_(settlement_account_ids)
                ).distinct().all()
                settlement_ver_ids = [v.verification_id for v in settlement_verification_ids]

                if settlement_ver_ids:
                    verification_ids = verification_ids.filter(~Verification.id.in_(settlement_ver_ids))

        verification_ids = verification_ids.distinct().all()
        ver_ids = [v.verification_id for v in verification_ids]

        # Fetch full verification details
        verifications = db.query(Verification).filter(Verification.id.in_(ver_ids)).order_by(
            Verification.transaction_date.desc()
        ).all()

        for ver in verifications:
            # Get ALL transaction lines for this verification (not just VAT)
            all_trans = db.query(TransactionLine).filter(
                TransactionLine.verification_id == ver.id
            ).all()

            # Get all accounts for these transactions
            all_account_ids = [tl.account_id for tl in all_trans]
            all_accounts = db.query(Account).filter(Account.id.in_(all_account_ids)).all()
            accounts_dict = {acc.id: acc for acc in all_accounts}

            # VAT account IDs for marking
            vat_account_ids = {acc.id for acc in vat_accounts}

            transaction_lines = []
            for tl in all_trans:
                acc = accounts_dict.get(tl.account_id)
                if acc:
                    transaction_lines.append({
                        "account_number": acc.account_number,
                        "account_name": acc.name,
                        "debit": float(tl.debit),
                        "credit": float(tl.credit),
                        "is_vat_account": tl.account_id in vat_account_ids
                    })

            verification_details.append({
                "id": ver.id,
                "verification_number": ver.verification_number,
                "series": ver.series,
                "transaction_date": ver.transaction_date.isoformat(),
                "description": ver.description or "",
                "transaction_lines": transaction_lines
            })

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
        "pay_or_refund": "pay" if net_vat > 0 else "refund" if net_vat < 0 else "zero",
        "skv_3800": skv_3800,
        "debug_info": {
            "total_vat_accounts_found": len(vat_accounts),
            "outgoing_vat_accounts": [{"number": acc.account_number, "name": acc.name} for acc in outgoing_vat_accounts],
            "incoming_vat_accounts": [{"number": acc.account_number, "name": acc.name} for acc in incoming_vat_accounts],
            "transaction_groups_found": len(transactions),
            "accounts_with_transactions": [
                {
                    "number": trans_accounts_by_id[t.account_id].account_number,
                    "name": trans_accounts_by_id[t.account_id].name,
                    "debit": float(t.total_debit or 0),
                    "credit": float(t.total_credit or 0)
                }
                for t in transactions if t.account_id in trans_accounts_by_id
            ],
            "verifications": verification_details
        }
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


@router.get("/vat-debug")
def get_vat_debug(
    company_id: int = Query(..., description="Company ID"),
    fiscal_year_id: int = Query(..., description="Fiscal Year ID"),
    start_date: Optional[date] = Query(None, description="Start date (YYYY-MM-DD)"),
    end_date: Optional[date] = Query(None, description="End date (YYYY-MM-DD)"),
    db: Session = Depends(get_db)
):
    """
    Debug endpoint to see what VAT accounts and transactions exist for a fiscal year
    """
    # Get all VAT accounts (including inactive ones) for this fiscal year
    vat_accounts = db.query(Account).filter(
        Account.company_id == company_id,
        Account.fiscal_year_id == fiscal_year_id,
        (
            ((Account.account_number >= 2610) & (Account.account_number <= 2619)) |
            ((Account.account_number >= 2640) & (Account.account_number <= 2649))
        )
    ).all()

    # Get all verifications with dates
    query = db.query(Verification).filter(
        Verification.company_id == company_id
    )

    if start_date:
        query = query.filter(Verification.transaction_date >= start_date)
    if end_date:
        query = query.filter(Verification.transaction_date <= end_date)

    verifications = query.all()

    # Get transaction lines for VAT accounts
    vat_account_ids = [acc.id for acc in vat_accounts]

    trans_query = db.query(TransactionLine).join(
        Verification, TransactionLine.verification_id == Verification.id
    ).filter(
        Verification.company_id == company_id,
        TransactionLine.account_id.in_(vat_account_ids) if vat_account_ids else False
    )

    if start_date:
        trans_query = trans_query.filter(Verification.transaction_date >= start_date)
    if end_date:
        trans_query = trans_query.filter(Verification.transaction_date <= end_date)

    vat_transactions = trans_query.all()

    return {
        "vat_accounts": [
            {
                "id": acc.id,
                "account_number": acc.account_number,
                "name": acc.name,
                "current_balance": float(acc.current_balance)
            }
            for acc in vat_accounts
        ],
        "total_verifications": len(verifications),
        "verification_date_range": {
            "earliest": min([v.transaction_date.isoformat() for v in verifications]) if verifications else None,
            "latest": max([v.transaction_date.isoformat() for v in verifications]) if verifications else None,
        } if verifications else None,
        "vat_transactions": [
            {
                "account_id": t.account_id,
                "verification_id": t.verification_id,
                "debit": float(t.debit),
                "credit": float(t.credit),
                "verification_date": db.query(Verification).filter(Verification.id == t.verification_id).first().transaction_date.isoformat()
            }
            for t in vat_transactions[:50]  # Limit to first 50
        ],
        "total_vat_transactions": len(vat_transactions),
        "filters": {
            "start_date": start_date.isoformat() if start_date else None,
            "end_date": end_date.isoformat() if end_date else None,
        }
    }


@router.get("/vat-report-xml")
def export_vat_report_xml(
    company_id: int = Query(..., description="Company ID"),
    start_date: date = Query(..., description="Start date for VAT period (YYYY-MM-DD)"),
    end_date: date = Query(..., description="End date for VAT period (YYYY-MM-DD)"),
    exclude_vat_settlements: bool = Query(True, description="Exclude VAT settlement/declaration entries"),
    db: Session = Depends(get_db)
):
    """
    Export VAT report as XML file for upload to Skatteverket (eSKDUpload format version 6.0)
    Returns an XML file that can be uploaded directly to Swedish Tax Agency.
    """

    # Get company info for org number
    company = db.query(Company).filter(Company.id == company_id).first()
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")

    # Get the VAT report data (reuse existing logic)
    vat_report_response = get_vat_report(
        company_id=company_id,
        start_date=start_date,
        end_date=end_date,
        exclude_vat_settlements=exclude_vat_settlements,
        db=db
    )

    skv = vat_report_response["skv_3800"]

    # Format period as YYYYMM (use end date)
    period = end_date.strftime("%Y%m")

    # Convert amounts to integers (öre to whole kronor, rounded)
    def to_int(amount: float) -> int:
        return int(round(amount))

    # Create XML structure
    root = ET.Element("eSKDUpload", Version="6.0")

    # Organization number (format: xxxxxx-xxxx)
    org_nr = ET.SubElement(root, "OrgNr")
    org_nr.text = company.org_number if company.org_number else ""

    # Moms section
    moms = ET.SubElement(root, "Moms")

    # Period
    period_elem = ET.SubElement(moms, "Period")
    period_elem.text = period

    # Sales and output VAT by rate
    # 25% VAT
    if skv["outgoing_25"]["vat"] > 0:
        # Försäljning 25% (Box 05)
        fors_25 = ET.SubElement(moms, "ForsMomsEjAnnan")
        fors_25.text = str(to_int(skv["outgoing_25"]["sales"]))

        # Utgående moms 25% (Box 10 in SKV naming)
        moms_utg_hog = ET.SubElement(moms, "MomsUtgHog")
        moms_utg_hog.text = str(to_int(skv["outgoing_25"]["vat"]))

    # 12% VAT
    if skv["outgoing_12"]["vat"] > 0:
        # Försäljning 12%
        fors_12_elem = ET.SubElement(moms, "ForsMoms12")
        fors_12_elem.text = str(to_int(skv["outgoing_12"]["sales"]))

        # Utgående moms 12%
        moms_utg_medel = ET.SubElement(moms, "MomsUtgMedel")
        moms_utg_medel.text = str(to_int(skv["outgoing_12"]["vat"]))

    # 6% VAT
    if skv["outgoing_6"]["vat"] > 0:
        # Försäljning 6%
        fors_6_elem = ET.SubElement(moms, "ForsMoms6")
        fors_6_elem.text = str(to_int(skv["outgoing_6"]["sales"]))

        # Utgående moms 6%
        moms_utg_lag = ET.SubElement(moms, "MomsUtgLag")
        moms_utg_lag.text = str(to_int(skv["outgoing_6"]["vat"]))

    # Ingående moms (deductible input VAT)
    if skv["incoming_total"]["vat"] > 0:
        moms_ing_avdr = ET.SubElement(moms, "MomsIngAvdr")
        moms_ing_avdr.text = str(to_int(skv["incoming_total"]["vat"]))

    # Net VAT to pay or refund
    moms_betala = ET.SubElement(moms, "MomsBetala")
    net_vat_amount = to_int(skv["net_vat"]["amount"])
    moms_betala.text = str(net_vat_amount)

    # Pretty print the XML with indentation
    def indent(elem, level=0):
        i = "\n" + level * "  "
        if len(elem):
            if not elem.text or not elem.text.strip():
                elem.text = i + "  "
            if not elem.tail or not elem.tail.strip():
                elem.tail = i
            for child in elem:
                indent(child, level + 1)
            if not child.tail or not child.tail.strip():
                child.tail = i
        else:
            if level and (not elem.tail or not elem.tail.strip()):
                elem.tail = i

    indent(root)

    # Convert to XML string with utf-8 encoding
    xml_bytes = ET.tostring(root, encoding="utf-8", method="xml")
    xml_string = xml_bytes.decode("utf-8")

    # Add DOCTYPE declaration after XML declaration
    doctype = '<!DOCTYPE eSKDUpload PUBLIC "-//Skatteverket, Sweden//DTD Skatteverket eSKDUpload-DTD Version 6.0//SV" "https://www.skatteverket.se/download/18.3f4496fd14864cc5ac99cb1/1415022101213/eSKDUpload_6p0.dtd">\n'

    # Split to insert DOCTYPE after XML declaration
    xml_lines = xml_string.split('\n', 1)
    if len(xml_lines) == 2:
        full_xml = xml_lines[0] + '\n' + doctype + xml_lines[1]
    else:
        full_xml = xml_string

    # Return as downloadable file
    filename = f"momsdeklaration_{company.org_number}_{period}.xml"

    return Response(
        content=full_xml.encode("utf-8"),
        media_type="application/xml",
        headers={
            "Content-Disposition": f"attachment; filename={filename}"
        }
    )


@router.get("/monthly-statistics")
def get_monthly_statistics(
    company_id: int = Query(..., description="Company ID"),
    fiscal_year_id: int = Query(..., description="Fiscal Year ID"),
    year: int = Query(..., description="Year (e.g., 2024)"),
    db: Session = Depends(get_db)
):
    """
    Get monthly revenue and expense statistics for a specific fiscal year.
    Used for dashboard charts to visualize financial performance over time.
    """
    # Get all revenue accounts (3000-3999) for this fiscal year
    revenue_accounts = db.query(Account).filter(
        Account.company_id == company_id,
        Account.fiscal_year_id == fiscal_year_id,
        Account.account_number >= 3000,
        Account.account_number < 4000
    ).all()

    # Get all expense accounts (4000-8999) for this fiscal year
    expense_accounts = db.query(Account).filter(
        Account.company_id == company_id,
        Account.fiscal_year_id == fiscal_year_id,
        Account.account_number >= 4000,
        Account.account_number < 9000
    ).all()

    revenue_account_ids = [acc.id for acc in revenue_accounts]
    expense_account_ids = [acc.id for acc in expense_accounts]

    monthly_data = []

    # Calculate for each month
    for month in range(1, 13):
        # Start and end dates for the month
        start_date = date(year, month, 1)
        if month == 12:
            end_date = date(year, 12, 31)
        else:
            end_date = date(year, month + 1, 1) - timedelta(days=1)

        # Get all transactions for revenue accounts in this month
        if revenue_account_ids:
            revenue_trans = db.query(
                func.sum(TransactionLine.credit - TransactionLine.debit).label('total')
            ).join(
                Verification, TransactionLine.verification_id == Verification.id
            ).filter(
                Verification.company_id == company_id,
                Verification.transaction_date >= start_date,
                Verification.transaction_date <= end_date,
                TransactionLine.account_id.in_(revenue_account_ids)
            ).scalar()
        else:
            revenue_trans = 0

        # Get all transactions for expense accounts in this month
        if expense_account_ids:
            expense_trans = db.query(
                func.sum(TransactionLine.debit - TransactionLine.credit).label('total')
            ).join(
                Verification, TransactionLine.verification_id == Verification.id
            ).filter(
                Verification.company_id == company_id,
                Verification.transaction_date >= start_date,
                Verification.transaction_date <= end_date,
                TransactionLine.account_id.in_(expense_account_ids)
            ).scalar()
        else:
            expense_trans = 0

        revenue = float(revenue_trans or 0)
        expenses = float(expense_trans or 0)
        profit = revenue - expenses

        monthly_data.append({
            "month": month,
            "month_name": start_date.strftime("%b"),  # Jan, Feb, etc.
            "revenue": revenue,
            "expenses": expenses,
            "profit": profit
        })

    # Calculate year-to-date totals
    ytd_revenue = sum(m["revenue"] for m in monthly_data)
    ytd_expenses = sum(m["expenses"] for m in monthly_data)
    ytd_profit = ytd_revenue - ytd_expenses

    return {
        "company_id": company_id,
        "year": year,
        "monthly_data": monthly_data,
        "ytd_totals": {
            "revenue": ytd_revenue,
            "expenses": ytd_expenses,
            "profit": ytd_profit
        }
    }
