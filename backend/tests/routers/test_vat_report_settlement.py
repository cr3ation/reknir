"""The VAT report must ignore the settlement verification that moves a period's VAT
to the tax account, whichever accounts the settlement uses."""

from datetime import date
from decimal import Decimal

import pytest

from app.models.account import Account, AccountType
from app.models.verification import TransactionLine, Verification


@pytest.fixture
def accounts(db_session, test_company_with_fiscal_year):
    company, fy = test_company_with_fiscal_year
    made = {}
    for number, kind in [
        (1630, AccountType.ASSET),
        (1650, AccountType.ASSET),
        (2640, AccountType.EQUITY_LIABILITY),
        (2611, AccountType.EQUITY_LIABILITY),
        (2650, AccountType.EQUITY_LIABILITY),
        (2890, AccountType.EQUITY_LIABILITY),
        (3740, AccountType.REVENUE),
        (5410, AccountType.COST_LOCAL),
    ]:
        a = Account(
            company_id=company.id, fiscal_year_id=fy.id, account_number=number, name=str(number), account_type=kind
        )
        db_session.add(a)
        made[number] = a
    db_session.commit()
    return company, fy, made


def _ver(db, company, fy, number, when, text, lines):
    v = Verification(
        company_id=company.id,
        fiscal_year_id=fy.id,
        verification_number=number,
        series="V",
        transaction_date=when,
        description=text,
    )
    db.add(v)
    db.flush()
    for acc, debit, credit in lines:
        db.add(TransactionLine(verification_id=v.id, account_id=acc.id, debit=Decimal(debit), credit=Decimal(credit)))
    db.commit()


@pytest.mark.parametrize(
    "settlement_lines",
    [
        # Bokio style: Momsfordran / Ingående moms / öresutjämning
        lambda a: [(a[1650], "3997.00", "0"), (a[2640], "0", "3997.40"), (a[3740], "0.40", "0")],
        # Redovisningskonto för moms
        lambda a: [(a[2650], "3997.40", "0"), (a[2640], "0", "3997.40")],
        # Straight to skattekontot
        lambda a: [(a[1630], "3997.40", "0"), (a[2640], "0", "3997.40")],
    ],
)
def test_settlement_is_excluded_from_vat_report(client, auth_headers, db_session, accounts, settlement_lines):
    company, fy, a = accounts
    _ver(
        db_session,
        company,
        fy,
        1,
        date(2025, 6, 22),
        "Utlägg - inköp",
        [(a[5410], "15989.60", "0"), (a[2640], "3997.40", "0"), (a[2890], "0", "19987.00")],
    )
    _ver(db_session, company, fy, 2, date(2025, 6, 30), "Momsredovisning: april 2025 - juni 2025", settlement_lines(a))

    report = client.get(
        "/api/reports/vat-report",
        params={
            "company_id": company.id,
            "fiscal_year_id": fy.id,
            "start_date": "2025-04-01",
            "end_date": "2025-06-30",
            "exclude_vat_settlements": True,
        },
        headers=auth_headers,
    ).json()
    assert report["incoming_vat"]["total"] == pytest.approx(3997.40)
    assert report["net_vat"] == pytest.approx(-3997.40)
    assert report["pay_or_refund"] == "refund"

    # Without the exclusion the settlement nets the period to zero, which is the bug this guards against
    raw = client.get(
        "/api/reports/vat-report",
        params={
            "company_id": company.id,
            "fiscal_year_id": fy.id,
            "start_date": "2025-04-01",
            "end_date": "2025-06-30",
            "exclude_vat_settlements": False,
        },
        headers=auth_headers,
    ).json()
    assert raw["incoming_vat"]["total"] == 0
