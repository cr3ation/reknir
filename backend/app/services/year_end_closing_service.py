"""
Year-end closing (bokslut) logic.

The closing stores the user's answers. Everything shown in the wizard — the traffic
light checks, the computed result, the tax and the postings that will be made — is
derived from (answers, ledger) on every read. Nothing is written to the ledger until
complete_closing runs, which is what makes going back and changing an answer free.
"""

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.account import Account, AccountType
from app.models.company import AccountingBasis, Company, CompanyForm
from app.models.default_account import DefaultAccountType
from app.models.fiscal_year import FiscalYear
from app.models.invoice import Invoice, InvoiceStatus, PaymentStatus, SupplierInvoice
from app.models.verification import TransactionLine, Verification
from app.models.year_end_closing import (
    AdjustmentType,
    ClosingEventType,
    ClosingStatus,
    ClosingStep,
    YearEndAdjustment,
    YearEndClosing,
    YearEndClosingEvent,
)
from app.services import default_account_service

# Swedish corporate income tax (bolagsskatt), unchanged since 2021.
CORPORATE_TAX_RATE = Decimal("0.206")

# Year-end verifications get their own series so they never mix with the running
# bookkeeping. Verification.series is a free String(10), so this costs nothing.
YEAR_END_SERIES = "B"

RESULT_ACCOUNT_TYPES = (
    AccountType.REVENUE,
    AccountType.COST_GOODS,
    AccountType.COST_LOCAL,
    AccountType.COST_OTHER,
    AccountType.COST_PERSONNEL,
    AccountType.COST_MISC,
)

# Company forms whose tax the closing knows how to handle. A partnership is taxed on
# the partners personally and needs a profit allocation reknir does not model.
SUPPORTED_COMPANY_FORMS = (
    CompanyForm.LIMITED_COMPANY,
    CompanyForm.SOLE_TRADER,
    CompanyForm.ECONOMIC_ASSOCIATION,
)


@dataclass(frozen=True)
class AccountSpec:
    """An account the closing needs, and how to create it if the chart lacks it."""

    default_type: str
    number: int
    name: str
    account_type: AccountType


BANK_SPEC = AccountSpec(DefaultAccountType.BANK, 1930, "Företagskonto", AccountType.ASSET)
CASH_SPEC = AccountSpec(DefaultAccountType.CASH, 1910, "Kassa", AccountType.ASSET)

STOCK_BALANCE_SPEC = AccountSpec(DefaultAccountType.INVENTORY_STOCK, 1460, "Lager av handelsvaror", AccountType.ASSET)
STOCK_RESULT_SPEC = AccountSpec(
    DefaultAccountType.INVENTORY_CHANGE, 4990, "Förändring av lager", AccountType.COST_GOODS
)
ACCRUED_EXPENSE_SPEC = AccountSpec(
    DefaultAccountType.ACCRUED_EXPENSE,
    2990,
    "Övriga upplupna kostnader och förutbetalda intäkter",
    AccountType.EQUITY_LIABILITY,
)
PREPAID_EXPENSE_SPEC = AccountSpec(
    DefaultAccountType.PREPAID_EXPENSE,
    1790,
    "Övriga förutbetalda kostnader och upplupna intäkter",
    AccountType.ASSET,
)
ACCRUED_REVENUE_SPEC = AccountSpec(
    DefaultAccountType.ACCRUED_REVENUE,
    1790,
    "Övriga förutbetalda kostnader och upplupna intäkter",
    AccountType.ASSET,
)
PREPAID_REVENUE_SPEC = AccountSpec(
    DefaultAccountType.PREPAID_REVENUE,
    2990,
    "Övriga upplupna kostnader och förutbetalda intäkter",
    AccountType.EQUITY_LIABILITY,
)
DEFAULT_COST_SPEC = AccountSpec(
    DefaultAccountType.EXPENSE_DEFAULT, 6570, "Övriga externa tjänster", AccountType.COST_OTHER
)
DEFAULT_REVENUE_SPEC = AccountSpec(
    DefaultAccountType.REVENUE_0, 3105, "Försäljning varor, momsfri", AccountType.REVENUE
)
TAX_EXPENSE_SPEC = AccountSpec(DefaultAccountType.TAX_EXPENSE, 8910, "Skatt på årets resultat", AccountType.COST_MISC)
TAX_LIABILITY_SPEC = AccountSpec(DefaultAccountType.TAX_LIABILITY, 2510, "Skatteskulder", AccountType.EQUITY_LIABILITY)
YEAR_RESULT_EXPENSE_SPEC = AccountSpec(
    DefaultAccountType.YEAR_RESULT_EXPENSE, 8999, "Årets resultat", AccountType.COST_MISC
)
ACCOUNTS_RECEIVABLE_SPEC = AccountSpec(
    DefaultAccountType.ACCOUNTS_RECEIVABLE, 1510, "Kundfordringar", AccountType.ASSET
)
ACCOUNTS_PAYABLE_SPEC = AccountSpec(
    DefaultAccountType.ACCOUNTS_PAYABLE, 2440, "Leverantörsskulder", AccountType.EQUITY_LIABILITY
)

# Which accounts each adjustment kind posts against. The balance side is fixed by the
# kind; the result side is a sensible default the user may override per adjustment.
ADJUSTMENT_SPECS: dict[AdjustmentType, tuple[AccountSpec, AccountSpec]] = {
    AdjustmentType.STOCK: (STOCK_BALANCE_SPEC, STOCK_RESULT_SPEC),
    AdjustmentType.ACCRUED_EXPENSE: (ACCRUED_EXPENSE_SPEC, DEFAULT_COST_SPEC),
    AdjustmentType.PREPAID_EXPENSE: (PREPAID_EXPENSE_SPEC, DEFAULT_COST_SPEC),
    AdjustmentType.ACCRUED_REVENUE: (ACCRUED_REVENUE_SPEC, DEFAULT_REVENUE_SPEC),
    AdjustmentType.PREPAID_REVENUE: (PREPAID_REVENUE_SPEC, DEFAULT_REVENUE_SPEC),
}


@dataclass
class PostingLine:
    """One line of a proposed posting, in preview form."""

    account_number: int
    account_name: str
    debit: Decimal
    credit: Decimal
    account_will_be_created: bool


@dataclass
class ProposedPosting:
    """A verification the closing will create when it is completed."""

    kind: str
    description: str
    transaction_date: date
    lines: list[PostingLine]
    # Accruals must be taken back on the first day of the next year, or the real invoice
    # would count twice. Invoice postings must NOT: the payment settles the receivable
    # instead, which keeps the VAT reported in exactly one period.
    reverses_next_year: bool = False
    # Set for the postings that book an unpaid invoice, so the closing can point the
    # invoice at the verification it was booked by.
    source_invoice_id: int | None = None
    source_supplier_invoice_id: int | None = None


@dataclass
class Check:
    """One traffic light result."""

    code: str
    severity: str  # "red" | "yellow" | "green"
    message: str
    detail: str | None = None


# =============================================================================
# Balances
# =============================================================================


def account_net(db: Session, account: Account) -> Decimal:
    """
    Net movement on an account in debit-positive terms, including its opening balance.

    Computed from the transaction lines rather than Account.current_balance, which is
    maintained incrementally by every posting path and drifts.
    """
    totals = (
        db.query(
            func.sum(TransactionLine.debit).label("debit"),
            func.sum(TransactionLine.credit).label("credit"),
        )
        .filter(TransactionLine.account_id == account.id)
        .one()
    )
    debit = totals.debit or Decimal("0")
    credit = totals.credit or Decimal("0")
    return Decimal(account.opening_balance or 0) + Decimal(debit) - Decimal(credit)


def _accounts_for_year(db: Session, fiscal_year: FiscalYear) -> list[Account]:
    return db.query(Account).filter(Account.fiscal_year_id == fiscal_year.id).all()


def compute_result_before_adjustments(db: Session, fiscal_year: FiscalYear) -> Decimal:
    """
    Profit or loss currently visible in the ledger, before any closing postings.

    Revenue accounts carry credit balances and cost accounts debit balances, so the
    result is the negated sum of the net movement across every result account.
    """
    total = Decimal("0")
    for account in _accounts_for_year(db, fiscal_year):
        if account.account_type in RESULT_ACCOUNT_TYPES:
            total += account_net(db, account)
    return -total


# =============================================================================
# Account resolution
# =============================================================================


def resolve_account(
    db: Session, company_id: int, fiscal_year_id: int, spec: AccountSpec, create: bool
) -> tuple[Account | None, bool]:
    """
    Find the account for a spec, optionally creating it.

    Looks first at the company's default account mapping, then at the plain account
    number in this fiscal year. Charts seeded before the year-end accounts were added
    will be missing several of them, which is why creation is offered at all.

    Returns (account, was_or_would_be_created). When create is False and the account
    does not exist, the account is None and the flag is True — that is what lets the
    preview say "this account will be created" before the user commits.
    """
    # An empty default_type means "just this account number" — used when mirroring an
    # account into the next year. Writing a mapping for it would put a junk row keyed on
    # the empty string into default_accounts.
    remember_mapping = bool(spec.default_type)

    if remember_mapping:
        mapped = default_account_service.get_default_account(db, company_id, fiscal_year_id, spec.default_type)
        if mapped:
            return mapped, False

    existing = (
        db.query(Account)
        .filter(
            Account.company_id == company_id,
            Account.fiscal_year_id == fiscal_year_id,
            Account.account_number == spec.number,
        )
        .first()
    )
    if existing:
        if create and remember_mapping:
            default_account_service.set_default_account(db, company_id, spec.default_type, existing.id)
        return existing, False

    if not create:
        return None, True

    account = Account(
        company_id=company_id,
        fiscal_year_id=fiscal_year_id,
        account_number=spec.number,
        name=spec.name,
        account_type=spec.account_type,
        opening_balance=Decimal("0"),
        current_balance=Decimal("0"),
        active=True,
        is_bas_account=True,
    )
    db.add(account)
    db.flush()
    if remember_mapping:
        default_account_service.set_default_account(db, company_id, spec.default_type, account.id)
    return account, True


def year_result_equity_spec(company: Company) -> AccountSpec:
    """Balance sheet side of the year result, which depends on the company form."""
    if company.company_form == CompanyForm.SOLE_TRADER:
        return AccountSpec(DefaultAccountType.YEAR_RESULT_EQUITY, 2019, "Årets resultat", AccountType.EQUITY_LIABILITY)
    return AccountSpec(DefaultAccountType.YEAR_RESULT_EQUITY, 2099, "Årets resultat", AccountType.EQUITY_LIABILITY)


# =============================================================================
# Tax
# =============================================================================


def compute_tax(company: Company, result_before_tax: Decimal) -> Decimal:
    """
    Corporate income tax on the year result.

    Only a limited company or an economic association books tax in its own ledger. A
    sole trader is taxed personally on the business result, so the company books no tax
    verification at all — posting one would overstate its costs.
    """
    if company.company_form not in (CompanyForm.LIMITED_COMPANY, CompanyForm.ECONOMIC_ASSOCIATION):
        return Decimal("0")
    if result_before_tax <= 0:
        return Decimal("0")
    return (result_before_tax * CORPORATE_TAX_RATE).quantize(Decimal("0.01"))


# =============================================================================
# Posting plan
# =============================================================================


def _line(account: Account | None, spec: AccountSpec, debit: Decimal, credit: Decimal, created: bool) -> PostingLine:
    return PostingLine(
        account_number=account.account_number if account else spec.number,
        account_name=account.name if account else spec.name,
        debit=debit,
        credit=credit,
        account_will_be_created=created,
    )


def _adjustment_posting(
    db: Session,
    closing: YearEndClosing,
    fiscal_year: FiscalYear,
    adjustment: YearEndAdjustment,
    create: bool,
) -> ProposedPosting | None:
    """
    Turn one stored answer into one balanced posting.

    Stock is the odd one out: the user enters what the stock was worth on the last day
    of the year, but the posting is the change against what is already on the stock
    account, which is what the income statement needs to see.
    """
    balance_spec, result_spec = ADJUSTMENT_SPECS[adjustment.adjustment_type]

    balance_account, balance_created = resolve_account(db, closing.company_id, fiscal_year.id, balance_spec, create)
    if adjustment.balance_account_id:
        balance_account = db.query(Account).filter(Account.id == adjustment.balance_account_id).first()
        balance_created = False

    result_account, result_created = resolve_account(db, closing.company_id, fiscal_year.id, result_spec, create)
    if adjustment.result_account_id:
        result_account = db.query(Account).filter(Account.id == adjustment.result_account_id).first()
        result_created = False

    amount = Decimal(adjustment.amount or 0)

    if adjustment.adjustment_type == AdjustmentType.STOCK:
        current = account_net(db, balance_account) if balance_account else Decimal("0")
        amount = (amount - current).quantize(Decimal("0.01"))
        description = "Bokslut: varulager"
    else:
        description = f"Bokslut: {ADJUSTMENT_DESCRIPTIONS[adjustment.adjustment_type]}"

    if amount == 0:
        return None

    if adjustment.description:
        description = f"{description} – {adjustment.description}"

    # Positive amount debits the balance side for asset-increasing adjustments and
    # credits it for liability-increasing ones.
    debit_balance_side = adjustment.adjustment_type in (
        AdjustmentType.STOCK,
        AdjustmentType.PREPAID_EXPENSE,
        AdjustmentType.ACCRUED_REVENUE,
    )

    magnitude = abs(amount)
    if (amount > 0) == debit_balance_side:
        lines = [
            _line(balance_account, balance_spec, magnitude, Decimal("0"), balance_created),
            _line(result_account, result_spec, Decimal("0"), magnitude, result_created),
        ]
    else:
        lines = [
            _line(result_account, result_spec, magnitude, Decimal("0"), result_created),
            _line(balance_account, balance_spec, Decimal("0"), magnitude, balance_created),
        ]

    return ProposedPosting(
        kind=adjustment.adjustment_type.value,
        description=description,
        transaction_date=fiscal_year.end_date,
        lines=lines,
    )


ADJUSTMENT_DESCRIPTIONS = {
    AdjustmentType.STOCK: "varulager",
    AdjustmentType.ACCRUED_EXPENSE: "upplupen kostnad",
    AdjustmentType.PREPAID_EXPENSE: "förutbetald kostnad",
    AdjustmentType.ACCRUED_REVENUE: "upplupen intäkt",
    AdjustmentType.PREPAID_REVENUE: "förutbetald intäkt",
}


def _account_in_year(db: Session, account: Account | None, fiscal_year_id: int) -> Account | None:
    """
    Find the same account number inside a given fiscal year.

    Invoice lines point at an account in whichever year the invoice was created, and
    accounts are per fiscal year, so the reference has to be translated.
    """
    if account is None:
        return None
    if account.fiscal_year_id == fiscal_year_id:
        return account
    return (
        db.query(Account)
        .filter(
            Account.company_id == account.company_id,
            Account.fiscal_year_id == fiscal_year_id,
            Account.account_number == account.account_number,
        )
        .first()
    )


# BAS output VAT accounts by rate, used when the company has no default mapping.
VAT_OUTGOING_BY_RATE = {
    Decimal("25"): (2611, "Utgående moms, försäljning 25%"),
    Decimal("12"): (2621, "Utgående moms, försäljning 12%"),
    Decimal("6"): (2631, "Utgående moms, försäljning 6%"),
}
VAT_INCOMING_SPEC = AccountSpec(DefaultAccountType.VAT_INCOMING_25, 2640, "Ingående moms", AccountType.EQUITY_LIABILITY)


def _vat_outgoing_account(
    db: Session, company: Company, fiscal_year: FiscalYear, rate: Decimal, create: bool
) -> tuple[Account | None, bool]:
    """
    Output VAT account for a rate, falling back to the standard BAS number.

    Same reasoning as the revenue account: a company that never configured its default
    accounts must still be able to close its year.
    """
    mapped = default_account_service.get_vat_outgoing_account_for_rate(db, company.id, fiscal_year.id, rate)
    if mapped:
        return mapped, False

    number, name = VAT_OUTGOING_BY_RATE.get(rate.quantize(Decimal("1")), (2610, "Utgående moms"))
    spec = AccountSpec(DefaultAccountType.VAT_OUTGOING_25, number, name, AccountType.EQUITY_LIABILITY)
    return resolve_account(db, company.id, fiscal_year.id, spec, create)


def _revenue_account_for_line(
    db: Session, company: Company, fiscal_year: FiscalYear, invoice_line, create: bool
) -> tuple[Account | None, bool]:
    """
    Which revenue account an unpaid invoice line should be credited to.

    The line's own account first, then the company's default for that VAT rate, and
    only then a generic revenue account. The last step matters: a company that never
    configured its default accounts must still be able to close its year, and a visible
    posting on a generic account beats a dead end.
    """
    if invoice_line.account_id:
        account = db.query(Account).filter(Account.id == invoice_line.account_id).first()
        resolved = _account_in_year(db, account, fiscal_year.id)
        if resolved:
            return resolved, False

    mapped = default_account_service.get_revenue_account_for_vat_rate(
        db, company.id, fiscal_year.id, invoice_line.vat_rate
    )
    if mapped:
        return mapped, False

    return resolve_account(db, company.id, fiscal_year.id, DEFAULT_REVENUE_SPEC, create)


def _cost_account_for_line(
    db: Session, company: Company, fiscal_year: FiscalYear, supplier_line, create: bool
) -> tuple[Account | None, bool]:
    """Same idea as _revenue_account_for_line, for the supplier invoice side."""
    if supplier_line.account_id:
        account = db.query(Account).filter(Account.id == supplier_line.account_id).first()
        resolved = _account_in_year(db, account, fiscal_year.id)
        if resolved:
            return resolved, False

    return resolve_account(db, company.id, fiscal_year.id, DEFAULT_COST_SPEC, create)


def outstanding_invoice_postings(
    db: Session, fiscal_year: FiscalYear, company: Company, create: bool
) -> list[ProposedPosting]:
    """
    Book every invoice that is still unpaid at the end of the year.

    Only relevant under the cash method. Bokföringslagen 5 kap. 2 § lets a small company
    wait until payment to record a business event, but the same sentence continues:
    "Vid räkenskapsårets utgång skall dock samtliga då obetalda fordringar och skulder
    bokföras." Without this the December sale would land in next year's result and both
    years would be wrong.

    Each posting is reversed on the first day of the next year, because reknir's cash
    method books the full revenue again when the payment actually arrives.
    """
    if company.accounting_basis != AccountingBasis.CASH:
        return []

    postings: list[ProposedPosting] = []

    receivable_account, receivable_created = resolve_account(
        db, company.id, fiscal_year.id, ACCOUNTS_RECEIVABLE_SPEC, create
    )
    payable_account, payable_created = resolve_account(db, company.id, fiscal_year.id, ACCOUNTS_PAYABLE_SPEC, create)

    # Customer invoices: debit the receivable, credit revenue and output VAT.
    invoices = (
        db.query(Invoice)
        .filter(
            Invoice.company_id == company.id,
            Invoice.invoice_date >= fiscal_year.start_date,
            Invoice.invoice_date <= fiscal_year.end_date,
            Invoice.status == InvoiceStatus.ISSUED,
            Invoice.payment_status != PaymentStatus.PAID,
        )
        .order_by(Invoice.invoice_number)
        .all()
    )

    for invoice in invoices:
        outstanding = Decimal(invoice.total_amount) - Decimal(invoice.paid_amount or 0)
        if outstanding <= 0:
            continue
        ratio = outstanding / Decimal(invoice.total_amount)

        lines = [_line(receivable_account, ACCOUNTS_RECEIVABLE_SPEC, outstanding, Decimal("0"), receivable_created)]
        vat_by_rate: dict[Decimal, Decimal] = {}

        for invoice_line in invoice.invoice_lines:
            net = (Decimal(invoice_line.net_amount) * ratio).quantize(Decimal("0.01"))
            if net == 0:
                continue
            account, created = _revenue_account_for_line(db, company, fiscal_year, invoice_line, create)
            lines.append(_line(account, DEFAULT_REVENUE_SPEC, Decimal("0"), net, created))

            rate = Decimal(str(invoice_line.vat_rate))
            if rate > 0:
                vat_by_rate[rate] = vat_by_rate.get(rate, Decimal("0")) + (
                    Decimal(invoice_line.vat_amount) * ratio
                ).quantize(Decimal("0.01"))

        for rate, vat_amount in vat_by_rate.items():
            vat_account, vat_created = _vat_outgoing_account(db, company, fiscal_year, rate, create)
            number, name = VAT_OUTGOING_BY_RATE.get(rate.quantize(Decimal("1")), (2610, "Utgående moms"))
            spec = AccountSpec(DefaultAccountType.VAT_OUTGOING_25, number, name, AccountType.EQUITY_LIABILITY)
            lines.append(_line(vat_account, spec, Decimal("0"), vat_amount, vat_created))

        postings.append(
            ProposedPosting(
                kind="outstanding_receivable",
                description=f"Bokslut: obetald kundfaktura {invoice.invoice_number}",
                transaction_date=fiscal_year.end_date,
                lines=lines,
                source_invoice_id=invoice.id,
            )
        )

    # Supplier invoices: debit the cost and input VAT, credit the payable.
    supplier_invoices = (
        db.query(SupplierInvoice)
        .filter(
            SupplierInvoice.company_id == company.id,
            SupplierInvoice.invoice_date >= fiscal_year.start_date,
            SupplierInvoice.invoice_date <= fiscal_year.end_date,
            SupplierInvoice.status == InvoiceStatus.ISSUED,
            SupplierInvoice.payment_status != PaymentStatus.PAID,
        )
        .order_by(SupplierInvoice.id)
        .all()
    )

    for supplier_invoice in supplier_invoices:
        outstanding = Decimal(supplier_invoice.total_amount) - Decimal(supplier_invoice.paid_amount or 0)
        if outstanding <= 0:
            continue
        ratio = outstanding / Decimal(supplier_invoice.total_amount)

        lines = []
        total_vat = Decimal("0")

        for supplier_line in supplier_invoice.supplier_invoice_lines:
            net = (Decimal(supplier_line.net_amount) * ratio).quantize(Decimal("0.01"))
            if net == 0:
                continue
            account, created = _cost_account_for_line(db, company, fiscal_year, supplier_line, create)
            lines.append(_line(account, DEFAULT_COST_SPEC, net, Decimal("0"), created))
            total_vat += (Decimal(supplier_line.vat_amount) * ratio).quantize(Decimal("0.01"))

        if total_vat > 0:
            vat_account, vat_created = resolve_account(db, company.id, fiscal_year.id, VAT_INCOMING_SPEC, create)
            lines.append(_line(vat_account, VAT_INCOMING_SPEC, total_vat, Decimal("0"), vat_created))

        lines.append(_line(payable_account, ACCOUNTS_PAYABLE_SPEC, Decimal("0"), outstanding, payable_created))

        postings.append(
            ProposedPosting(
                kind="outstanding_payable",
                description=(f"Bokslut: obetald leverantörsfaktura {supplier_invoice.supplier_invoice_number}"),
                transaction_date=fiscal_year.end_date,
                lines=lines,
                source_supplier_invoice_id=supplier_invoice.id,
            )
        )

    return postings


def build_posting_plan(
    db: Session, closing: YearEndClosing, fiscal_year: FiscalYear, company: Company, create: bool = False
) -> tuple[list[ProposedPosting], Decimal, Decimal, Decimal]:
    """
    Everything the closing will post, plus the figures behind it.

    Returns (postings, result_before_tax, tax, result_after_tax). With create=False
    nothing is written and missing accounts are reported rather than made, which is
    what the wizard renders as a preview.
    """
    postings: list[ProposedPosting] = []

    result_before_tax = compute_result_before_adjustments(db, fiscal_year)

    # Cash method only: unpaid invoices are not in the ledger yet and must be brought in.
    postings.extend(outstanding_invoice_postings(db, fiscal_year, company, create))

    for adjustment in closing.adjustments:
        posting = _adjustment_posting(db, closing, fiscal_year, adjustment, create)
        if not posting:
            continue
        posting.reverses_next_year = adjustment.adjustment_type in ACCRUAL_TYPES
        postings.append(posting)

    # Anything landing on a result account (3000 and up) moves the result.
    for posting in postings:
        for line in posting.lines:
            if line.account_number >= 3000:
                result_before_tax += line.credit - line.debit

    if closing.tax_amount_override is not None:
        tax = Decimal(closing.tax_amount_override)
    else:
        tax = compute_tax(company, result_before_tax)

    if tax > 0:
        tax_expense, tax_expense_created = resolve_account(
            db, closing.company_id, fiscal_year.id, TAX_EXPENSE_SPEC, create
        )
        tax_liability, tax_liability_created = resolve_account(
            db, closing.company_id, fiscal_year.id, TAX_LIABILITY_SPEC, create
        )
        postings.append(
            ProposedPosting(
                kind="tax",
                description="Bokslut: skatt på årets resultat",
                transaction_date=fiscal_year.end_date,
                lines=[
                    _line(tax_expense, TAX_EXPENSE_SPEC, tax, Decimal("0"), tax_expense_created),
                    _line(tax_liability, TAX_LIABILITY_SPEC, Decimal("0"), tax, tax_liability_created),
                ],
            )
        )

    result_after_tax = result_before_tax - tax

    if result_after_tax != 0:
        equity_spec = year_result_equity_spec(company)
        result_expense, result_expense_created = resolve_account(
            db, closing.company_id, fiscal_year.id, YEAR_RESULT_EXPENSE_SPEC, create
        )
        result_equity, result_equity_created = resolve_account(
            db, closing.company_id, fiscal_year.id, equity_spec, create
        )

        magnitude = abs(result_after_tax)
        if result_after_tax > 0:
            # A profit moves out of the income statement and increases equity.
            lines = [
                _line(result_expense, YEAR_RESULT_EXPENSE_SPEC, magnitude, Decimal("0"), result_expense_created),
                _line(result_equity, equity_spec, Decimal("0"), magnitude, result_equity_created),
            ]
        else:
            lines = [
                _line(result_equity, equity_spec, magnitude, Decimal("0"), result_equity_created),
                _line(result_expense, YEAR_RESULT_EXPENSE_SPEC, Decimal("0"), magnitude, result_expense_created),
            ]

        postings.append(
            ProposedPosting(
                kind="year_result",
                description="Bokslut: årets resultat",
                transaction_date=fiscal_year.end_date,
                lines=lines,
            )
        )

    return postings, result_before_tax, tax, result_after_tax


# =============================================================================
# Checks (traffic lights)
# =============================================================================

ACCRUAL_TYPES = (
    AdjustmentType.ACCRUED_EXPENSE,
    AdjustmentType.PREPAID_EXPENSE,
    AdjustmentType.ACCRUED_REVENUE,
    AdjustmentType.PREPAID_REVENUE,
)


def _next_fiscal_year(db: Session, fiscal_year: FiscalYear) -> FiscalYear | None:
    return (
        db.query(FiscalYear)
        .filter(
            FiscalYear.company_id == fiscal_year.company_id,
            FiscalYear.start_date > fiscal_year.end_date,
        )
        .order_by(FiscalYear.start_date)
        .first()
    )


def run_checks(db: Session, closing: YearEndClosing, fiscal_year: FiscalYear, company: Company) -> list[Check]:
    """
    The reasonableness checks that stand between the user and a finished closing.

    Red blocks completion, yellow can be acknowledged and passed. Every message is
    written for someone who does not know what a debit is.
    """
    checks: list[Check] = []
    accounts = _accounts_for_year(db, fiscal_year)
    by_number = {a.account_number: a for a in accounts}

    # Company form drives the tax posting, so it has to be known.
    if company.company_form is None:
        checks.append(
            Check(
                code="company_form_missing",
                severity="red",
                message="Vi vet inte vilken företagsform du har.",
                detail="Ange företagsform under Inställningar. Den avgör hur skatt och årets resultat bokförs.",
            )
        )
    elif company.company_form not in SUPPORTED_COMPANY_FORMS:
        checks.append(
            Check(
                code="company_form_unsupported",
                severity="red",
                message="Bokslut för handelsbolag och kommanditbolag stöds inte än.",
                detail="Resultatet ska fördelas mellan delägarna, vilket kräver uppgifter som saknas i reknir. Ta hjälp av din redovisningskonsult.",
            )
        )

    # Every verification must balance. One that does not makes every figure below wrong.
    unbalanced = []
    verifications = db.query(Verification).filter(Verification.fiscal_year_id == fiscal_year.id).all()
    for verification in verifications:
        if not verification.is_balanced:
            unbalanced.append(f"{verification.series}{verification.verification_number}")
    if unbalanced:
        checks.append(
            Check(
                code="unbalanced_verifications",
                severity="red",
                message=f"{len(unbalanced)} verifikat går inte ihop.",
                detail=f"Debet och kredit skiljer sig åt i: {', '.join(unbalanced[:10])}.",
            )
        )

    # The whole ledger is debit-positive, so everything together must net to zero.
    total_net = sum((account_net(db, a) for a in accounts), Decimal("0"))
    if abs(total_net) >= Decimal("0.01"):
        checks.append(
            Check(
                code="balance_sheet_unbalanced",
                severity="red",
                message="Balansräkningen går inte ihop.",
                # reknir is self-hosted, so there is no support desk to point at. The
                # usual cause is an opening balance that was entered by hand.
                detail=f"Tillgångarna skiljer sig {total_net} kr från skulder och eget kapital. Det beror oftast på ett ingående saldo som lagts in för hand. Kontrollera de ingående balanserna under Kontoplan.",
            )
        )

    # Bank reconciliation. reknir has no bank feed, so the user supplies the real figure.
    bank_account = by_number.get(BANK_SPEC.number)
    if closing.bank_statement_balance is None:
        checks.append(
            Check(
                code="bank_balance_missing",
                severity="red",
                message="Vi behöver veta vad du faktiskt hade på banken den sista dagen på året.",
                detail="Titta i din internetbank och skriv in saldot. Då kan vi kontrollera att bokföringen stämmer.",
            )
        )
    elif bank_account is not None:
        booked = account_net(db, bank_account)
        difference = (Decimal(closing.bank_statement_balance) - booked).quantize(Decimal("0.01"))
        if difference != 0:
            checks.append(
                Check(
                    code="bank_reconciliation",
                    severity="red",
                    message="Ditt bokförda banksaldo stämmer inte med vad du hade på banken.",
                    detail=f"Bokfört {booked} kr, du angav {closing.bank_statement_balance} kr. Skillnad {difference} kr. Har du glömt att bokföra något?",
                )
            )

    # Cash cannot go below zero — you cannot have less than nothing in your wallet.
    cash_account = by_number.get(CASH_SPEC.number)
    if cash_account is not None:
        cash_balance = account_net(db, cash_account)
        if cash_balance < 0:
            checks.append(
                Check(
                    code="negative_cash",
                    severity="red",
                    message="Din kontantkassa ligger på minus.",
                    detail=f"Kassan visar {cash_balance} kr. Kontrollera om du missat att bokföra ett utlägg eller skrivit fel belopp.",
                )
            )

    # Unposted invoices dated inside the year would otherwise be silently left out.
    draft_customer = (
        db.query(Invoice)
        .filter(
            Invoice.company_id == company.id,
            Invoice.invoice_date >= fiscal_year.start_date,
            Invoice.invoice_date <= fiscal_year.end_date,
            Invoice.status == InvoiceStatus.DRAFT,
        )
        .count()
    )
    draft_supplier = (
        db.query(SupplierInvoice)
        .filter(
            SupplierInvoice.company_id == company.id,
            SupplierInvoice.invoice_date >= fiscal_year.start_date,
            SupplierInvoice.invoice_date <= fiscal_year.end_date,
            SupplierInvoice.status == InvoiceStatus.DRAFT,
        )
        .count()
    )
    if draft_customer or draft_supplier:
        checks.append(
            Check(
                code="draft_invoices",
                severity="red",
                message=f"Du har {draft_customer + draft_supplier} fakturor som hör till året men inte är bokförda.",
                detail="Bokför eller ta bort dem innan du gör bokslut, annars saknas de i resultatet.",
            )
        )

    # VAT. reknir stores no record of which returns were submitted, so this can only
    # point at a balance still sitting on the VAT accounts.
    vat_balance = sum((account_net(db, a) for a in accounts if 2610 <= a.account_number <= 2650), Decimal("0"))
    if abs(vat_balance) >= Decimal("0.01"):
        checks.append(
            Check(
                code="vat_not_settled",
                severity="yellow",
                message="Det ligger kvar moms på momskontona vid årets slut.",
                detail=f"Saldot är {vat_balance} kr. Kontrollera att alla momsdeklarationer är inlämnade och bokförda.",
            )
        )

    # Cash method: unpaid invoices are still outside the ledger. BFL 5 kap. 2 § requires
    # them to be booked at year end, and the closing does it automatically, so this is
    # information rather than a problem to fix.
    outstanding = outstanding_invoice_postings(db, fiscal_year, company, create=False)
    if outstanding:
        receivables = sum(1 for p in outstanding if p.kind == "outstanding_receivable")
        payables = len(outstanding) - receivables
        parts = []
        if receivables:
            parts.append(
                f"{receivables} obetald{'a' if receivables > 1 else ''} kundfaktur{'or' if receivables > 1 else 'a'}"
            )
        if payables:
            parts.append(
                f"{payables} obetald{'a' if payables > 1 else ''} leverantörsfaktur{'or' if payables > 1 else 'a'}"
            )
        checks.append(
            Check(
                code="outstanding_invoices_booked",
                severity="green",
                message=f"Vi bokför {' och '.join(parts)} i årets bokföring.",
                detail=(
                    "Du använder kontantmetoden och bokför normalt först vid betalning. Vid årsskiftet "
                    "måste ändå alla obetalda fordringar och skulder tas med i året — det står i "
                    "bokföringslagen. Momsen redovisas samtidigt, i årets sista momsperiod. När fakturan "
                    "sedan betalas nästa år bokförs bara pengarna in mot fordran, utan moms en gång till."
                ),
            )
        )

    if not closing.adjustments:
        checks.append(
            Check(
                code="no_adjustments",
                severity="yellow",
                message="Du har inte gjort några bokslutsjusteringar.",
                # The check list is shown on every step, so this must not assume the
                # user has already passed the adjustments step.
                detail="Det är helt i sin ordning om du varken har varulager eller fakturor som hör till fel år. Har du det fyller du i det under steg 2, Justeringar.",
            )
        )

    # Accruals must be reversed at the start of the next year, which needs that year.
    has_accruals = any(a.adjustment_type in ACCRUAL_TYPES for a in closing.adjustments)
    if has_accruals and _next_fiscal_year(db, fiscal_year) is None:
        checks.append(
            Check(
                code="no_next_fiscal_year",
                severity="yellow",
                message="Nästa räkenskapsår finns inte upplagt.",
                detail="Dina periodiseringar ska vändas tillbaka i början av nästa år. Skapa nästa räkenskapsår först, annars måste du bokföra återföringen själv.",
            )
        )

    if not checks:
        checks.append(Check(code="all_clear", severity="green", message="Allt ser bra ut. Du kan slutföra bokslutet."))

    return checks


def blocking_checks(checks: list[Check]) -> list[Check]:
    return [c for c in checks if c.severity == "red"]


def unacknowledged_warnings(checks: list[Check], acknowledged: list[str]) -> list[Check]:
    return [c for c in checks if c.severity == "yellow" and c.code not in (acknowledged or [])]


# =============================================================================
# Lifecycle
# =============================================================================


def get_or_create_closing(db: Session, fiscal_year: FiscalYear) -> YearEndClosing:
    """Fetch the closing for a fiscal year, creating an empty one on first access."""
    closing = db.query(YearEndClosing).filter(YearEndClosing.fiscal_year_id == fiscal_year.id).first()
    if closing:
        return closing

    closing = YearEndClosing(
        company_id=fiscal_year.company_id,
        fiscal_year_id=fiscal_year.id,
        status=ClosingStatus.IN_PROGRESS,
        current_step=ClosingStep.PREPARATION,
        acknowledged_warnings=[],
    )
    db.add(closing)
    db.commit()
    db.refresh(closing)
    return closing


def unlocked_steps(closing: YearEndClosing, company: Company) -> dict[ClosingStep, bool]:
    """
    Which steps the user may open. The server decides this; the frontend renders it.

    The gate is deliberately shallow: the preparation step must be confirmed, and the
    final step additionally needs a company form, because the tax figure shown there
    depends on it.
    """
    confirmed = bool(closing.preparation_confirmed)
    return {
        ClosingStep.PREPARATION: True,
        ClosingStep.ADJUSTMENTS: confirmed,
        ClosingStep.TAX: confirmed,
        ClosingStep.REVIEW: confirmed and company.company_form is not None,
    }


def _create_verification(
    db: Session,
    company_id: int,
    fiscal_year_id: int,
    transaction_date: date,
    description: str,
    lines: list[tuple[Account, Decimal, Decimal]],
) -> Verification:
    """Write one balanced year-end verification and move the account balances."""
    from app.routers.verifications import get_next_verification_number

    verification = Verification(
        company_id=company_id,
        fiscal_year_id=fiscal_year_id,
        verification_number=get_next_verification_number(db, company_id, YEAR_END_SERIES),
        series=YEAR_END_SERIES,
        transaction_date=transaction_date,
        description=description,
        registration_date=date.today(),
    )
    db.add(verification)
    db.flush()

    for account, debit, credit in lines:
        db.add(
            TransactionLine(
                verification_id=verification.id,
                account_id=account.id,
                debit=debit,
                credit=credit,
            )
        )
        account.current_balance = Decimal(account.current_balance or 0) + debit - credit

    return verification


def complete_closing(
    db: Session, closing: YearEndClosing, fiscal_year: FiscalYear, company: Company, user_id: int
) -> list[Verification]:
    """
    Turn the answers into real bookkeeping and lock the year.

    Everything happens in one commit: the adjustment postings, their reversals in the
    next year, the tax posting, the year result, then the lock. A closing that fails
    halfway would leave a year that is neither open nor properly closed.
    """
    postings, _result_before_tax, _tax, _result_after_tax = build_posting_plan(
        db, closing, fiscal_year, company, create=True
    )

    created: list[Verification] = []
    for posting in postings:
        lines = []
        for line in posting.lines:
            account = (
                db.query(Account)
                .filter(
                    Account.fiscal_year_id == fiscal_year.id,
                    Account.account_number == line.account_number,
                )
                .first()
            )
            if account is None:
                raise ValueError(f"Account {line.account_number} could not be resolved for the closing")
            lines.append((account, line.debit, line.credit))

        verification = _create_verification(
            db,
            company.id,
            fiscal_year.id,
            posting.transaction_date,
            posting.description,
            lines,
        )
        created.append(verification)

        # Point the invoice at the verification that booked it. This is what makes the
        # payment in the next year settle the receivable instead of booking the revenue
        # a second time — the same rule the accrual method already relies on.
        if posting.source_invoice_id:
            invoice = db.query(Invoice).filter(Invoice.id == posting.source_invoice_id).first()
            if invoice:
                invoice.invoice_verification_id = verification.id
        if posting.source_supplier_invoice_id:
            supplier_invoice = (
                db.query(SupplierInvoice).filter(SupplierInvoice.id == posting.source_supplier_invoice_id).first()
            )
            if supplier_invoice:
                supplier_invoice.invoice_verification_id = verification.id

    created.extend(_post_reversals(db, postings, fiscal_year, company))

    # Lock every verification in the year, including the ones just written. This is the
    # first time Verification.locked is actually set anywhere in reknir.
    db.query(Verification).filter(Verification.fiscal_year_id == fiscal_year.id).update({"locked": True})

    fiscal_year.is_closed = True
    closing.status = ClosingStatus.COMPLETED
    closing.current_step = ClosingStep.REVIEW
    closing.completed_at = datetime.now()
    closing.completed_by = user_id

    db.add(
        YearEndClosingEvent(
            closing_id=closing.id,
            event_type=ClosingEventType.COMPLETED,
            user_id=user_id,
        )
    )

    db.commit()
    return created


def _post_reversals(
    db: Session, postings: list[ProposedPosting], fiscal_year: FiscalYear, company: Company
) -> list[Verification]:
    """
    Reverse, on the first day of the next year, every posting that needs it.

    Two kinds need it. An accrual moves a cost or an income into the year it belongs
    to, and leaving it in place would double count it when the real invoice arrives.
    An unpaid invoice booked under the cash method would likewise be counted twice,
    because reknir books the full revenue again when the payment lands.

    Skipped when the next fiscal year does not exist or is itself closed; run_checks
    warns about the missing year beforehand.
    """
    to_reverse = [p for p in postings if p.reverses_next_year]
    if not to_reverse:
        return []

    next_year = _next_fiscal_year(db, fiscal_year)
    if next_year is None or next_year.is_closed:
        return []

    created: list[Verification] = []
    for posting in to_reverse:
        lines = []
        for line in posting.lines:
            account, _ = resolve_account(
                db,
                company.id,
                next_year.id,
                AccountSpec(
                    default_type="",
                    number=line.account_number,
                    name=line.account_name,
                    account_type=_account_type_for_number(line.account_number),
                ),
                create=True,
            )
            # Swap debit and credit: this is the reversal.
            lines.append((account, line.credit, line.debit))

        created.append(
            _create_verification(
                db,
                company.id,
                next_year.id,
                next_year.start_date,
                f"Återföring {posting.description.lower()}",
                lines,
            )
        )

    return created


def _account_type_for_number(number: int) -> AccountType:
    """BAS account class from the account number, used when mirroring an account forward."""
    if number < 2000:
        return AccountType.ASSET
    if number < 3000:
        return AccountType.EQUITY_LIABILITY
    if number < 4000:
        return AccountType.REVENUE
    if number < 5000:
        return AccountType.COST_GOODS
    if number < 6000:
        return AccountType.COST_LOCAL
    if number < 7000:
        return AccountType.COST_OTHER
    if number < 8000:
        return AccountType.COST_PERSONNEL
    return AccountType.COST_MISC


def reopen_closing(
    db: Session, closing: YearEndClosing, fiscal_year: FiscalYear, company: Company, user_id: int, reason: str
) -> list[Verification]:
    """
    Unlock a completed closing without erasing anything.

    Bokföringslagen does not allow a posted entry to disappear, so reopening does not
    delete the year-end verifications — it posts mirrored reversals of them. The books
    keep showing both what was booked and that it was taken back, and the reason for
    doing so is recorded.
    """
    year_end_verifications = (
        db.query(Verification)
        .filter(
            Verification.fiscal_year_id == fiscal_year.id,
            Verification.series == YEAR_END_SERIES,
        )
        .order_by(Verification.verification_number)
        .all()
    )

    # Unlock first, otherwise the reversals land in a year that still refuses writes.
    fiscal_year.is_closed = False
    db.query(Verification).filter(Verification.fiscal_year_id == fiscal_year.id).update({"locked": False})
    db.flush()

    created: list[Verification] = []
    for verification in year_end_verifications:
        lines = [(line.account, line.credit, line.debit) for line in verification.transaction_lines]
        created.append(
            _create_verification(
                db,
                company.id,
                fiscal_year.id,
                fiscal_year.end_date,
                f"Återföring av {verification.series}{verification.verification_number}: {verification.description}",
                lines,
            )
        )

    closing.status = ClosingStatus.IN_PROGRESS
    closing.current_step = ClosingStep.REVIEW
    closing.completed_at = None
    closing.completed_by = None

    db.add(
        YearEndClosingEvent(
            closing_id=closing.id,
            event_type=ClosingEventType.REOPENED,
            user_id=user_id,
            reason=reason,
        )
    )

    db.commit()
    return created
