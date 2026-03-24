"""
Tests for report_pdf_service: build_balance_sheet_data, build_income_statement_data,
build_general_ledger_data, and _build_grouped_data.
"""

from datetime import date
from decimal import Decimal

import pytest

from app.models.account import Account, AccountType
from app.models.company import AccountingBasis, Company, PaymentType, VATReportingPeriod
from app.models.fiscal_year import FiscalYear
from app.models.user import CompanyUser, User
from app.models.verification import TransactionLine, Verification
from app.services.auth_service import get_password_hash
from app.services.report_pdf_service import (
    ASSET_GROUPS,
    EQUITY_LIABILITY_GROUPS,
    _build_grouped_data,
    build_balance_sheet_data,
    build_general_ledger_data,
    build_income_statement_data,
)

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def report_data(db_session):
    """Create a complete set of test data for report tests.

    Creates:
    - User + Company + FiscalYear (2025)
    - Accounts: 1910, 1510, 2440, 2099, 3000, 5010
    - Verification A1: Invoice (1510 D:12500, 3000 C:10000, 2610 C:2500)
    - Verification A2: Rent payment (5010 D:8000, 1910 C:8000)
    """
    # User
    user = User(
        email="report_test@example.com",
        hashed_password=get_password_hash("testpassword"),
        full_name="Report Tester",
        is_admin=False,
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()

    # Company
    company = Company(
        name="Rapport AB",
        org_number="556677-8899",
        address="Rapportgatan 1",
        postal_code="12345",
        city="Stockholm",
        phone="08-111 22 33",
        email="info@rapport.se",
        fiscal_year_start=date(2025, 1, 1),
        fiscal_year_end=date(2025, 12, 31),
        accounting_basis=AccountingBasis.ACCRUAL,
        vat_reporting_period=VATReportingPeriod.QUARTERLY,
        is_vat_registered=True,
        payment_type=PaymentType.BANKGIRO,
        bankgiro_number="123-4567",
    )
    db_session.add(company)
    db_session.commit()

    company_user = CompanyUser(user_id=user.id, company_id=company.id)
    db_session.add(company_user)
    db_session.commit()

    # Fiscal year
    fy = FiscalYear(
        company_id=company.id,
        year=2025,
        label="2025",
        start_date=date(2025, 1, 1),
        end_date=date(2025, 12, 31),
        is_closed=False,
    )
    db_session.add(fy)
    db_session.commit()

    # Accounts
    accounts = {}
    accounts_spec = [
        (1910, "Kassa", AccountType.ASSET, Decimal("50000")),
        (1510, "Kundfordringar", AccountType.ASSET, Decimal("10000")),
        (2440, "Leverantörsskulder", AccountType.EQUITY_LIABILITY, Decimal("-60000")),
        (2099, "Årets resultat", AccountType.EQUITY_LIABILITY, Decimal("0")),
        (2610, "Utgående moms 25%", AccountType.EQUITY_LIABILITY, Decimal("0")),
        (3000, "Försäljning tjänster", AccountType.REVENUE, Decimal("0")),
        (5010, "Lokalhyra", AccountType.COST_LOCAL, Decimal("0")),
    ]

    for num, name, acc_type, opening in accounts_spec:
        account = Account(
            company_id=company.id,
            fiscal_year_id=fy.id,
            account_number=num,
            name=name,
            account_type=acc_type,
            opening_balance=opening,
            current_balance=opening,
            active=True,
        )
        db_session.add(account)
        accounts[num] = account

    db_session.commit()
    for acc in accounts.values():
        db_session.refresh(acc)

    # Verification A1: Invoice — 1510 D:12500, 3000 C:10000, 2610 C:2500
    ver1 = Verification(
        company_id=company.id,
        fiscal_year_id=fy.id,
        verification_number=1,
        series="A",
        transaction_date=date(2025, 3, 15),
        description="Faktura 101",
    )
    db_session.add(ver1)
    db_session.commit()

    db_session.add_all(
        [
            TransactionLine(
                verification_id=ver1.id,
                account_id=accounts[1510].id,
                debit=Decimal("12500"),
                credit=Decimal("0"),
            ),
            TransactionLine(
                verification_id=ver1.id,
                account_id=accounts[3000].id,
                debit=Decimal("0"),
                credit=Decimal("10000"),
            ),
            TransactionLine(
                verification_id=ver1.id,
                account_id=accounts[2610].id,
                debit=Decimal("0"),
                credit=Decimal("2500"),
            ),
        ]
    )
    db_session.commit()

    # Verification A2: Rent payment — 5010 D:8000, 1910 C:8000
    ver2 = Verification(
        company_id=company.id,
        fiscal_year_id=fy.id,
        verification_number=2,
        series="A",
        transaction_date=date(2025, 3, 20),
        description="Hyra mars",
    )
    db_session.add(ver2)
    db_session.commit()

    db_session.add_all(
        [
            TransactionLine(
                verification_id=ver2.id,
                account_id=accounts[5010].id,
                debit=Decimal("8000"),
                credit=Decimal("0"),
            ),
            TransactionLine(
                verification_id=ver2.id,
                account_id=accounts[1910].id,
                debit=Decimal("0"),
                credit=Decimal("8000"),
            ),
        ]
    )
    db_session.commit()

    return {
        "company": company,
        "fiscal_year": fy,
        "accounts": accounts,
        "verifications": [ver1, ver2],
    }


# =============================================================================
# _build_grouped_data tests
# =============================================================================


class TestBuildGroupedData:
    """Tests for _build_grouped_data helper."""

    def test_empty_accounts(self):
        result = _build_grouped_data([], ASSET_GROUPS)
        assert result == []

    def test_accounts_with_subgroups(self):
        accounts_data = [
            {"account_number": 1510, "name": "Kundfordringar", "ib": 10000, "period": 5000, "ub": 15000},
            {"account_number": 1910, "name": "Kassa", "ib": 50000, "period": -8000, "ub": 42000},
        ]
        result = _build_grouped_data(accounts_data, ASSET_GROUPS)

        # Should be in "Omsättningstillgångar" group (1400-1999)
        assert len(result) == 1
        group = result[0]
        assert group["title"] == "Omsättningstillgångar"
        assert group["ib_total"] == 60000
        assert group["period_total"] == -3000
        assert group["ub_total"] == 57000

        # Should have two subgroups: Fordringar and Kassa och bank
        assert len(group["subgroups"]) == 2
        fordring_sg = [sg for sg in group["subgroups"] if sg["title"] == "Fordringar"][0]
        assert fordring_sg["ib_total"] == 10000
        kassa_sg = [sg for sg in group["subgroups"] if sg["title"] == "Kassa och bank"][0]
        assert kassa_sg["ib_total"] == 50000

    def test_group_without_subgroups(self):
        accounts_data = [
            {"account_number": 2440, "name": "Leverantörsskulder", "ib": -5000, "period": -2500, "ub": -7500},
        ]
        result = _build_grouped_data(accounts_data, EQUITY_LIABILITY_GROUPS)

        # 2440 is in Kortfristiga skulder (2400-2999)
        assert len(result) == 1
        group = result[0]
        assert group["title"] == "Kortfristiga skulder"
        # No named subgroups — accounts placed directly
        assert len(group["subgroups"]) == 1
        assert group["subgroups"][0]["title"] is None
        assert len(group["subgroups"][0]["accounts"]) == 1

    def test_accounts_in_multiple_groups(self):
        accounts_data = [
            {"account_number": 1100, "name": "Byggnader", "ib": 100000, "period": 0, "ub": 100000},
            {"account_number": 1910, "name": "Kassa", "ib": 50000, "period": 0, "ub": 50000},
        ]
        result = _build_grouped_data(accounts_data, ASSET_GROUPS)

        # Should have two groups: Anläggningstillgångar and Omsättningstillgångar
        assert len(result) == 2
        titles = [g["title"] for g in result]
        assert "Anläggningstillgångar" in titles
        assert "Omsättningstillgångar" in titles


# =============================================================================
# build_balance_sheet_data tests
# =============================================================================


class TestBuildBalanceSheetData:
    """Tests for build_balance_sheet_data."""

    def test_asset_totals(self, db_session, report_data):
        data = build_balance_sheet_data(db_session, report_data["company"].id, report_data["fiscal_year"])

        assets = data["total_assets"]
        # 1910: IB=50000, period=-8000 → UB=42000
        # 1510: IB=10000, period=+12500 → UB=22500
        assert assets["ib"] == 60000
        assert assets["period"] == pytest.approx(4500, abs=0.01)
        assert assets["ub"] == pytest.approx(64500, abs=0.01)

    def test_equity_liability_totals(self, db_session, report_data):
        data = build_balance_sheet_data(db_session, report_data["company"].id, report_data["fiscal_year"])

        el = data["total_equity_liabilities"]
        # 2440: IB=-60000, period=0 → UB=-60000
        # 2610: IB=0, period=-2500 → UB=-2500
        # total_el = -62500
        # + årets resultat from P&L: IB=0, period=-2000
        # grand_el_ib = -60000 + 0 = -60000
        assert el["ib"] == pytest.approx(-60000, abs=0.01)

    def test_balanced(self, db_session, report_data):
        data = build_balance_sheet_data(db_session, report_data["company"].id, report_data["fiscal_year"])
        assert data["balanced"] is True

    def test_arets_resultat_from_pl_accounts(self, db_session, report_data):
        data = build_balance_sheet_data(db_session, report_data["company"].id, report_data["fiscal_year"])

        ar = data["arets_resultat"]
        # P&L accounts: 3000 period=-10000, 5010 period=+8000
        # revenue_expense_total_period = -10000 + 8000 = -2000
        assert ar["ib"] == 0
        assert ar["period"] == pytest.approx(-2000, abs=0.01)

    def test_zero_accounts_excluded(self, db_session, report_data):
        """Accounts with IB=0, period=0, UB=0 should not appear in groups."""
        data = build_balance_sheet_data(db_session, report_data["company"].id, report_data["fiscal_year"])

        # 2099 Årets resultat has IB=0 and no transactions → should be excluded
        all_account_numbers = []
        for group in data["asset_groups"] + data["equity_liability_groups"]:
            for sg in group["subgroups"]:
                for acc in sg["accounts"]:
                    all_account_numbers.append(acc["account_number"])
        assert 2099 not in all_account_numbers


# =============================================================================
# build_income_statement_data tests
# =============================================================================


class TestBuildIncomeStatementData:
    """Tests for build_income_statement_data."""

    def test_rows_contain_expected_types(self, db_session, report_data):
        data = build_income_statement_data(db_session, report_data["company"].id, report_data["fiscal_year"])

        row_types = {r["type"] for r in data["rows"]}
        assert "section_header" in row_types
        assert "account" in row_types
        assert "final_result" in row_types

    def test_revenue_shown_positive(self, db_session, report_data):
        """Revenue (3000) should be positive after negation."""
        data = build_income_statement_data(db_session, report_data["company"].id, report_data["fiscal_year"])

        revenue_rows = [r for r in data["rows"] if r["type"] == "account" and r.get("account_number") == 3000]
        assert len(revenue_rows) == 1
        # 3000 raw period = credit 10000 → net = 0 - 10000 = -10000
        # Negated: -(-10000) = 10000 (positive)
        assert revenue_rows[0]["period"] == pytest.approx(10000, abs=0.01)

    def test_expenses_shown_negative(self, db_session, report_data):
        """Expenses (5010) should be negative after negation."""
        data = build_income_statement_data(db_session, report_data["company"].id, report_data["fiscal_year"])

        expense_rows = [r for r in data["rows"] if r["type"] == "account" and r.get("account_number") == 5010]
        assert len(expense_rows) == 1
        # 5010 raw period = debit 8000 → net = 8000 - 0 = 8000
        # Negated: -(8000) = -8000
        assert expense_rows[0]["period"] == pytest.approx(-8000, abs=0.01)

    def test_no_previous_year(self, db_session, report_data):
        data = build_income_statement_data(db_session, report_data["company"].id, report_data["fiscal_year"])
        assert data["has_prev_year"] is False

    def test_beraknat_resultat(self, db_session, report_data):
        data = build_income_statement_data(db_session, report_data["company"].id, report_data["fiscal_year"])

        final = [r for r in data["rows"] if r["type"] == "final_result"]
        assert len(final) == 1
        # Revenue 10000 + expense -8000 = 2000
        assert final[0]["period"] == pytest.approx(2000, abs=0.01)


# =============================================================================
# build_general_ledger_data tests
# =============================================================================


class TestBuildGeneralLedgerData:
    """Tests for build_general_ledger_data."""

    def test_running_balance(self, db_session, report_data):
        """Running balance should be IB + cumulative (debit - credit)."""
        data = build_general_ledger_data(db_session, report_data["company"].id, report_data["fiscal_year"])

        # Find account 1510 (IB=10000, one transaction D:12500)
        acc_1510 = [a for a in data["accounts"] if a["account_number"] == 1510][0]
        assert acc_1510["opening_balance"] == pytest.approx(10000, abs=0.01)
        assert len(acc_1510["transactions"]) == 1
        tx = acc_1510["transactions"][0]
        assert tx["debit"] == pytest.approx(12500, abs=0.01)
        assert tx["balance"] == pytest.approx(22500, abs=0.01)  # 10000 + 12500

    def test_closing_balance(self, db_session, report_data):
        data = build_general_ledger_data(db_session, report_data["company"].id, report_data["fiscal_year"])

        acc_1910 = [a for a in data["accounts"] if a["account_number"] == 1910][0]
        # IB=50000, C:8000 → closing = 50000 + 0 - 8000 = 42000
        assert acc_1910["closing_balance"] == pytest.approx(42000, abs=0.01)

    def test_grand_totals(self, db_session, report_data):
        data = build_general_ledger_data(db_session, report_data["company"].id, report_data["fiscal_year"])

        # Total debit: 12500 (A1) + 8000 (A2) = 20500
        # Total credit: 10000 + 2500 (A1) + 8000 (A2) = 20500
        assert data["grand_total_debit"] == pytest.approx(20500, abs=0.01)
        assert data["grand_total_credit"] == pytest.approx(20500, abs=0.01)

    def test_pl_accounts_have_zero_opening_balance(self, db_session, report_data):
        """P&L accounts (>=3000) should have opening_balance=0."""
        data = build_general_ledger_data(db_session, report_data["company"].id, report_data["fiscal_year"])

        acc_3000 = [a for a in data["accounts"] if a["account_number"] == 3000][0]
        assert acc_3000["opening_balance"] == 0

        acc_5010 = [a for a in data["accounts"] if a["account_number"] == 5010][0]
        assert acc_5010["opening_balance"] == 0

    def test_inactive_accounts_excluded(self, db_session, report_data):
        """Accounts with no transactions and IB=0 should not appear."""
        data = build_general_ledger_data(db_session, report_data["company"].id, report_data["fiscal_year"])

        account_numbers = [a["account_number"] for a in data["accounts"]]
        # 2099 Årets resultat: balance account but IB=0 and no transactions
        assert 2099 not in account_numbers

    def test_account_count(self, db_session, report_data):
        data = build_general_ledger_data(db_session, report_data["company"].id, report_data["fiscal_year"])

        # Accounts with activity or IB!=0:
        # 1910 (IB=50000, tx), 1510 (IB=10000, tx), 2440 (IB=-5000),
        # 2610 (tx), 3000 (tx), 5010 (tx)
        assert data["account_count"] == 6
