import os
from datetime import date
from decimal import Decimal
from pathlib import Path

from fastapi import HTTPException
from jinja2 import Environment, FileSystemLoader
from sqlalchemy import func
from sqlalchemy.orm import Session
from weasyprint import HTML

from app.models.account import Account, AccountType
from app.models.company import Company
from app.models.fiscal_year import FiscalYear
from app.models.verification import TransactionLine, Verification
from app.services.pdf_service import format_sek

# BAS 2024 account groupings for balance sheet
ASSET_GROUPS = [
    {
        "title": "Anläggningstillgångar",
        "range": (1000, 1399),
        "subgroups": [
            ("Immateriella anläggningstillgångar", 1000, 1099),
            ("Materiella anläggningstillgångar", 1100, 1299),
            ("Finansiella anläggningstillgångar", 1300, 1399),
        ],
    },
    {
        "title": "Omsättningstillgångar",
        "range": (1400, 1999),
        "subgroups": [
            ("Varulager m.m.", 1400, 1499),
            ("Fordringar", 1500, 1799),
            ("Kortfristiga placeringar", 1800, 1899),
            ("Kassa och bank", 1900, 1999),
        ],
    },
]

EQUITY_LIABILITY_GROUPS = [
    {
        "title": "Eget kapital",
        "range": (2000, 2099),
        "subgroups": [],
    },
    {
        "title": "Obeskattade reserver",
        "range": (2100, 2199),
        "subgroups": [],
    },
    {
        "title": "Avsättningar",
        "range": (2200, 2299),
        "subgroups": [],
    },
    {
        "title": "Långfristiga skulder",
        "range": (2300, 2399),
        "subgroups": [],
    },
    {
        "title": "Kortfristiga skulder",
        "range": (2400, 2999),
        "subgroups": [],
    },
]


def _load_company_logo(company: Company) -> str | None:
    """Load company logo as base64 data URI."""
    if not company.logo_filename:
        return None
    logo_path = f"/app/uploads/logos/{company.logo_filename}"
    if not os.path.exists(logo_path):
        return None
    import base64

    with open(logo_path, "rb") as logo_file:
        logo_data = base64.b64encode(logo_file.read()).decode("utf-8")
        extension = company.logo_filename.split(".")[-1].lower()
        mime_type = "image/png" if extension == "png" else "image/jpeg"
        return f"data:{mime_type};base64,{logo_data}"


def _render_report_pdf(template_name: str, context: dict) -> bytes:
    """Render a report template to PDF bytes using WeasyPrint."""
    template_dir = Path(__file__).parent.parent / "templates"
    env = Environment(loader=FileSystemLoader(str(template_dir)))
    env.filters["format_sek"] = format_sek

    template = env.get_template(template_name)
    html_content = template.render(**context)

    try:
        return HTML(string=html_content).write_pdf()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"PDF generation failed: {str(e)}") from e


def _get_account_period_change(
    db: Session,
    account_id: int,
    company_id: int,
    start_date: date,
    end_date: date,
) -> float:
    """Calculate net debit - credit for an account in a date range."""
    result = (
        db.query(func.sum(TransactionLine.debit - TransactionLine.credit))
        .join(Verification, TransactionLine.verification_id == Verification.id)
        .filter(
            TransactionLine.account_id == account_id,
            Verification.company_id == company_id,
            Verification.transaction_date >= start_date,
            Verification.transaction_date <= end_date,
        )
        .scalar()
    )
    return float(result or Decimal(0))


def _build_grouped_data(
    accounts_data: list[dict],
    groups: list[dict],
) -> list[dict]:
    """
    Group accounts into BAS hierarchy.
    Only includes groups/subgroups that have accounts with non-zero balances.
    """
    result = []

    for group in groups:
        g_min, g_max = group["range"]
        group_accounts = [a for a in accounts_data if g_min <= a["account_number"] <= g_max]

        if not group_accounts:
            continue

        group_entry = {
            "title": group["title"],
            "subgroups": [],
            "ib_total": 0.0,
            "period_total": 0.0,
            "ub_total": 0.0,
        }

        if group["subgroups"]:
            for sg_name, sg_min, sg_max in group["subgroups"]:
                sg_accounts = [a for a in group_accounts if sg_min <= a["account_number"] <= sg_max]
                if not sg_accounts:
                    continue

                sg_ib = sum(a["ib"] for a in sg_accounts)
                sg_period = sum(a["period"] for a in sg_accounts)
                sg_ub = sum(a["ub"] for a in sg_accounts)

                group_entry["subgroups"].append(
                    {
                        "title": sg_name,
                        "accounts": sg_accounts,
                        "ib_total": sg_ib,
                        "period_total": sg_period,
                        "ub_total": sg_ub,
                    }
                )

                group_entry["ib_total"] += sg_ib
                group_entry["period_total"] += sg_period
                group_entry["ub_total"] += sg_ub
        else:
            # No subgroups — accounts directly under group
            group_entry["subgroups"].append(
                {
                    "title": None,
                    "accounts": group_accounts,
                    "ib_total": sum(a["ib"] for a in group_accounts),
                    "period_total": sum(a["period"] for a in group_accounts),
                    "ub_total": sum(a["ub"] for a in group_accounts),
                }
            )
            group_entry["ib_total"] = group_entry["subgroups"][0]["ib_total"]
            group_entry["period_total"] = group_entry["subgroups"][0]["period_total"]
            group_entry["ub_total"] = group_entry["subgroups"][0]["ub_total"]

        result.append(group_entry)

    return result


def build_balance_sheet_data(
    db: Session,
    company_id: int,
    fiscal_year: FiscalYear,
) -> dict:
    """
    Build detailed balance sheet data with IB/Period/UB columns
    and hierarchical BAS account grouping.
    """
    accounts = (
        db.query(Account)
        .filter(
            Account.company_id == company_id,
            Account.fiscal_year_id == fiscal_year.id,
            Account.active.is_(True),
        )
        .order_by(Account.account_number)
        .all()
    )

    asset_accounts = []
    equity_liability_accounts = []
    revenue_expense_total_ib = 0.0
    revenue_expense_total_period = 0.0

    for account in accounts:
        period_change = _get_account_period_change(
            db, account.id, company_id, fiscal_year.start_date, fiscal_year.end_date
        )
        ib = float(account.opening_balance)
        ub = ib + period_change

        # Skip accounts with all zeros
        if ib == 0 and period_change == 0 and ub == 0:
            continue

        account_data = {
            "account_number": account.account_number,
            "name": account.name,
            "ib": ib,
            "period": period_change,
            "ub": ub,
        }

        if account.account_type == AccountType.ASSET:
            asset_accounts.append(account_data)
        elif account.account_type == AccountType.EQUITY_LIABILITY:
            equity_liability_accounts.append(account_data)
        elif account.account_type in [
            AccountType.REVENUE,
            AccountType.COST_GOODS,
            AccountType.COST_LOCAL,
            AccountType.COST_OTHER,
            AccountType.COST_PERSONNEL,
            AccountType.COST_MISC,
        ]:
            revenue_expense_total_ib += ib
            revenue_expense_total_period += period_change

    # Build grouped data
    asset_groups = _build_grouped_data(asset_accounts, ASSET_GROUPS)
    equity_liability_groups = _build_grouped_data(equity_liability_accounts, EQUITY_LIABILITY_GROUPS)

    # Totals
    total_assets_ib = sum(g["ib_total"] for g in asset_groups)
    total_assets_period = sum(g["period_total"] for g in asset_groups)
    total_assets_ub = sum(g["ub_total"] for g in asset_groups)

    total_el_ib = sum(g["ib_total"] for g in equity_liability_groups)
    total_el_period = sum(g["period_total"] for g in equity_liability_groups)
    total_el_ub = sum(g["ub_total"] for g in equity_liability_groups)

    # Årets resultat is included in the P&L accounts (3xxx-8xxx)
    # In a balance report, it shows as: IB from result accounts + period changes
    arets_resultat_ib = revenue_expense_total_ib
    arets_resultat_period = revenue_expense_total_period
    arets_resultat_ub = arets_resultat_ib + arets_resultat_period

    # Grand totals for equity+liabilities side (includes årets resultat)
    grand_el_ib = total_el_ib + arets_resultat_ib
    grand_el_period = total_el_period + arets_resultat_period
    grand_el_ub = total_el_ub + arets_resultat_ub

    # Beräknat resultat (should be 0 if balanced)
    beraknat_ib = total_assets_ib + grand_el_ib
    beraknat_period = total_assets_period + grand_el_period
    beraknat_ub = total_assets_ub + grand_el_ub

    return {
        "asset_groups": asset_groups,
        "equity_liability_groups": equity_liability_groups,
        "total_assets": {"ib": total_assets_ib, "period": total_assets_period, "ub": total_assets_ub},
        "total_equity_liabilities": {"ib": grand_el_ib, "period": grand_el_period, "ub": grand_el_ub},
        "arets_resultat": {
            "ib": arets_resultat_ib,
            "period": arets_resultat_period,
            "ub": arets_resultat_ub,
        },
        "beraknat_resultat": {"ib": beraknat_ib, "period": beraknat_period, "ub": beraknat_ub},
        "balanced": abs(beraknat_ub) < 0.01,
    }


def generate_balance_sheet_pdf(
    db: Session,
    company: Company,
    fiscal_year: FiscalYear,
) -> bytes:
    """Generate Balance Sheet (Balansrapport) PDF."""
    data = build_balance_sheet_data(db, company.id, fiscal_year)
    logo_data = _load_company_logo(company)

    context = {
        "company": company,
        "fiscal_year": fiscal_year,
        "company_logo": logo_data,
        "data": data,
        "period_start": fiscal_year.start_date.strftime("%y-%m-%d"),
        "period_end": fiscal_year.end_date.strftime("%y-%m-%d"),
        "generated_date": date.today().strftime("%y-%m-%d"),
        "generated_time": date.today().strftime("%H:%M") if False else "",
    }

    return _render_report_pdf("balance_sheet_template.html", context)
