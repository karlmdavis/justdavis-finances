"""Tests for Apple Card CSV format handler."""

import pytest

from finances.bank_accounts.format_handlers.apple_card_csv import AppleCardCsvHandler
from finances.core import FinancialDate, Money


@pytest.fixture
def sample_csv(tmp_path):
    """Create a temporary Apple Card CSV file."""
    csv_content = """Transaction Date,Clearing Date,Description,Merchant,Category,Type,Amount (USD),Purchased By
12/30/2024,12/31/2024,"AMAZON MKTPL*ZP5WJ4KK2","Amazon Mktpl*zp5wj4kk2","Other","Purchase","94.52","Karl Davis"
12/29/2024,12/30/2024,"SAFEWAY 1616 444 WMC DRIVE","Safeway","Grocery","Purchase","42.99","Erica Davis"
12/28/2024,12/29/2024,"PAYMENT - THANK YOU","Apple Card","Payment","Payment","-150.00","Karl Davis"
"""

    csv_file = tmp_path / "apple_card_sample.csv"
    csv_file.write_text(csv_content)
    return csv_file


def test_handler_properties():
    """Test handler format_name and supported_extensions."""
    handler = AppleCardCsvHandler()

    assert handler.format_name == "apple_card_csv"
    assert handler.supported_extensions == (".csv",)


def test_parse_transactions(sample_csv):
    """Test parsing Apple Card CSV transactions."""
    handler = AppleCardCsvHandler()
    result = handler.parse(sample_csv)

    assert len(result.transactions) == 3

    # First transaction (purchase - should be negative)
    tx1 = result.transactions[0]
    assert tx1.posted_date == FinancialDate.from_string("2024-12-31")
    assert tx1.transaction_date == FinancialDate.from_string("2024-12-30")
    assert tx1.description == "AMAZON MKTPL*ZP5WJ4KK2"
    assert tx1.merchant == "Amazon Mktpl*zp5wj4kk2"
    assert tx1.amount == Money.from_cents(-9452)  # Flipped sign
    assert tx1.type == "Purchase"
    assert tx1.category == "Other"
    assert tx1.purchased_by == "Karl Davis"

    # Third transaction (payment - should be positive)
    tx3 = result.transactions[2]
    assert tx3.amount == Money.from_cents(15000)  # Flipped sign


def test_parse_no_balances(sample_csv):
    """Test that CSV parsing returns no balance data."""
    handler = AppleCardCsvHandler()
    result = handler.parse(sample_csv)

    assert len(result.balance_points) == 0
    assert result.statement_date is None


def test_parse_invalid_amount_fails(tmp_path):
    """Test parsing fails with invalid amount format."""
    csv_content = """Transaction Date,Clearing Date,Description,Merchant,Category,Type,Amount (USD),Purchased By
12/30/2024,12/31/2024,"TEST","Test","Other","Purchase","---","Karl Davis"
"""

    csv_file = tmp_path / "invalid.csv"
    csv_file.write_text(csv_content)

    handler = AppleCardCsvHandler()

    with pytest.raises(ValueError, match="Invalid amount format"):
        handler.parse(csv_file)
