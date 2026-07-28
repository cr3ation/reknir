"""Tests for the year-end closing (bokslut) resource."""

from datetime import date
from decimal import Decimal

import pytest

from app.models.company import CompanyForm


def create_fiscal_year(client, auth_headers, company_id, year):
    response = client.post(
        "/api/fiscal-years/",
        json={
            "company_id": company_id,
            "year": year,
            "label": str(year),
            "start_date": f"{year}-01-01",
            "end_date": f"{year}-12-31",
        },
        headers=auth_headers,
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def create_account(client, auth_headers, company_id, fiscal_year_id, number, name, account_type):
    response = client.post(
        "/api/accounts/",
        json={
            "company_id": company_id,
            "fiscal_year_id": fiscal_year_id,
            "account_number": number,
            "name": name,
            "account_type": account_type,
        },
        headers=auth_headers,
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def post_verification(client, auth_headers, company_id, fiscal_year_id, when, description, lines):
    response = client.post(
        "/api/verifications/",
        json={
            "company_id": company_id,
            "fiscal_year_id": fiscal_year_id,
            "series": "A",
            "transaction_date": when,
            "description": description,
            "transaction_lines": lines,
        },
        headers=auth_headers,
    )
    assert response.status_code == 201, response.text
    return response.json()


@pytest.fixture
def closing_setup(client, auth_headers, test_company, db_session):
    """
    A company with one fiscal year, a minimal chart of accounts and a single sale.

    Bank 1930 is debited 125 000 and revenue 3001 credited 100 000 with 25 000 VAT, so
    the year has a 100 000 profit and a bank balance the test can reconcile against.
    """
    test_company.company_form = CompanyForm.LIMITED_COMPANY
    db_session.commit()

    fy_id = create_fiscal_year(client, auth_headers, test_company.id, 2021)

    bank = create_account(client, auth_headers, test_company.id, fy_id, 1930, "Företagskonto", "asset")
    revenue = create_account(client, auth_headers, test_company.id, fy_id, 3001, "Försäljning", "revenue")
    vat = create_account(client, auth_headers, test_company.id, fy_id, 2611, "Utgående moms", "equity_liability")

    post_verification(
        client,
        auth_headers,
        test_company.id,
        fy_id,
        "2021-06-01",
        "Försäljning",
        [
            {"account_id": bank, "debit": "125000.00", "credit": "0.00"},
            {"account_id": revenue, "debit": "0.00", "credit": "100000.00"},
            {"account_id": vat, "debit": "0.00", "credit": "25000.00"},
        ],
    )

    return {
        "company_id": test_company.id,
        "fiscal_year_id": fy_id,
        "bank_account_id": bank,
        "revenue_account_id": revenue,
        "vat_account_id": vat,
    }


class TestClosingDocument:
    def test_get_creates_empty_closing(self, client, auth_headers, closing_setup):
        """First read creates the closing and reports the preparation step as current."""
        response = client.get(f"/api/fiscal-years/{closing_setup['fiscal_year_id']}/closing", headers=auth_headers)
        assert response.status_code == 200, response.text
        body = response.json()

        assert body["status"] == "in_progress"
        assert body["current_step"] == "preparation"
        assert body["preparation_confirmed"] is False
        assert body["can_complete"] is False
        assert [s["step"] for s in body["steps"]] == ["preparation", "adjustments", "tax", "review"]

    def test_later_steps_locked_until_preparation_confirmed(self, client, auth_headers, closing_setup):
        """The server owns step gating; the frontend only renders it."""
        fy_id = closing_setup["fiscal_year_id"]

        body = client.get(f"/api/fiscal-years/{fy_id}/closing", headers=auth_headers).json()
        unlocked = {s["step"]: s["is_unlocked"] for s in body["steps"]}
        assert unlocked["preparation"] is True
        assert unlocked["adjustments"] is False

        body = client.patch(
            f"/api/fiscal-years/{fy_id}/closing",
            json={"preparation_confirmed": True},
            headers=auth_headers,
        ).json()
        unlocked = {s["step"]: s["is_unlocked"] for s in body["steps"]}
        assert unlocked["adjustments"] is True
        assert unlocked["review"] is True

    def test_result_computed_from_ledger(self, client, auth_headers, closing_setup):
        """100 000 revenue and no costs is a 100 000 profit, taxed at 20.6 percent."""
        body = client.get(f"/api/fiscal-years/{closing_setup['fiscal_year_id']}/closing", headers=auth_headers).json()

        assert Decimal(body["result_before_tax"]) == Decimal("100000.00")
        assert Decimal(body["tax"]) == Decimal("20600.00")
        assert Decimal(body["result_after_tax"]) == Decimal("79400.00")

    def test_preview_flags_accounts_that_will_be_created(self, client, auth_headers, closing_setup):
        """The chart has no 8999 or 2510, and the preview says so before anything is written."""
        body = client.get(f"/api/fiscal-years/{closing_setup['fiscal_year_id']}/closing", headers=auth_headers).json()

        flagged = {
            line["account_number"]
            for posting in body["postings"]
            for line in posting["lines"]
            if line["account_will_be_created"]
        }
        assert 8999 in flagged
        assert 8910 in flagged
        assert 2510 in flagged


class TestAdjustments:
    def test_adjustments_replace_wholesale(self, client, auth_headers, closing_setup):
        """Sending the list twice leaves one adjustment, not two."""
        fy_id = closing_setup["fiscal_year_id"]
        payload = {"adjustments": [{"adjustment_type": "stock", "amount": "30000.00"}]}

        client.patch(f"/api/fiscal-years/{fy_id}/closing", json=payload, headers=auth_headers)
        body = client.patch(f"/api/fiscal-years/{fy_id}/closing", json=payload, headers=auth_headers).json()

        assert len(body["adjustments"]) == 1

    def test_stock_increases_the_result(self, client, auth_headers, closing_setup):
        """Stock on hand at year end is not a cost, so it lifts the result by its value."""
        fy_id = closing_setup["fiscal_year_id"]

        body = client.patch(
            f"/api/fiscal-years/{fy_id}/closing",
            json={"adjustments": [{"adjustment_type": "stock", "amount": "30000.00"}]},
            headers=auth_headers,
        ).json()

        assert Decimal(body["result_before_tax"]) == Decimal("130000.00")
        stock_posting = next(p for p in body["postings"] if p["kind"] == "stock")
        debits = {line["account_number"]: Decimal(line["debit"]) for line in stock_posting["lines"]}
        credits = {line["account_number"]: Decimal(line["credit"]) for line in stock_posting["lines"]}
        assert debits[1460] == Decimal("30000.00")
        assert credits[4990] == Decimal("30000.00")

    def test_accrued_expense_lowers_the_result(self, client, auth_headers, closing_setup):
        """A cost belonging to this year but invoiced later still belongs to this year."""
        fy_id = closing_setup["fiscal_year_id"]

        body = client.patch(
            f"/api/fiscal-years/{fy_id}/closing",
            json={"adjustments": [{"adjustment_type": "accrued_expense", "amount": "10000.00"}]},
            headers=auth_headers,
        ).json()

        assert Decimal(body["result_before_tax"]) == Decimal("90000.00")
        posting = next(p for p in body["postings"] if p["kind"] == "accrued_expense")
        credits = {line["account_number"]: Decimal(line["credit"]) for line in posting["lines"]}
        assert credits[2990] == Decimal("10000.00")

    def test_depreciation_is_rejected(self, client, auth_headers, closing_setup):
        """Depreciation is reserved in the enum but not offered without a fixed asset register."""
        response = client.patch(
            f"/api/fiscal-years/{closing_setup['fiscal_year_id']}/closing",
            json={"adjustments": [{"adjustment_type": "depreciation", "amount": "5000.00"}]},
            headers=auth_headers,
        )
        assert response.status_code == 422


class TestCompanyForm:
    def test_sole_trader_pays_no_company_tax(self, client, auth_headers, closing_setup, test_company, db_session):
        """A sole trader is taxed personally, so the company books no tax at all."""
        test_company.company_form = CompanyForm.SOLE_TRADER
        db_session.commit()

        body = client.get(f"/api/fiscal-years/{closing_setup['fiscal_year_id']}/closing", headers=auth_headers).json()

        assert Decimal(body["tax"]) == Decimal("0")
        assert Decimal(body["result_after_tax"]) == Decimal("100000.00")
        result_posting = next(p for p in body["postings"] if p["kind"] == "year_result")
        assert {line["account_number"] for line in result_posting["lines"]} == {8999, 2019}

    def test_limited_company_closes_against_2099(self, client, auth_headers, closing_setup):
        result_posting = next(
            p
            for p in client.get(
                f"/api/fiscal-years/{closing_setup['fiscal_year_id']}/closing", headers=auth_headers
            ).json()["postings"]
            if p["kind"] == "year_result"
        )
        assert {line["account_number"] for line in result_posting["lines"]} == {8999, 2099}

    def test_missing_company_form_blocks(self, client, auth_headers, closing_setup, test_company, db_session):
        test_company.company_form = None
        db_session.commit()

        body = client.get(f"/api/fiscal-years/{closing_setup['fiscal_year_id']}/closing", headers=auth_headers).json()

        codes = {c["code"]: c["severity"] for c in body["checks"]}
        assert codes["company_form_missing"] == "red"
        assert body["can_complete"] is False


class TestChecks:
    def test_bank_balance_required(self, client, auth_headers, closing_setup):
        body = client.get(f"/api/fiscal-years/{closing_setup['fiscal_year_id']}/closing", headers=auth_headers).json()
        assert "bank_balance_missing" in {c["code"] for c in body["checks"]}

    def test_bank_mismatch_is_blocking(self, client, auth_headers, closing_setup):
        """The booked bank balance is 125 000; claiming 100 000 must stop the closing."""
        body = client.patch(
            f"/api/fiscal-years/{closing_setup['fiscal_year_id']}/closing",
            json={"bank_statement_balance": "100000.00"},
            headers=auth_headers,
        ).json()

        check = next(c for c in body["checks"] if c["code"] == "bank_reconciliation")
        assert check["severity"] == "red"
        assert body["can_complete"] is False

    def test_matching_bank_balance_clears_the_check(self, client, auth_headers, closing_setup):
        body = client.patch(
            f"/api/fiscal-years/{closing_setup['fiscal_year_id']}/closing",
            json={"bank_statement_balance": "125000.00"},
            headers=auth_headers,
        ).json()

        codes = {c["code"] for c in body["checks"]}
        assert "bank_reconciliation" not in codes
        assert "bank_balance_missing" not in codes
        assert Decimal(body["booked_bank_balance"]) == Decimal("125000.00")

    def test_warnings_must_be_acknowledged(self, client, auth_headers, closing_setup):
        """VAT sits unsettled on 2611 and no adjustments were made — both yellow."""
        fy_id = closing_setup["fiscal_year_id"]
        body = client.patch(
            f"/api/fiscal-years/{fy_id}/closing",
            json={"preparation_confirmed": True, "bank_statement_balance": "125000.00"},
            headers=auth_headers,
        ).json()

        yellows = [c["code"] for c in body["checks"] if c["severity"] == "yellow"]
        assert "vat_not_settled" in yellows
        assert body["can_complete"] is False

        body = client.patch(
            f"/api/fiscal-years/{fy_id}/closing",
            json={"acknowledged_warnings": yellows},
            headers=auth_headers,
        ).json()
        assert body["can_complete"] is True


class TestComplete:
    @staticmethod
    def _make_completable(client, auth_headers, fy_id):
        body = client.patch(
            f"/api/fiscal-years/{fy_id}/closing",
            json={"preparation_confirmed": True, "bank_statement_balance": "125000.00"},
            headers=auth_headers,
        ).json()
        yellows = [c["code"] for c in body["checks"] if c["severity"] == "yellow"]
        return client.patch(
            f"/api/fiscal-years/{fy_id}/closing",
            json={"acknowledged_warnings": yellows},
            headers=auth_headers,
        ).json()

    def test_complete_posts_b_series_and_locks_the_year(self, client, auth_headers, closing_setup):
        fy_id = closing_setup["fiscal_year_id"]
        self._make_completable(client, auth_headers, fy_id)

        response = client.post(f"/api/fiscal-years/{fy_id}/closing/complete", headers=auth_headers)
        assert response.status_code == 200, response.text
        assert response.json()["status"] == "completed"

        # The year-end verifications landed in their own series.
        verifications = client.get(
            f"/api/verifications/?company_id={closing_setup['company_id']}&fiscal_year_id={fy_id}",
            headers=auth_headers,
        ).json()
        b_series = [v for v in verifications if v["series"] == "B"]
        assert b_series, "expected year-end verifications in series B"
        assert all(v["locked"] for v in verifications), "every verification in the year must be locked"

        # And the year itself refuses further writes.
        fiscal_year = client.get(f"/api/fiscal-years/{fy_id}", headers=auth_headers).json()
        assert fiscal_year["is_closed"] is True

    def test_completed_year_rejects_new_verifications(self, client, auth_headers, closing_setup):
        fy_id = closing_setup["fiscal_year_id"]
        self._make_completable(client, auth_headers, fy_id)
        client.post(f"/api/fiscal-years/{fy_id}/closing/complete", headers=auth_headers)

        response = client.post(
            "/api/verifications/",
            json={
                "company_id": closing_setup["company_id"],
                "fiscal_year_id": fy_id,
                "series": "A",
                "transaction_date": "2021-12-30",
                "description": "Too late",
                "transaction_lines": [
                    {"account_id": closing_setup["bank_account_id"], "debit": "1.00", "credit": "0.00"},
                    {"account_id": closing_setup["revenue_account_id"], "debit": "0.00", "credit": "1.00"},
                ],
            },
            headers=auth_headers,
        )
        assert response.status_code == 403

    def test_complete_is_refused_while_a_red_check_stands(self, client, auth_headers, closing_setup):
        fy_id = closing_setup["fiscal_year_id"]
        response = client.post(f"/api/fiscal-years/{fy_id}/closing/complete", headers=auth_headers)
        assert response.status_code == 400

    def test_completed_closing_rejects_further_edits(self, client, auth_headers, closing_setup):
        fy_id = closing_setup["fiscal_year_id"]
        self._make_completable(client, auth_headers, fy_id)
        client.post(f"/api/fiscal-years/{fy_id}/closing/complete", headers=auth_headers)

        response = client.patch(
            f"/api/fiscal-years/{fy_id}/closing",
            json={"bank_statement_balance": "1.00"},
            headers=auth_headers,
        )
        assert response.status_code == 403

    def test_the_books_still_balance_after_closing(self, client, auth_headers, closing_setup):
        """Every posting the closing makes must keep debit equal to credit."""
        fy_id = closing_setup["fiscal_year_id"]
        self._make_completable(client, auth_headers, fy_id)
        client.post(f"/api/fiscal-years/{fy_id}/closing/complete", headers=auth_headers)

        verifications = client.get(
            f"/api/verifications/?company_id={closing_setup['company_id']}&fiscal_year_id={fy_id}",
            headers=auth_headers,
        ).json()
        for listed in verifications:
            detail = client.get(f"/api/verifications/{listed['id']}", headers=auth_headers).json()
            debit = sum(Decimal(line["debit"]) for line in detail["transaction_lines"])
            credit = sum(Decimal(line["credit"]) for line in detail["transaction_lines"])
            assert debit == credit, f"{detail['series']}{detail['verification_number']} does not balance"


class TestCashMethodOutstandingInvoices:
    """
    Bokföringslagen 5 kap. 2 §: the cash method lets you wait until payment, but
    "vid räkenskapsårets utgång skall dock samtliga då obetalda fordringar och skulder
    bokföras". Without this an invoice sent in December and paid in January would land
    entirely in the wrong year.
    """

    @staticmethod
    def _issue_unpaid_invoice(
        client, auth_headers, db_session, company_id, fiscal_year_id, customer_id, revenue_account_id
    ):
        from app.models.invoice import Invoice, InvoiceLine, InvoiceStatus, PaymentStatus

        invoice = Invoice(
            company_id=company_id,
            customer_id=customer_id,
            invoice_number=20210001,
            invoice_date=date(2021, 12, 20),
            due_date=date(2022, 1, 19),
            status=InvoiceStatus.ISSUED,
            payment_status=PaymentStatus.UNPAID,
            net_amount=Decimal("8000.00"),
            vat_amount=Decimal("2000.00"),
            total_amount=Decimal("10000.00"),
            paid_amount=Decimal("0.00"),
        )
        db_session.add(invoice)
        db_session.flush()
        db_session.add(
            InvoiceLine(
                invoice_id=invoice.id,
                description="Decemberuppdrag",
                quantity=Decimal("1"),
                unit="st",
                unit_price=Decimal("8000.00"),
                vat_rate=Decimal("25.00"),
                account_id=revenue_account_id,
                net_amount=Decimal("8000.00"),
                vat_amount=Decimal("2000.00"),
                total_amount=Decimal("10000.00"),
            )
        )
        db_session.commit()
        return invoice

    @pytest.fixture
    def cash_setup(self, client, auth_headers, closing_setup, test_company, test_customer, db_session):
        """Switch the company to the cash method and leave one invoice unpaid."""
        from app.models.company import AccountingBasis

        test_company.accounting_basis = AccountingBasis.CASH
        db_session.commit()

        self._issue_unpaid_invoice(
            client,
            auth_headers,
            db_session,
            test_company.id,
            closing_setup["fiscal_year_id"],
            test_customer.id,
            closing_setup["revenue_account_id"],
        )
        return closing_setup

    def test_unpaid_invoice_is_brought_into_the_year(self, client, auth_headers, cash_setup):
        """The receivable is debited and the revenue and VAT credited, at 31 December."""
        body = client.get(f"/api/fiscal-years/{cash_setup['fiscal_year_id']}/closing", headers=auth_headers).json()

        posting = next(p for p in body["postings"] if p["kind"] == "outstanding_receivable")
        debits = {line["account_number"]: Decimal(line["debit"]) for line in posting["lines"]}
        credits = {line["account_number"]: Decimal(line["credit"]) for line in posting["lines"]}

        assert debits[1510] == Decimal("10000.00")
        assert credits[3001] == Decimal("8000.00")
        assert credits[2611] == Decimal("2000.00")
        assert posting["transaction_date"] == "2021-12-31"

    def test_it_raises_the_result(self, client, auth_headers, cash_setup):
        """The December sale belongs to this year, so the result goes up by the net."""
        body = client.get(f"/api/fiscal-years/{cash_setup['fiscal_year_id']}/closing", headers=auth_headers).json()
        assert Decimal(body["result_before_tax"]) == Decimal("108000.00")

    def test_the_user_is_told_it_happened(self, client, auth_headers, cash_setup):
        body = client.get(f"/api/fiscal-years/{cash_setup['fiscal_year_id']}/closing", headers=auth_headers).json()
        check = next(c for c in body["checks"] if c["code"] == "outstanding_invoices_booked")
        assert check["severity"] == "green"
        assert "kundfaktura" in check["message"]

    def test_accrual_companies_are_untouched(self, client, auth_headers, closing_setup, test_customer, db_session):
        """An accrual company already booked the invoice when it was sent."""
        self._issue_unpaid_invoice(
            client,
            None,
            db_session,
            closing_setup["company_id"],
            closing_setup["fiscal_year_id"],
            test_customer.id,
            closing_setup["revenue_account_id"],
        )
        body = client.get(f"/api/fiscal-years/{closing_setup['fiscal_year_id']}/closing", headers=auth_headers).json()
        assert not [p for p in body["postings"] if p["kind"] == "outstanding_receivable"]

    def test_not_reversed_in_the_next_year(self, client, auth_headers, cash_setup, test_company, db_session):
        """
        The invoice posting must NOT be reversed on 1 January.

        Reversing it and letting the ordinary cash-method payment re-book the revenue
        gives the right total but reports the VAT in three periods: plus in December,
        minus in January, plus again on payment. VAT returns are filed per period, so a
        monthly filer would submit two wrong ones. The receivable is settled by the
        payment instead, which keeps the VAT in exactly one period.
        """
        fy_id = cash_setup["fiscal_year_id"]
        next_fy_id = create_fiscal_year(client, auth_headers, test_company.id, 2022)

        TestComplete._make_completable(client, auth_headers, fy_id)
        response = client.post(f"/api/fiscal-years/{fy_id}/closing/complete", headers=auth_headers)
        assert response.status_code == 200, response.text

        next_year = client.get(
            f"/api/verifications/?company_id={test_company.id}&fiscal_year_id={next_fy_id}",
            headers=auth_headers,
        ).json()
        invoice_reversals = [
            v for v in next_year if "Återföring" in v["description"] and "kundfaktura" in v["description"]
        ]
        assert not invoice_reversals, "an invoice posting must not be reversed"

    def test_invoice_is_linked_to_the_year_end_verification(
        self, client, auth_headers, cash_setup, test_company, db_session
    ):
        """The link is what tells the payment path the invoice is already booked."""
        from app.models.invoice import Invoice

        fy_id = cash_setup["fiscal_year_id"]
        TestComplete._make_completable(client, auth_headers, fy_id)
        client.post(f"/api/fiscal-years/{fy_id}/closing/complete", headers=auth_headers)

        invoice = db_session.query(Invoice).filter(Invoice.invoice_number == 20210001).first()
        db_session.refresh(invoice)
        assert invoice.invoice_verification_id is not None

    def test_payment_next_year_only_settles_the_receivable(
        self, client, auth_headers, cash_setup, test_company, db_session
    ):
        """
        D 1930 / K 1510, with no revenue and no VAT — those were reported at year end.
        """
        from app.models.invoice import Invoice

        fy_id = cash_setup["fiscal_year_id"]
        next_fy_id = create_fiscal_year(client, auth_headers, test_company.id, 2022)
        create_account(client, auth_headers, test_company.id, next_fy_id, 1930, "Företagskonto", "asset")
        create_account(client, auth_headers, test_company.id, next_fy_id, 1510, "Kundfordringar", "asset")
        bank_next = client.get(
            f"/api/accounts/?company_id={test_company.id}&fiscal_year_id={next_fy_id}",
            headers=auth_headers,
        ).json()
        bank_id = next(a["id"] for a in bank_next if a["account_number"] == 1930)

        TestComplete._make_completable(client, auth_headers, fy_id)
        client.post(f"/api/fiscal-years/{fy_id}/closing/complete", headers=auth_headers)

        invoice = db_session.query(Invoice).filter(Invoice.invoice_number == 20210001).first()
        response = client.post(
            f"/api/invoices/{invoice.id}/mark-paid",
            json={"paid_date": "2022-01-15", "bank_account_id": bank_id},
            headers=auth_headers,
        )
        assert response.status_code == 200, response.text

        next_year = client.get(
            f"/api/verifications/?company_id={test_company.id}&fiscal_year_id={next_fy_id}",
            headers=auth_headers,
        ).json()
        payment = next(v for v in next_year if "Betalning" in v["description"])
        detail = client.get(f"/api/verifications/{payment['id']}", headers=auth_headers).json()
        accounts = {line["account_number"] for line in detail["transaction_lines"]}

        assert accounts == {1930, 1510}, f"expected only bank and receivable, got {accounts}"
        lines = {line["account_number"]: line for line in detail["transaction_lines"]}
        assert Decimal(lines[1930]["debit"]) == Decimal("10000.00")
        assert Decimal(lines[1510]["credit"]) == Decimal("10000.00")

    def test_accruals_are_still_reversed(self, client, auth_headers, cash_setup, test_company):
        """Reversal is right for accruals — only the invoice postings changed."""
        fy_id = cash_setup["fiscal_year_id"]
        next_fy_id = create_fiscal_year(client, auth_headers, test_company.id, 2022)

        client.patch(
            f"/api/fiscal-years/{fy_id}/closing",
            json={"adjustments": [{"adjustment_type": "accrued_expense", "amount": "5000.00"}]},
            headers=auth_headers,
        )
        TestComplete._make_completable(client, auth_headers, fy_id)
        client.post(f"/api/fiscal-years/{fy_id}/closing/complete", headers=auth_headers)

        next_year = client.get(
            f"/api/verifications/?company_id={test_company.id}&fiscal_year_id={next_fy_id}",
            headers=auth_headers,
        ).json()
        assert [v for v in next_year if "Återföring" in v["description"]]


class TestReportsAfterClosing:
    def test_income_statement_still_shows_the_result(self, client, auth_headers, closing_setup):
        """
        8999 Årets resultat is the bottom line, not a cost.

        Counting it among the expenses would cancel the result out and report a closed
        year as breaking even, which is what happened before it was excluded.
        """
        fy_id = closing_setup["fiscal_year_id"]
        TestComplete._make_completable(client, auth_headers, fy_id)
        client.post(f"/api/fiscal-years/{fy_id}/closing/complete", headers=auth_headers)

        income = client.get(
            f"/api/reports/income-statement?company_id={closing_setup['company_id']}&fiscal_year_id={fy_id}",
            headers=auth_headers,
        ).json()

        assert 8999 not in {a["account_number"] for a in income["expenses"]["accounts"]}
        assert Decimal(str(income["profit_loss"])) == Decimal("79400.00")

    def test_income_statement_agrees_with_the_balance_sheet(self, client, auth_headers, closing_setup):
        """The result in the income statement must equal what was posted to equity."""
        fy_id = closing_setup["fiscal_year_id"]
        TestComplete._make_completable(client, auth_headers, fy_id)
        client.post(f"/api/fiscal-years/{fy_id}/closing/complete", headers=auth_headers)

        income = client.get(
            f"/api/reports/income-statement?company_id={closing_setup['company_id']}&fiscal_year_id={fy_id}",
            headers=auth_headers,
        ).json()
        balance = client.get(
            f"/api/reports/balance-sheet?company_id={closing_setup['company_id']}&fiscal_year_id={fy_id}",
            headers=auth_headers,
        ).json()

        equity_result = next(a["balance"] for a in balance["equity"]["accounts"] if a["account_number"] == 2099)
        assert Decimal(str(equity_result)) == Decimal(str(income["profit_loss"]))
        assert balance["balanced"] is True


class TestReopen:
    def test_reopen_requires_admin(self, client, auth_headers, closing_setup):
        fy_id = closing_setup["fiscal_year_id"]
        TestComplete._make_completable(client, auth_headers, fy_id)
        client.post(f"/api/fiscal-years/{fy_id}/closing/complete", headers=auth_headers)

        response = client.post(
            f"/api/fiscal-years/{fy_id}/closing/reopen",
            json={"reason": "Missed an invoice"},
            headers=auth_headers,
        )
        assert response.status_code == 403

    def test_reopen_reverses_rather_than_deletes(self, client, auth_headers, admin_auth_headers, closing_setup):
        """Bokföringslagen forbids erasing a posting, so reopening mirrors them instead."""
        fy_id = closing_setup["fiscal_year_id"]
        TestComplete._make_completable(client, auth_headers, fy_id)
        client.post(f"/api/fiscal-years/{fy_id}/closing/complete", headers=auth_headers)

        before = client.get(
            f"/api/verifications/?company_id={closing_setup['company_id']}&fiscal_year_id={fy_id}",
            headers=auth_headers,
        ).json()
        b_before = len([v for v in before if v["series"] == "B"])

        response = client.post(
            f"/api/fiscal-years/{fy_id}/closing/reopen",
            json={"reason": "Forgot a supplier invoice"},
            headers=admin_auth_headers,
        )
        assert response.status_code == 200, response.text
        assert response.json()["status"] == "in_progress"

        after = client.get(
            f"/api/verifications/?company_id={closing_setup['company_id']}&fiscal_year_id={fy_id}",
            headers=auth_headers,
        ).json()
        b_after = len([v for v in after if v["series"] == "B"])

        assert b_after == b_before * 2, "each year-end verification should gain a mirrored reversal"

        fiscal_year = client.get(f"/api/fiscal-years/{fy_id}", headers=auth_headers).json()
        assert fiscal_year["is_closed"] is False
