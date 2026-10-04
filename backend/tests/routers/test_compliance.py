"""Reversal instead of edit, per-year numbering, period locks, gaps, audit log, reports."""

from datetime import date, timedelta
from decimal import Decimal

import pytest

from app.models.account import Account, AccountType
from app.models.compliance import AuditLog
from app.models.fiscal_year import FiscalYear
from app.models.verification import Verification


@pytest.fixture
def ledger(db_session, test_company_with_fiscal_year):
    company, fy = test_company_with_fiscal_year
    accounts = {}
    for number, name, kind in [
        (1930, "Bank", AccountType.ASSET),
        (1510, "Kundfordringar", AccountType.ASSET),
        (6110, "Kontor", AccountType.COST_OTHER),
        (3011, "Försäljning", AccountType.REVENUE),
    ]:
        a = Account(company_id=company.id, fiscal_year_id=fy.id, account_number=number, name=name, account_type=kind)
        db_session.add(a)
        accounts[number] = a
    db_session.commit()
    return company, fy, accounts


def _post(client, headers, company, fy, accounts, when: date, amount="100.00", debit=6110, credit=1930, series="A"):
    body = {
        "company_id": company.id,
        "fiscal_year_id": fy.id,
        "series": series,
        "transaction_date": when.isoformat(),
        "description": f"test {when}",
        "transaction_lines": [
            {"account_id": accounts[debit].id, "debit": amount, "credit": "0"},
            {"account_id": accounts[credit].id, "debit": "0", "credit": amount},
        ],
    }
    return client.post("/api/verifications/", json=body, headers=headers)


def test_reversal_swaps_lines_and_links_both_ways(client, auth_headers, db_session, ledger):
    company, fy, accounts = ledger
    original = _post(client, auth_headers, company, fy, accounts, date(2025, 3, 1)).json()
    assert original["verification_number"] == 1

    r = client.post(
        f"/api/verifications/{original['id']}/reverse", json={"transaction_date": "2025-03-05"}, headers=auth_headers
    )
    assert r.status_code == 201, r.text
    reversal = r.json()
    assert reversal["verification_number"] == 2 and reversal["series"] == "A"
    assert reversal["reverses_verification_id"] == original["id"]
    assert reversal["description"].startswith("Rättelse av A1")
    lines = {line["account_number"]: line for line in reversal["transaction_lines"]}
    assert lines[6110]["credit"] == 100 and lines[1930]["debit"] == 100

    db_session.expire_all()
    orig = db_session.query(Verification).get(original["id"])
    assert orig.reversed_by_verification_id == reversal["id"]
    assert db_session.query(Account).get(accounts[6110].id).current_balance == Decimal("0")

    # A verification can only be reversed once
    again = client.post(f"/api/verifications/{original['id']}/reverse", headers=auth_headers)
    assert again.status_code == 400 and "redan rättad" in again.json()["detail"]


def test_posted_verification_cannot_be_edited(client, auth_headers, ledger, monkeypatch):
    from app.config import settings

    company, fy, accounts = ledger
    ver = _post(client, auth_headers, company, fy, accounts, date(2025, 3, 1)).json()
    monkeypatch.setattr(settings, "debug", False)
    r = client.patch(f"/api/verifications/{ver['id']}", json={"description": "ändrad"}, headers=auth_headers)
    assert r.status_code == 403
    assert "rättelse" in r.json()["detail"].lower()


def test_numbering_restarts_per_fiscal_year(client, auth_headers, db_session, ledger):
    company, fy, accounts = ledger
    assert _post(client, auth_headers, company, fy, accounts, date(2025, 1, 10)).json()["verification_number"] == 1
    assert _post(client, auth_headers, company, fy, accounts, date(2025, 1, 11)).json()["verification_number"] == 2
    fy2 = FiscalYear(
        company_id=company.id, year=2026, label="2026", start_date=date(2026, 1, 1), end_date=date(2026, 12, 31)
    )
    db_session.add(fy2)
    db_session.flush()
    accounts2 = {}
    for number in (6110, 1930):
        a = Account(
            company_id=company.id,
            fiscal_year_id=fy2.id,
            account_number=number,
            name=str(number),
            account_type=AccountType.ASSET,
        )
        db_session.add(a)
        accounts2[number] = a
    db_session.commit()
    assert _post(client, auth_headers, company, fy2, accounts2, date(2026, 1, 5)).json()["verification_number"] == 1


def test_period_lock_blocks_posting_and_only_moves_forward(client, auth_headers, db_session, ledger):
    company, fy, accounts = ledger
    _post(client, auth_headers, company, fy, accounts, date(2025, 2, 10))

    r = client.post(
        f"/api/companies/{company.id}/period-locks",
        json={"locked_through": "2025-03-31", "note": "Moms Q1 deklarerad"},
        headers=auth_headers,
    )
    assert r.status_code == 201, r.text
    status = client.get(f"/api/companies/{company.id}/period-locks", headers=auth_headers).json()
    assert status["locked_through"] == "2025-03-31" and len(status["history"]) == 1

    blocked = _post(client, auth_headers, company, fy, accounts, date(2025, 3, 31))
    assert blocked.status_code == 403 and "låst" in blocked.json()["detail"].lower()
    allowed = _post(client, auth_headers, company, fy, accounts, date(2025, 4, 1))
    assert allowed.status_code == 201

    db_session.expire_all()
    assert all(
        v.locked for v in db_session.query(Verification).filter(Verification.transaction_date <= date(2025, 3, 31))
    )

    back = client.post(
        f"/api/companies/{company.id}/period-locks", json={"locked_through": "2025-01-31"}, headers=auth_headers
    )
    assert back.status_code == 400

    # Reversal of a locked verification lands on an open date
    locked_ver = db_session.query(Verification).filter(Verification.transaction_date == date(2025, 2, 10)).one()
    rev = client.post(
        f"/api/verifications/{locked_ver.id}/reverse", json={"transaction_date": "2025-03-15"}, headers=auth_headers
    )
    assert rev.status_code == 403
    rev = client.post(
        f"/api/verifications/{locked_ver.id}/reverse", json={"transaction_date": "2025-04-02"}, headers=auth_headers
    )
    assert rev.status_code == 201


def test_gaps_are_detected_and_explained(client, auth_headers, db_session, ledger):
    company, fy, accounts = ledger
    _post(client, auth_headers, company, fy, accounts, date(2025, 1, 1))
    _post(client, auth_headers, company, fy, accounts, date(2025, 1, 2))
    _post(client, auth_headers, company, fy, accounts, date(2025, 1, 3))
    db_session.query(Verification).filter(Verification.verification_number == 2).delete()
    db_session.commit()

    gaps = client.get(
        "/api/verifications/gaps", params={"company_id": company.id, "fiscal_year_id": fy.id}, headers=auth_headers
    ).json()
    assert gaps == [{"series": "A", "verification_number": 2, "explanation": None}]

    overview = client.get(
        "/api/dashboard/overview", params={"company_id": company.id, "fiscal_year_id": fy.id}, headers=auth_headers
    ).json()
    assert overview["verification_gaps"] == gaps

    r = client.post(
        "/api/verifications/gaps/explain",
        json={
            "company_id": company.id,
            "fiscal_year_id": fy.id,
            "series": "A",
            "verification_number": 2,
            "explanation": "Makulerad vid import",
        },
        headers=auth_headers,
    )
    assert r.status_code == 201
    gaps = client.get(
        "/api/verifications/gaps", params={"company_id": company.id, "fiscal_year_id": fy.id}, headers=auth_headers
    ).json()
    assert gaps[0]["explanation"] == "Makulerad vid import"
    overview = client.get(
        "/api/dashboard/overview", params={"company_id": company.id, "fiscal_year_id": fy.id}, headers=auth_headers
    ).json()
    assert overview["verification_gaps"] == []

    r = client.post(
        "/api/verifications/gaps/explain",
        json={
            "company_id": company.id,
            "fiscal_year_id": fy.id,
            "series": "A",
            "verification_number": 1,
            "explanation": "finns",
        },
        headers=auth_headers,
    )
    assert r.status_code == 400


def test_audit_log_records_who_did_what(client, auth_headers, db_session, ledger, test_user):
    company, fy, accounts = ledger
    ver = _post(client, auth_headers, company, fy, accounts, date(2025, 5, 1)).json()
    client.post(
        f"/api/verifications/{ver['id']}/reverse", json={"transaction_date": "2025-05-02"}, headers=auth_headers
    )

    entries = client.get(
        "/api/audit-log/", params={"company_id": company.id, "table_name": "verifications"}, headers=auth_headers
    ).json()
    summaries = [e["summary"] for e in entries]
    assert "insert verifications A1" in summaries and "insert verifications A2" in summaries
    update = next(e for e in entries if e["action"] == "update" and e["record_id"] == ver["id"])
    assert update["changes"]["reversed_by_verification_id"][1] is not None
    assert all(e["user_email"] == test_user.email for e in entries)

    # Company changes are logged with old and new values
    client.patch(f"/api/companies/{company.id}", json={"city": "Göteborg"}, headers=auth_headers)
    entries = client.get(
        "/api/audit-log/", params={"company_id": company.id, "table_name": "companies"}, headers=auth_headers
    ).json()
    assert entries[0]["changes"]["city"] == ["Stockholm", "Göteborg"]

    # Non-admin cannot read the instance-wide log
    assert client.get("/api/audit-log/", headers=auth_headers).status_code == 403
    assert db_session.query(AuditLog).count() >= 4


def test_aging_and_cash_flow_reports(client, auth_headers, db_session, ledger, test_customer):
    from app.models.invoice import Invoice, InvoiceStatus, PaymentStatus

    company, fy, accounts = ledger
    today = date.today()
    for n, due_offset, paid in [(1, -45, Decimal("0")), (2, -5, Decimal("0")), (3, 10, Decimal("250.00"))]:
        db_session.add(
            Invoice(
                company_id=company.id,
                customer_id=test_customer.id,
                invoice_number=n,
                invoice_series="F",
                invoice_date=today - timedelta(days=60),
                due_date=today + timedelta(days=due_offset),
                total_amount=Decimal("1000.00"),
                vat_amount=Decimal("200.00"),
                net_amount=Decimal("800.00"),
                status=InvoiceStatus.ISSUED,
                payment_status=PaymentStatus.PARTIALLY_PAID if paid else PaymentStatus.UNPAID,
                paid_amount=paid,
            )
        )
    db_session.commit()
    aging = client.get(
        "/api/reports/aging", params={"company_id": company.id, "kind": "customer"}, headers=auth_headers
    ).json()
    by_key = {b["key"]: b["amount"] for b in aging["buckets"]}
    assert by_key["d31_60"] == 1000 and by_key["d1_30"] == 1000 and by_key["not_due"] == 750
    assert aging["total"] == 2750 and aging["parties"][0]["name"] == test_customer.name

    _post(client, auth_headers, company, fy, accounts, date(2025, 1, 15), amount="300.00", debit=1930, credit=3011)
    _post(client, auth_headers, company, fy, accounts, date(2025, 2, 3), amount="120.00", debit=6110, credit=1930)
    cash = client.get(
        "/api/reports/cash-flow", params={"company_id": company.id, "fiscal_year_id": fy.id}, headers=auth_headers
    ).json()
    assert cash["cash_accounts"] == [1930] and cash["opening"] == 0
    assert [m["month"] for m in cash["months"]] == ["2025-01", "2025-02"]
    assert cash["months"][0]["inflow"] == 300 and cash["months"][0]["by_category"]["sales"] == 300
    assert cash["months"][1]["outflow"] == 120 and cash["months"][1]["by_category"]["purchases"] == -120
    assert cash["closing"] == 180
