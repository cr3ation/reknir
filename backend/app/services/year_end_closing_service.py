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
from app.models.company import Company, CompanyForm
from app.models.default_account import DefaultAccountType
from app.models.fiscal_year import FiscalYear
from app.models.invoice import Invoice, InvoiceStatus, SupplierInvoice
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
        if create:
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

    for adjustment in closing.adjustments:
        posting = _adjustment_posting(db, closing, fiscal_year, adjustment, create)
        if not posting:
            continue
        postings.append(posting)
        # Adjustments move the result by whatever hits their result account.
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
                detail=f"Tillgångarna skiljer sig {total_net} kr från skulder och eget kapital. Kontakta support.",
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

    if not closing.adjustments:
        checks.append(
            Check(
                code="no_adjustments",
                severity="yellow",
                message="Du har inte gjort några bokslutsjusteringar.",
                detail="Det är helt i sin ordning om du varken har varulager eller fakturor som hör till fel år. Annars, gå tillbaka ett steg.",
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

        created.append(
            _create_verification(
                db,
                company.id,
                fiscal_year.id,
                posting.transaction_date,
                posting.description,
                lines,
            )
        )

    created.extend(_post_accrual_reversals(db, closing, fiscal_year, company))

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


def _post_accrual_reversals(
    db: Session, closing: YearEndClosing, fiscal_year: FiscalYear, company: Company
) -> list[Verification]:
    """
    Reverse the accruals on the first day of the next year.

    An accrual moves a cost or an income into the year it belongs to; leaving it in
    place would double count it when the real invoice arrives. Skipped when the next
    fiscal year does not exist yet, which run_checks warns about beforehand.
    """
    accruals = [a for a in closing.adjustments if a.adjustment_type in ACCRUAL_TYPES]
    if not accruals:
        return []

    next_year = _next_fiscal_year(db, fiscal_year)
    if next_year is None or next_year.is_closed:
        return []

    created: list[Verification] = []
    for adjustment in accruals:
        posting = _adjustment_posting(db, closing, fiscal_year, adjustment, create=True)
        if not posting:
            continue

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
