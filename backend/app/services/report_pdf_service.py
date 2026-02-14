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
from app.models.customer import Customer, Supplier
from app.models.fiscal_year import FiscalYear
from app.models.invoice import Invoice, SupplierInvoice
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
        "period_start": fiscal_year.start_date.strftime("%Y-%m-%d"),
        "period_end": fiscal_year.end_date.strftime("%Y-%m-%d"),
        "generated_date": date.today().strftime("%Y-%m-%d"),
        "generated_time": date.today().strftime("%H:%M") if False else "",
    }

    return _render_report_pdf("balance_sheet_template.html", context)


# ── Income Statement (Resultaträkning) ──────────────────────────────────────

INCOME_GROUPS = {
    "nettoomsattning": ("Nettoomsättning", 3000, 3799),
    "ovriga_intakter": ("Övriga rörelseintäkter", 3800, 3999),
    "ravaror": ("Råvaror och förnödenheter mm", 4000, 4999),
    "ovriga_externa": ("Övriga externa kostnader", 5000, 6999),
    "personal": ("Personalkostnader", 7000, 7699),
    "avskrivningar": ("Av- och nedskrivningar", 7700, 7899),
    "ovriga_rorelsekostnader": ("Övriga rörelsekostnader", 7900, 7999),
    "fin_intakter": ("Övriga ränteintäkter och liknande resultatposter", 8000, 8399),
    "fin_kostnader": ("Räntekostnader och liknande resultatposter", 8400, 8499),
    "extraordinara": ("Extraordinära poster", 8500, 8699),
    "bokslutsdispositioner": ("Bokslutsdispositioner", 8700, 8899),
    "skatt": ("Skatt", 8900, 8989),
    "arets_resultat_konto": ("Årets resultat", 8990, 8999),
}


def _get_pl_amounts(db: Session, company_id: int, fiscal_year: FiscalYear) -> dict[int, dict]:
    """Get P&L accounts (3000-8999) with negated amounts for income statement display.

    Negation makes revenue positive and expenses negative, matching Swedish convention.
    Returns dict keyed by account_number.
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

    result = {}
    for account in accounts:
        if account.account_number < 3000 or account.account_number > 8999:
            continue
        raw = _get_account_period_change(db, account.id, company_id, fiscal_year.start_date, fiscal_year.end_date)
        amount = -raw  # Negate: revenue positive, expenses negative
        if amount == 0:
            continue
        result[account.account_number] = {
            "account_number": account.account_number,
            "name": account.name,
            "amount": amount,
        }
    return result


def _extract_group(
    current: dict[int, dict],
    prev: dict[int, dict],
    r_min: int,
    r_max: int,
) -> tuple[list[dict], float, float]:
    """Extract accounts in range from current/prev data.

    Returns (accounts_list, current_total, prev_total).
    Each account dict includes period, accumulated, and prev_year.
    """
    accounts = []
    for num in sorted(current):
        if r_min <= num <= r_max:
            acc = current[num]
            accounts.append(
                {
                    "account_number": acc["account_number"],
                    "name": acc["name"],
                    "period": acc["amount"],
                    "accumulated": acc["amount"],
                    "prev_year": prev.get(num, {}).get("amount", 0.0),
                }
            )

    cur_total = sum(a["period"] for a in accounts)
    prev_total = sum(a["prev_year"] for a in accounts)
    return accounts, cur_total, prev_total


def build_income_statement_data(
    db: Session,
    company_id: int,
    fiscal_year: FiscalYear,
) -> dict:
    """Build structured income statement data with row-based layout for PDF."""
    current = _get_pl_amounts(db, company_id, fiscal_year)

    # Previous fiscal year for comparison column
    prev_fy = (
        db.query(FiscalYear)
        .filter(
            FiscalYear.company_id == company_id,
            FiscalYear.end_date < fiscal_year.start_date,
        )
        .order_by(FiscalYear.end_date.desc())
        .first()
    )
    prev = _get_pl_amounts(db, company_id, prev_fy) if prev_fy else {}

    # Build group data
    groups = {}
    for key, (title, r_min, r_max) in INCOME_GROUPS.items():
        accs, cur_total, prev_total = _extract_group(current, prev, r_min, r_max)
        groups[key] = {
            "title": title,
            "accounts": accs,
            "period": cur_total,
            "accumulated": cur_total,
            "prev_year": prev_total,
        }

    # Helper to make amount dict
    def amt(period, prev_year):
        return {"period": period, "accumulated": period, "prev_year": prev_year}

    # Build rows
    rows = []

    def sep():
        rows.append({"type": "separator"})

    def add_group(g):
        if not g["accounts"]:
            return
        rows.append({"type": "group_header", "title": g["title"]})
        for acc in g["accounts"]:
            rows.append({"type": "account", **acc})
        rows.append({"type": "group_sum", "title": f"S:a {g['title']}", **amt(g["period"], g["prev_year"])})
        sep()

    # === Rörelsens intäkter mm ===
    rows.append({"type": "section_header", "title": "Rörelsens intäkter mm"})
    add_group(groups["nettoomsattning"])
    add_group(groups["ovriga_intakter"])

    rev = groups["nettoomsattning"]["period"] + groups["ovriga_intakter"]["period"]
    rev_prev = groups["nettoomsattning"]["prev_year"] + groups["ovriga_intakter"]["prev_year"]
    rows.append({"type": "section_sum", "title": "S:a Rörelseintäkter mm", **amt(rev, rev_prev)})
    sep()

    # === Rörelsens kostnader ===
    rows.append({"type": "section_header", "title": "Rörelsens kostnader"})
    add_group(groups["ravaror"])

    # Bruttovinst (only if COGS exists)
    if groups["ravaror"]["accounts"]:
        bv = rev + groups["ravaror"]["period"]
        bv_prev = rev_prev + groups["ravaror"]["prev_year"]
        rows.append({"type": "intermediate", "title": "Bruttovinst", **amt(bv, bv_prev)})
        sep()

    add_group(groups["ovriga_externa"])
    add_group(groups["personal"])

    # S:a Rörelsens kostnader (before depreciation, excl övriga rörelsekostnader)
    costs_pre_depr = groups["ravaror"]["period"] + groups["ovriga_externa"]["period"] + groups["personal"]["period"]
    costs_pre_depr_prev = (
        groups["ravaror"]["prev_year"] + groups["ovriga_externa"]["prev_year"] + groups["personal"]["prev_year"]
    )
    rows.append(
        {
            "type": "section_sum",
            "title": "S:a Rörelsens kostnader inkl råvaror mm",
            **amt(costs_pre_depr, costs_pre_depr_prev),
        }
    )
    sep()

    # Rörelseresultat före avskrivningar
    rr_fore = rev + costs_pre_depr
    rr_fore_prev = rev_prev + costs_pre_depr_prev
    rows.append({"type": "intermediate", "title": "Rörelseresultat före avskrivningar", **amt(rr_fore, rr_fore_prev)})
    sep()

    # Av- och nedskrivningar
    add_group(groups["avskrivningar"])

    # Övriga rörelsekostnader (7900-7999) — per ÅRL placeras efter avskrivningar
    add_group(groups["ovriga_rorelsekostnader"])

    # Rörelseresultat
    rr = rr_fore + groups["avskrivningar"]["period"] + groups["ovriga_rorelsekostnader"]["period"]
    rr_prev = rr_fore_prev + groups["avskrivningar"]["prev_year"] + groups["ovriga_rorelsekostnader"]["prev_year"]
    rows.append({"type": "intermediate", "title": "Rörelseresultat", **amt(rr, rr_prev)})
    sep()

    # === Resultat från finansiella investeringar ===
    if groups["fin_intakter"]["accounts"] or groups["fin_kostnader"]["accounts"]:
        rows.append({"type": "section_header", "title": "Resultat från finansiella investeringar"})
        add_group(groups["fin_intakter"])
        add_group(groups["fin_kostnader"])
        fin = groups["fin_intakter"]["period"] + groups["fin_kostnader"]["period"]
        fin_prev = groups["fin_intakter"]["prev_year"] + groups["fin_kostnader"]["prev_year"]
        rows.append(
            {"type": "section_sum", "title": "S:a Resultat från finansiella investeringar", **amt(fin, fin_prev)}
        )
        sep()
    else:
        fin, fin_prev = 0.0, 0.0

    # Resultat efter finansiella poster
    res_efter_fin = rr + fin
    res_efter_fin_prev = rr_prev + fin_prev
    rows.append(
        {
            "type": "intermediate",
            "title": "Resultat efter finansiella poster",
            **amt(res_efter_fin, res_efter_fin_prev),
        }
    )
    sep()

    # Extraordinära poster / Bokslutsdispositioner
    bokslut = groups["bokslutsdispositioner"]["period"] + groups["extraordinara"]["period"]
    bokslut_prev = groups["bokslutsdispositioner"]["prev_year"] + groups["extraordinara"]["prev_year"]
    if groups["extraordinara"]["accounts"]:
        add_group(groups["extraordinara"])
    if groups["bokslutsdispositioner"]["accounts"]:
        add_group(groups["bokslutsdispositioner"])

    # Resultat före skatt
    res_fore_skatt = res_efter_fin + bokslut
    res_fore_skatt_prev = res_efter_fin_prev + bokslut_prev

    rows.append({"type": "intermediate", "title": "Resultat före skatt", **amt(res_fore_skatt, res_fore_skatt_prev)})
    sep()

    # Skatt
    if groups["skatt"]["accounts"]:
        rows.append({"type": "section_header", "title": "Skatt"})
        for acc in groups["skatt"]["accounts"]:
            rows.append({"type": "account", **acc})
        rows.append(
            {"type": "group_sum", "title": "S:a Skatt", **amt(groups["skatt"]["period"], groups["skatt"]["prev_year"])}
        )
        sep()

    # Beräknat resultat
    beraknat = res_fore_skatt + groups["skatt"]["period"]
    beraknat_prev = res_fore_skatt_prev + groups["skatt"]["prev_year"]
    rows.append({"type": "final_result", "title": "Beräknat resultat", **amt(beraknat, beraknat_prev)})
    sep()

    # 8999 Årets resultat
    for acc in groups["arets_resultat_konto"]["accounts"]:
        rows.append({"type": "account", **acc})

    return {"rows": rows, "has_prev_year": prev_fy is not None}


def generate_income_statement_pdf(
    db: Session,
    company: Company,
    fiscal_year: FiscalYear,
) -> bytes:
    """Generate Income Statement (Resultaträkning) PDF."""
    data = build_income_statement_data(db, company.id, fiscal_year)
    logo_data = _load_company_logo(company)

    context = {
        "company": company,
        "fiscal_year": fiscal_year,
        "company_logo": logo_data,
        "data": data,
        "period_start": fiscal_year.start_date.strftime("%Y-%m-%d"),
        "period_end": fiscal_year.end_date.strftime("%Y-%m-%d"),
        "generated_date": date.today().strftime("%Y-%m-%d"),
    }

    return _render_report_pdf("income_statement_template.html", context)


# ── General Ledger (Huvudbok) ────────────────────────────────────────────────


def _build_verification_invoice_map(db: Session, verification_ids: list[int]) -> dict[int, str]:
    """Build a map of verification_id -> transinfo string for invoice references."""
    if not verification_ids:
        return {}

    result = {}

    # Customer invoices (Kundfakturor)
    invoices = (
        db.query(Invoice, Customer)
        .join(Customer, Invoice.customer_id == Customer.id)
        .filter(Invoice.invoice_verification_id.in_(verification_ids))
        .all()
    )
    for inv, cust in invoices:
        result[inv.invoice_verification_id] = f"Faktnr: {inv.invoice_number}, Namn: {cust.name}"

    # Customer invoice payments
    payment_invoices = (
        db.query(Invoice, Customer)
        .join(Customer, Invoice.customer_id == Customer.id)
        .filter(Invoice.payment_verification_id.in_(verification_ids))
        .all()
    )
    for inv, cust in payment_invoices:
        if inv.payment_verification_id not in result:
            result[inv.payment_verification_id] = f"Faktnr: {inv.invoice_number}, Namn: {cust.name}"

    # Supplier invoices (Leverantörsfakturor)
    supplier_invoices = (
        db.query(SupplierInvoice, Supplier)
        .join(Supplier, SupplierInvoice.supplier_id == Supplier.id)
        .filter(SupplierInvoice.invoice_verification_id.in_(verification_ids))
        .all()
    )
    for sinv, supp in supplier_invoices:
        result[sinv.invoice_verification_id] = (
            f"LevFktnr: {sinv.our_invoice_number or sinv.supplier_invoice_number}, Namn: {supp.name}"
        )

    # Supplier invoice payments
    supplier_payments = (
        db.query(SupplierInvoice, Supplier)
        .join(Supplier, SupplierInvoice.supplier_id == Supplier.id)
        .filter(SupplierInvoice.payment_verification_id.in_(verification_ids))
        .all()
    )
    for sinv, supp in supplier_payments:
        if sinv.payment_verification_id not in result:
            result[sinv.payment_verification_id] = (
                f"LevFktnr: {sinv.our_invoice_number or sinv.supplier_invoice_number}, Namn: {supp.name}"
            )

    return result


def build_general_ledger_data(
    db: Session,
    company_id: int,
    fiscal_year: FiscalYear,
) -> dict:
    """Build detailed general ledger data with per-account transactions."""
    date_start = fiscal_year.start_date
    date_end = fiscal_year.end_date

    # Get all active accounts for this fiscal year
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

    # Collect all verification IDs across all accounts for batch invoice lookup
    all_verification_ids = set()
    account_transactions_raw = {}

    for account in accounts:
        transactions = (
            db.query(TransactionLine, Verification)
            .join(Verification, TransactionLine.verification_id == Verification.id)
            .filter(
                TransactionLine.account_id == account.id,
                Verification.company_id == company_id,
                Verification.transaction_date >= date_start,
                Verification.transaction_date <= date_end,
            )
            .order_by(Verification.transaction_date, Verification.verification_number)
            .all()
        )

        # Calculate opening balance
        is_balance_account = account.account_number < 3000
        if is_balance_account:
            opening_balance = float(account.opening_balance or Decimal(0))
        else:
            opening_balance = 0.0

        # Skip accounts with no transactions and no opening balance
        if not transactions and opening_balance == 0:
            continue

        for _tl, ver in transactions:
            all_verification_ids.add(ver.id)

        account_transactions_raw[account.id] = {
            "account": account,
            "opening_balance": opening_balance,
            "transactions": transactions,
        }

    # Batch lookup invoice references
    invoice_map = _build_verification_invoice_map(db, list(all_verification_ids))

    # Build structured data
    account_data = []
    min_account = None
    max_account = None
    max_vernr = None

    for _account_id, raw in account_transactions_raw.items():
        account = raw["account"]
        opening_balance = raw["opening_balance"]
        transactions = raw["transactions"]

        if min_account is None or account.account_number < min_account:
            min_account = account.account_number
        if max_account is None or account.account_number > max_account:
            max_account = account.account_number

        # Build transaction rows with running balance
        running_balance = opening_balance
        total_debit = 0.0
        total_credit = 0.0
        tx_rows = []

        for tl, ver in transactions:
            debit = float(tl.debit or Decimal(0))
            credit = float(tl.credit or Decimal(0))
            running_balance += debit - credit
            total_debit += debit
            total_credit += credit

            vernr = f"{ver.series}{ver.verification_number}"
            if max_vernr is None:
                max_vernr = vernr
            else:
                max_vernr = vernr  # Last one processed is highest

            tx_rows.append(
                {
                    "vernr": vernr,
                    "date": ver.transaction_date.strftime("%y-%m-%d"),
                    "text": ver.description or "",
                    "transinfo": invoice_map.get(ver.id),
                    "debit": debit,
                    "credit": credit,
                    "balance": running_balance,
                }
            )

        closing_balance = opening_balance + total_debit - total_credit

        account_data.append(
            {
                "account_number": account.account_number,
                "name": account.name,
                "opening_balance": opening_balance,
                "transactions": tx_rows,
                "total_debit": total_debit,
                "total_credit": total_credit,
                "closing_balance": closing_balance,
            }
        )

    grand_total_debit = sum(a["total_debit"] for a in account_data)
    grand_total_credit = sum(a["total_credit"] for a in account_data)

    return {
        "accounts": account_data,
        "account_count": len(account_data),
        "min_account": min_account or 1010,
        "max_account": max_account or 8999,
        "max_vernr": max_vernr or "",
        "grand_total_debit": grand_total_debit,
        "grand_total_credit": grand_total_credit,
    }


def generate_general_ledger_pdf(
    db: Session,
    company: Company,
    fiscal_year: FiscalYear,
) -> bytes:
    """Generate General Ledger (Huvudbok) PDF."""
    data = build_general_ledger_data(db, company.id, fiscal_year)
    logo_data = _load_company_logo(company)

    context = {
        "company": company,
        "fiscal_year": fiscal_year,
        "company_logo": logo_data,
        "data": data,
        "period_start": fiscal_year.start_date.strftime("%Y-%m-%d"),
        "period_end": fiscal_year.end_date.strftime("%Y-%m-%d"),
        "generated_date": date.today().strftime("%Y-%m-%d"),
    }

    return _render_report_pdf("general_ledger_template.html", context)
