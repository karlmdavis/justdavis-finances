"""Unit tests for Apple parser selector utilities."""

import pytest
from bs4 import BeautifulSoup

from finances.apple.parser import AppleReceiptParser
from finances.core import FinancialDate


class TestSelectorUtilities:
    """Test selector utility methods with size validation."""

    def test_select_large_container_accepts_200_chars(self):
        """Large container selector allows up to 200 characters."""
        html = f"<div class='container'>{'x' * 200}</div>"
        soup = BeautifulSoup(html, "html.parser")
        parser = AppleReceiptParser()

        result = parser._select_large_container(soup, "div.container")
        assert result is not None
        assert len(result) == 200

    def test_select_large_container_rejects_201_chars(self):
        """Large container selector throws on >200 characters."""
        html = f"<div class='container'>{'x' * 201}</div>"
        soup = BeautifulSoup(html, "html.parser")
        parser = AppleReceiptParser()

        with pytest.raises(ValueError, match=r"captured 201 chars.*likely matched a container"):
            parser._select_large_container(soup, "div.container")

    def test_select_small_container_accepts_80_chars(self):
        """Small container selector allows up to 80 characters."""
        html = f"<td class='label'>{'x' * 80}</td>"
        soup = BeautifulSoup(html, "html.parser")
        parser = AppleReceiptParser()

        result = parser._select_small_container(soup, "td.label")
        assert result is not None
        assert len(result) == 80

    def test_select_small_container_rejects_81_chars(self):
        """Small container selector throws on >80 characters."""
        html = f"<td class='label'>{'x' * 81}</td>"
        soup = BeautifulSoup(html, "html.parser")
        parser = AppleReceiptParser()

        with pytest.raises(ValueError, match=r"captured 81 chars.*exceeded small container limit"):
            parser._select_small_container(soup, "td.label")

    def test_select_value_accepts_80_chars(self):
        """Value selector allows up to 80 characters."""
        html = f"<span class='value'>{'$' + '9' * 79}</span>"
        soup = BeautifulSoup(html, "html.parser")
        parser = AppleReceiptParser()

        result = parser._select_value(soup, "span.value")
        assert result is not None
        assert len(result) == 80

    def test_select_value_rejects_81_chars(self):
        """Value selector throws on >80 characters."""
        html = f"<span class='value'>{'$' + '9' * 80}</span>"
        soup = BeautifulSoup(html, "html.parser")
        parser = AppleReceiptParser()

        with pytest.raises(ValueError, match=r"captured 81 chars.*exceeded value limit"):
            parser._select_value(soup, "span.value")

    def test_select_value_returns_none_when_not_found(self):
        """Value selector returns None when element not found."""
        html = "<div>no matching element</div>"
        soup = BeautifulSoup(html, "html.parser")
        parser = AppleReceiptParser()

        result = parser._select_value(soup, "span.missing")
        assert result is None


def test_format_detection_uses_new_names():
    """Format detection returns 'table_format' and 'modern_format', not legacy names."""
    # Table format (2020-era)
    table_html = """
    <table class="aapl-desktop-tbl">
      <tr><td>APPLE ID</td><td>test@example.com</td></tr>
    </table>
    """
    soup = BeautifulSoup(table_html, "html.parser")
    parser = AppleReceiptParser()
    format_name = parser._detect_format(soup)
    assert format_name == "table_format"

    # Modern format (2025+)
    modern_html = """
    <div class="custom-hzv07h">
      <p>Apple Account: test@example.com</p>
    </div>
    """
    soup = BeautifulSoup(modern_html, "html.parser")
    format_name = parser._detect_format(soup)
    assert format_name == "modern_format"


def test_modern_format_extract_date():
    """Extract date from modern format 'October 11, 2025' → FinancialDate."""
    html = """
    <div><p class="custom-18w16cf">October 11, 2025</p></div>
    """
    soup = BeautifulSoup(html, "html.parser")
    parser = AppleReceiptParser()

    date = parser._extract_modern_format_date(soup)
    assert date is not None
    assert date == FinancialDate.from_string("2025-10-11")


def test_parse_currency_standard_formats():
    """Verify _parse_currency handles standard currency formats with integer-only arithmetic."""
    parser = AppleReceiptParser()

    # Standard dollar.cents format
    assert parser._parse_currency("$12.34") == 1234
    assert parser._parse_currency("$0.99") == 99
    assert parser._parse_currency("$100.00") == 10000

    # With whitespace
    assert parser._parse_currency("$ 12.34") == 1234
    assert parser._parse_currency("$  0.99") == 99

    # Embedded in text (should extract currency)
    assert parser._parse_currency("Total: $12.34") == 1234
    assert parser._parse_currency("Amount $99.99 paid") == 9999


def test_parse_currency_edge_cases():
    """Verify _parse_currency handles edge cases correctly."""
    parser = AppleReceiptParser()

    # Single cent digit (should pad to two digits)
    assert parser._parse_currency("$12.3") == 1230
    assert parser._parse_currency("$12.0") == 1200

    # No cents (dollars only)
    assert parser._parse_currency("$12") == 1200
    assert parser._parse_currency("$100") == 10000

    # Zero amounts
    assert parser._parse_currency("$0.00") == 0
    assert parser._parse_currency("$0") == 0


def test_parse_currency_invalid_input():
    """Verify _parse_currency returns None for invalid input."""
    parser = AppleReceiptParser()

    # Non-currency text (no currency symbol)
    assert parser._parse_currency("not a price") is None
    assert parser._parse_currency("") is None
    assert parser._parse_currency("abc") is None
    assert parser._parse_currency("12.34") is None  # Missing $ symbol

    # Malformed currency
    assert parser._parse_currency("$") is None
    assert parser._parse_currency("$.") is None
    assert parser._parse_currency("$ .") is None
