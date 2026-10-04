"""Ledger rules: sequential numbering per fiscal year, period locks, reversals, gaps."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import desc, func
from sqlalchemy.orm import Session

from app.models.account import Account
from app.models.compliance import PeriodLock, VerificationGapExplanation
from app.models.fiscal_year import FiscalYear
from app.models.user import User
from app.models.verification import TransactionLine, Verification


class PeriodLockedError(Exception):
    """A transaction date falls in a locked period."""

    def __init__(self, transaction_date: date, locked_through: date):
        self.transaction_date = transaction_date
        self.locked_through = locked_through
        super().__init__(
            f"Perioden är låst t.o.m. {locked_through.isoformat()}; "
            f"transaktionsdatum {transaction_date.isoformat()} kan inte bokföras. "
            "Boka rättelsen på ett datum i en öppen period."
        )


class VerificationImmutableError(Exception):
    """Posted verifications are not edited; they are reversed."""


# ---------------------------------------------------------------------------
# numbering
# ---------------------------------------------------------------------------


def next_verification_number(db: Session, company_id: int, series: str, fiscal_year_id: int) -> int:
    """Next number in ``series`` within one fiscal year (numbering restarts every year)."""
    last = (
        db.query(Verification.verification_number)
        .filter(
            Verification.company_id == company_id,
            Verification.series == series,
            Verification.fiscal_year_id == fiscal_year_id,
        )
        .order_by(desc(Verification.verification_number))
        .first()
    )
    return (last[0] + 1) if last else 1


# ---------------------------------------------------------------------------
# period locks
# ---------------------------------------------------------------------------


def locked_through(db: Session, company_id: int) -> date | None:
    value = db.query(func.max(PeriodLock.locked_through)).filter(PeriodLock.company_id == company_id).scalar()
    return value


def assert_period_open(db: Session, company_id: int, transaction_date: date) -> None:
    through = locked_through(db, company_id)
    if through is not None and transaction_date <= through:
        raise PeriodLockedError(transaction_date, through)


def lock_period(db: Session, company_id: int, through: date, user: User | None, note: str | None = None) -> PeriodLock:
    """Lock the books through ``through`` and mark every verification up to it as locked.

    A lock only moves forward; re-opening is a deliberate, separate action.
    """
    current = locked_through(db, company_id)
    if current is not None and through < current:
        raise ValueError(f"Perioden är redan låst t.o.m. {current.isoformat()}; låsningen kan bara flyttas framåt.")
    lock = PeriodLock(
        company_id=company_id,
        locked_through=through,
        note=note,
        created_by=user.id if user else None,
        created_at=datetime.utcnow(),
    )
    db.add(lock)
    db.query(Verification).filter(
        Verification.company_id == company_id,
        Verification.transaction_date <= through,
        Verification.locked.is_(False),
    ).update({"locked": True}, synchronize_session=False)
    db.flush()
    return lock


# ---------------------------------------------------------------------------
# reversals (ändringsverifikation)
# ---------------------------------------------------------------------------


def create_reversal(
    db: Session,
    original: Verification,
    user: User | None,
    *,
    description: str | None = None,
    transaction_date: date | None = None,
) -> Verification:
    """Create the verification that cancels ``original``: same accounts, debit and credit swapped.

    The reversal is posted in the fiscal year of its own transaction date (default:
    today, or the original date if that period is still open), numbered next in
    the original's series, and both verifications point at each other.
    """
    if original.reversed_by_verification_id is not None:
        raise ValueError(f"{original.series}{original.verification_number} är redan rättad")
    when = transaction_date or date.today()
    assert_period_open(db, original.company_id, when)
    fiscal_year = (
        db.query(FiscalYear)
        .filter(
            FiscalYear.company_id == original.company_id, FiscalYear.start_date <= when, FiscalYear.end_date >= when
        )
        .first()
    )
    if fiscal_year is None:
        raise ValueError(f"Inget räkenskapsår täcker {when.isoformat()}")
    if fiscal_year.is_closed:
        raise ValueError(f"Räkenskapsåret {fiscal_year.label} är stängt")

    reversal = Verification(
        company_id=original.company_id,
        fiscal_year_id=fiscal_year.id,
        verification_number=next_verification_number(db, original.company_id, original.series, fiscal_year.id),
        series=original.series,
        transaction_date=when,
        registration_date=date.today(),
        description=description
        or f"Rättelse av {original.series}{original.verification_number}: {original.description}",
        reverses_verification_id=original.id,
    )
    db.add(reversal)
    db.flush()

    for line in original.transaction_lines:
        # Same account in the reversal's fiscal year (accounts are per year)
        account = db.query(Account).filter(Account.id == line.account_id).first()
        if account.fiscal_year_id != fiscal_year.id:
            account = (
                db.query(Account)
                .filter(
                    Account.company_id == original.company_id,
                    Account.fiscal_year_id == fiscal_year.id,
                    Account.account_number == account.account_number,
                )
                .first()
            )
            if account is None:
                raise ValueError(f"Konto {line.account.account_number} saknas i räkenskapsåret {fiscal_year.label}")
        db.add(
            TransactionLine(
                verification_id=reversal.id,
                account_id=account.id,
                debit=line.credit,
                credit=line.debit,
                description=line.description,
            )
        )
        account.current_balance += Decimal(line.credit) - Decimal(line.debit)

    original.reversed_by_verification_id = reversal.id
    db.flush()
    return reversal


# ---------------------------------------------------------------------------
# gaps
# ---------------------------------------------------------------------------


def find_gaps(db: Session, company_id: int, fiscal_year_id: int) -> list[dict]:
    """Missing numbers per series in a fiscal year, with any recorded explanation."""
    rows = (
        db.query(Verification.series, Verification.verification_number)
        .filter(Verification.company_id == company_id, Verification.fiscal_year_id == fiscal_year_id)
        .all()
    )
    by_series: dict[str, set[int]] = {}
    for series, number in rows:
        by_series.setdefault(series, set()).add(number)
    explanations = {
        (e.series, e.verification_number): e.explanation
        for e in db.query(VerificationGapExplanation).filter(
            VerificationGapExplanation.company_id == company_id,
            VerificationGapExplanation.fiscal_year_id == fiscal_year_id,
        )
    }
    gaps = []
    for series, numbers in sorted(by_series.items()):
        for missing in range(1, max(numbers) + 1):
            if missing not in numbers:
                gaps.append(
                    {
                        "series": series,
                        "verification_number": missing,
                        "explanation": explanations.get((series, missing)),
                    }
                )
    return gaps
