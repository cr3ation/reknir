"""
Tests for SIE4 import/export service.

Tests cover:
- Account import (#KONTO)
- Opening/closing balances (#IB, #UB) with year index filtering
- Verification import (#VER, #TRANS)
- Fiscal year validation (#RAR 0)
- Overlapping fiscal years detection
- Unbalanced verification prevention (missing accounts)
- Duplicate verification handling
"""

import pytest
from datetime import date
from decimal import Decimal

from app.models.account import Account
from app.models.fiscal_year import FiscalYear
from app.models.verification import Verification, TransactionLine
from app.services import sie4_service


class TestSIE4AccountImport:
    """Tests for account import from SIE4 files."""

    def test_import_accounts_basic(self, db_session, test_company_with_fiscal_year):
        """Import basic accounts from SIE4 file."""
        company, fiscal_year = test_company_with_fiscal_year

        sie4_content = """#FLAGGA 0
#PROGRAM "Test" "1.0"
#FORMAT PC8
#SIETYP 4
#RAR 0 20250101 20251231
#KONTO 1510 "Kundfordringar"
#KONTO 1930 "Företagskonto"
#KONTO 3000 "Försäljning"
"""
        stats = sie4_service.import_sie4(db_session, company.id, fiscal_year.id, sie4_content)

        assert stats["accounts_created"] == 3
        assert stats["errors"] == []

        # Verify accounts exist
        accounts = db_session.query(Account).filter(
            Account.company_id == company.id,
            Account.fiscal_year_id == fiscal_year.id
        ).all()
        account_numbers = [a.account_number for a in accounts]
        assert 1510 in account_numbers
        assert 1930 in account_numbers
        assert 3000 in account_numbers

    def test_import_accounts_with_opening_balance(self, db_session, test_company_with_fiscal_year):
        """Import accounts with opening balances."""
        company, fiscal_year = test_company_with_fiscal_year

        sie4_content = """#FLAGGA 0
#SIETYP 4
#RAR 0 20250101 20251231
#KONTO 1510 "Kundfordringar"
#IB 0 1510 50000.00
"""
        stats = sie4_service.import_sie4(db_session, company.id, fiscal_year.id, sie4_content)

        assert stats["accounts_created"] == 1

        account = db_session.query(Account).filter(
            Account.company_id == company.id,
            Account.account_number == 1510
        ).first()
        assert account is not None
        assert account.opening_balance == Decimal("50000.00")

    def test_import_accounts_with_closing_balance(self, db_session, test_company_with_fiscal_year):
        """Import accounts with closing balances."""
        company, fiscal_year = test_company_with_fiscal_year

        sie4_content = """#FLAGGA 0
#SIETYP 4
#RAR 0 20250101 20251231
#KONTO 1510 "Kundfordringar"
#IB 0 1510 50000.00
#UB 0 1510 75000.00
"""
        stats = sie4_service.import_sie4(db_session, company.id, fiscal_year.id, sie4_content)

        account = db_session.query(Account).filter(
            Account.company_id == company.id,
            Account.account_number == 1510
        ).first()
        assert account.opening_balance == Decimal("50000.00")
        assert account.current_balance == Decimal("75000.00")


class TestSIE4YearIndexFiltering:
    """Tests for year index filtering (#IB 0 vs #IB -1)."""

    def test_only_import_current_year_balances(self, db_session, test_company_with_fiscal_year):
        """Only import balances for year index 0 (current year), ignore -1 (previous year)."""
        company, fiscal_year = test_company_with_fiscal_year

        # This is a real-world scenario: SIE4 file contains both current and previous year
        sie4_content = """#FLAGGA 0
#SIETYP 4
#RAR 0 20250101 20251231
#RAR -1 20240101 20241231
#KONTO 2099 "Årets resultat"
#IB 0 2099 -68063.86
#UB 0 2099 -32327.06
#IB -1 2099 -46262.20
#UB -1 2099 -68063.86
"""
        stats = sie4_service.import_sie4(db_session, company.id, fiscal_year.id, sie4_content)

        account = db_session.query(Account).filter(
            Account.company_id == company.id,
            Account.account_number == 2099
        ).first()

        # Should have year 0 balances, NOT year -1 balances
        assert account.opening_balance == Decimal("-68063.86")
        assert account.current_balance == Decimal("-32327.06")

        # NOT the previous year values
        assert account.opening_balance != Decimal("-46262.20")
        assert account.current_balance != Decimal("-68063.86")

    def test_ignore_previous_year_balances(self, db_session, test_company_with_fiscal_year):
        """Verify that #IB -1 and #UB -1 are completely ignored."""
        company, fiscal_year = test_company_with_fiscal_year

        sie4_content = """#FLAGGA 0
#SIETYP 4
#RAR 0 20250101 20251231
#KONTO 1930 "Företagskonto"
#IB -1 1930 100000.00
#UB -1 1930 150000.00
"""
        stats = sie4_service.import_sie4(db_session, company.id, fiscal_year.id, sie4_content)

        account = db_session.query(Account).filter(
            Account.company_id == company.id,
            Account.account_number == 1930
        ).first()

        # No balances should be set since only -1 was provided
        assert account.opening_balance == Decimal("0")
        assert account.current_balance == Decimal("0")


class TestSIE4FiscalYearValidation:
    """Tests for fiscal year validation (#RAR 0)."""

    def test_warning_when_rar_does_not_match_fiscal_year(self, db_session, test_company_with_fiscal_year):
        """Warn when SIE4 file's #RAR 0 doesn't match selected fiscal year."""
        company, fiscal_year = test_company_with_fiscal_year

        # File is for 2024, but fiscal year is 2025
        sie4_content = """#FLAGGA 0
#SIETYP 4
#RAR 0 20240101 20241231
#KONTO 1510 "Kundfordringar"
"""
        stats = sie4_service.import_sie4(db_session, company.id, fiscal_year.id, sie4_content)

        # Should have a warning about mismatch
        assert len(stats["warnings"]) >= 1
        warning_found = any("matchar inte" in w for w in stats["warnings"])
        assert warning_found, f"Expected mismatch warning, got: {stats['warnings']}"

    def test_no_warning_when_rar_matches_fiscal_year(self, db_session, test_company_with_fiscal_year):
        """No warning when SIE4 file's #RAR 0 matches selected fiscal year."""
        company, fiscal_year = test_company_with_fiscal_year

        sie4_content = """#FLAGGA 0
#SIETYP 4
#RAR 0 20250101 20251231
#KONTO 1510 "Kundfordringar"
"""
        stats = sie4_service.import_sie4(db_session, company.id, fiscal_year.id, sie4_content)

        # Should NOT have a mismatch warning
        mismatch_warnings = [w for w in stats["warnings"] if "matchar inte" in w]
        assert len(mismatch_warnings) == 0

    def test_overlapping_fiscal_years_warning(self, db_session, test_company_with_fiscal_year):
        """Warn when SIE4 file's period overlaps with existing fiscal years."""
        company, fiscal_year = test_company_with_fiscal_year

        # Create another fiscal year that would overlap
        other_fy = FiscalYear(
            company_id=company.id,
            year=2024,
            label="2024",
            start_date=date(2024, 1, 1),
            end_date=date(2024, 12, 31),
            is_closed=False,
        )
        db_session.add(other_fy)
        db_session.commit()

        # SIE4 file that spans 2024-07-01 to 2025-06-30 (overlaps both years)
        sie4_content = """#FLAGGA 0
#SIETYP 4
#RAR 0 20240701 20250630
#KONTO 1510 "Kundfordringar"
"""
        stats = sie4_service.import_sie4(db_session, company.id, fiscal_year.id, sie4_content)

        # Should have overlap warning
        overlap_warnings = [w for w in stats["warnings"] if "överlappar" in w]
        assert len(overlap_warnings) >= 1, f"Expected overlap warning, got: {stats['warnings']}"


class TestSIE4VerificationImport:
    """Tests for verification import from SIE4 files."""

    def test_import_verification_basic(self, db_session, test_company_with_fiscal_year):
        """Import a basic verification with transactions."""
        company, fiscal_year = test_company_with_fiscal_year

        sie4_content = """#FLAGGA 0
#SIETYP 4
#RAR 0 20250101 20251231
#KONTO 1510 "Kundfordringar"
#KONTO 3000 "Försäljning"
#VER "A" 1 20250115 "Faktura 1"
{
#TRANS 1510 {} 10000.00
#TRANS 3000 {} -10000.00
}
"""
        stats = sie4_service.import_sie4(db_session, company.id, fiscal_year.id, sie4_content)

        assert stats["verifications_created"] == 1
        assert stats["errors"] == []

        ver = db_session.query(Verification).filter(
            Verification.company_id == company.id,
            Verification.series == "A",
            Verification.verification_number == 1
        ).first()
        assert ver is not None
        assert ver.description == "Faktura 1"
        assert len(ver.transaction_lines) == 2

    def test_skip_entire_verification_when_account_missing(self, db_session, test_company_with_fiscal_year):
        """Skip entire verification if any account is missing to prevent unbalanced entries."""
        company, fiscal_year = test_company_with_fiscal_year

        sie4_content = """#FLAGGA 0
#SIETYP 4
#RAR 0 20250101 20251231
#KONTO 1510 "Kundfordringar"
#VER "A" 1 20250115 "Faktura med saknat konto"
{
#TRANS 1510 {} 10000.00
#TRANS 3000 {} -10000.00
}
"""
        # Note: Account 3000 is NOT defined in the file

        stats = sie4_service.import_sie4(db_session, company.id, fiscal_year.id, sie4_content)

        # Verification should be skipped entirely
        assert stats["verifications_created"] == 0
        assert stats["verifications_skipped"] == 1

        # Check warning message
        skip_warnings = [w for w in stats["warnings"] if "hoppades över" in w]
        assert len(skip_warnings) >= 1
        assert "3000" in skip_warnings[0]

        # Verify no verification was created
        ver = db_session.query(Verification).filter(
            Verification.company_id == company.id
        ).first()
        assert ver is None

    def test_skip_duplicate_verifications(self, db_session, test_company_with_fiscal_year):
        """Skip verifications that already exist (same series, number, date)."""
        company, fiscal_year = test_company_with_fiscal_year

        sie4_content = """#FLAGGA 0
#SIETYP 4
#RAR 0 20250101 20251231
#KONTO 1510 "Kundfordringar"
#KONTO 3000 "Försäljning"
#VER "A" 1 20250115 "Faktura 1"
{
#TRANS 1510 {} 10000.00
#TRANS 3000 {} -10000.00
}
"""
        # First import
        stats1 = sie4_service.import_sie4(db_session, company.id, fiscal_year.id, sie4_content)
        assert stats1["verifications_created"] == 1

        # Second import with same verification
        stats2 = sie4_service.import_sie4(db_session, company.id, fiscal_year.id, sie4_content)
        assert stats2["verifications_created"] == 0  # Already exists

        # Check for duplicate warning
        dup_warnings = [w for w in stats2["warnings"] if "duplicerade" in w]
        assert len(dup_warnings) >= 1


class TestSIE4EmptyAndInvalidFiles:
    """Tests for empty and invalid SIE4 files."""

    def test_empty_file(self, db_session, test_company_with_fiscal_year):
        """Handle empty file gracefully."""
        company, fiscal_year = test_company_with_fiscal_year

        sie4_content = ""

        stats = sie4_service.import_sie4(db_session, company.id, fiscal_year.id, sie4_content)

        assert stats["accounts_created"] == 0
        assert stats["verifications_created"] == 0
        # Should have error about no commands
        error_found = any("No SIE4 commands" in e for e in stats["errors"])
        assert error_found

    def test_file_with_only_comments(self, db_session, test_company_with_fiscal_year):
        """Handle file with only comments/whitespace."""
        company, fiscal_year = test_company_with_fiscal_year

        sie4_content = """
# This is a comment
# Another comment

"""
        stats = sie4_service.import_sie4(db_session, company.id, fiscal_year.id, sie4_content)

        assert stats["accounts_created"] == 0
        error_found = any("No SIE4 commands" in e for e in stats["errors"])
        assert error_found


class TestSIE4Export:
    """Tests for SIE4 export functionality."""

    def test_export_basic(self, db_session, test_company_with_fiscal_year):
        """Export a company to SIE4 format."""
        company, fiscal_year = test_company_with_fiscal_year

        # Create some accounts
        account = Account(
            company_id=company.id,
            fiscal_year_id=fiscal_year.id,
            account_number=1510,
            name="Kundfordringar",
            account_type="asset",
            active=True,
            opening_balance=Decimal("10000"),
            current_balance=Decimal("15000"),
        )
        db_session.add(account)
        db_session.commit()

        sie4_content = sie4_service.export_sie4(db_session, company.id, fiscal_year.id)

        # Check basic structure
        assert "#FLAGGA 0" in sie4_content
        assert "#SIETYP 4" in sie4_content
        assert f'#FNAMN "{company.name}"' in sie4_content
        assert '#KONTO 1510 "Kundfordringar"' in sie4_content
        assert "#IB 0 1510 10000" in sie4_content
        assert "#UB 0 1510 15000" in sie4_content


class TestSIE4HelperFunctions:
    """Tests for internal helper functions."""

    def test_parse_rar_from_file(self):
        """Test parsing #RAR 0 from file content."""
        content = """#FLAGGA 0
#RAR 0 20250101 20251231
#RAR -1 20240101 20241231
#KONTO 1510 "Test"
"""
        result = sie4_service._parse_rar_from_file(content)
        assert result is not None
        assert result[0] == date(2025, 1, 1)
        assert result[1] == date(2025, 12, 31)

    def test_parse_rar_from_file_not_found(self):
        """Return None when #RAR 0 not in file."""
        content = """#FLAGGA 0
#KONTO 1510 "Test"
"""
        result = sie4_service._parse_rar_from_file(content)
        assert result is None

    def test_determine_account_type(self):
        """Test account type determination from account number."""
        assert sie4_service._determine_account_type(1510).value == "asset"
        assert sie4_service._determine_account_type(2099).value == "equity_liability"
        assert sie4_service._determine_account_type(3000).value == "revenue"
        assert sie4_service._determine_account_type(4000).value == "cost_goods"
        assert sie4_service._determine_account_type(5000).value == "cost_local"
        assert sie4_service._determine_account_type(6000).value == "cost_other"
        assert sie4_service._determine_account_type(7000).value == "cost_personnel"
        assert sie4_service._determine_account_type(8000).value == "cost_misc"
