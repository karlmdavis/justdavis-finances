"""Tests for Chase Credit CSV format handler."""

import pytest

from finances.bank_accounts.format_handlers.chase_credit_csv import ChaseCreditCsvHandler
from finances.core import FinancialDate, Money


@pytest.fixture
def sample_csv(tmp_path):
    """Create a temporary Chase Credit CSV file."""
    csv_content = """Transaction Date,Post Date,Description,Category,Type,Amount,Memo
12/26/2024,12/26/2024,COMCAST / XFINITY,Bills & Utilities,Sale,-219.53,
12/25/2024,12/25/2024,AMAZON.COM*ZE1234567,Shopping,Sale,-45.99,
12/24/2024,12/24/2024,PAYMENT - THANK YOU,Payment/Credit,Payment,500.00,
"""

    csv_file = tmp_path / "chase_credit_sample.csv"
    csv_file.write_text(csv_content)
    return csv_file


def test_handler_properties():
    """Test handler format_name and supported_extensions."""
    handler = ChaseCreditCsvHandler()

    assert handler.format_name == "chase_credit_csv"
    assert handler.supported_extensions == (".csv",)


def test_parse_transactions(sample_csv):
    """Test parsing Chase Credit CSV transactions."""
    handler = ChaseCreditCsvHandler()
    result = handler.parse(sample_csv)

    assert len(result.transactions) == 3

    # First transaction (purchase - negative in CSV, use as-is)
    tx1 = result.transactions[0]
    assert tx1.transaction_date == FinancialDate.from_string("2024-12-26")
    assert tx1.posted_date == FinancialDate.from_string("2024-12-26")
    assert tx1.description == "COMCAST / XFINITY"
    assert tx1.amount == Money.from_cents(-21953)  # Use as-is (already accounting standard)
    assert tx1.type == "Sale"
    assert tx1.category == "Bills & Utilities"
    assert tx1.memo is None  # Empty memo

    # Second transaction (purchase - negative in CSV, use as-is)
    tx2 = result.transactions[1]
    assert tx2.transaction_date == FinancialDate.from_string("2024-12-25")
    assert tx2.posted_date == FinancialDate.from_string("2024-12-25")
    assert tx2.description == "AMAZON.COM*ZE1234567"
    assert tx2.amount == Money.from_cents(-4599)  # Use as-is
    assert tx2.type == "Sale"
    assert tx2.category == "Shopping"
    assert tx2.memo is None

    # Third transaction (payment - positive in CSV, use as-is)
    tx3 = result.transactions[2]
    assert tx3.transaction_date == FinancialDate.from_string("2024-12-24")
    assert tx3.posted_date == FinancialDate.from_string("2024-12-24")
    assert tx3.description == "PAYMENT - THANK YOU"
    assert tx3.amount == Money.from_cents(50000)  # Use as-is
    assert tx3.type == "Payment"
    assert tx3.category == "Payment/Credit"


def test_parse_no_balances(sample_csv):
    """Test that Chase Credit CSV has NO balance points."""
    handler = ChaseCreditCsvHandler()
    result = handler.parse(sample_csv)

    # Credit card CSV doesn't include balance data
    assert len(result.balance_points) == 0


def test_parse_no_statement_date(sample_csv):
    """Test that CSV parsing returns no statement date."""
    handler = ChaseCreditCsvHandler()
    result = handler.parse(sample_csv)

    # CSV doesn't have statement date concept
    assert result.statement_date is None


def test_parse_invalid_amount_fails(tmp_path):
    """Test parsing fails with invalid amount format."""
    csv_content = """Transaction Date,Post Date,Description,Category,Type,Amount,Memo
12/26/2024,12/26/2024,TEST,Shopping,Sale,---,
"""

    csv_file = tmp_path / "invalid.csv"
    csv_file.write_text(csv_content)

    handler = ChaseCreditCsvHandler()

    with pytest.raises(ValueError, match="Invalid amount format"):
        handler.parse(csv_file)
