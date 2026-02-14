"""
Tests for format_sek() Swedish number formatting.
"""

from decimal import Decimal

from app.services.pdf_service import format_sek


class TestFormatSek:
    """Tests for Swedish number formatting."""

    def test_integer(self):
        assert format_sek(1000) == "1 000,00"

    def test_float_with_decimals(self):
        assert format_sek(1234.56) == "1 234,56"

    def test_negative_number(self):
        assert format_sek(-5000) == "-5 000,00"

    def test_zero(self):
        assert format_sek(0) == "0,00"

    def test_none_returns_empty(self):
        assert format_sek(None) == ""

    def test_custom_decimals_zero(self):
        assert format_sek(1234.5, decimals=0) == "1 234"

    def test_large_number(self):
        assert format_sek(1000000) == "1 000 000,00"

    def test_decimal_type(self):
        assert format_sek(Decimal("1234.56")) == "1 234,56"

    def test_small_decimal(self):
        assert format_sek(0.5) == "0,50"

    def test_negative_decimal(self):
        assert format_sek(Decimal("-68063.86")) == "-68 063,86"
