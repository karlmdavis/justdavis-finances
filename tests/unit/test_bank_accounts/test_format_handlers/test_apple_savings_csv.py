"""Tests for Apple Savings CSV format handler."""

from pathlib import Path

import pytest

from finances.bank_accounts.format_handlers.apple_savings_csv import AppleSavingsCsvHandler
from finances.core import FinancialDate, Money


@pytest.fixture
def sample_csv():
    """Return path to sample Apple Savings CSV fixture."""
    # Navigate from tests/unit/test_bank_accounts/test_format_handlers/ to tests/fixtures/
    return (
        Path(__file__).parent.parent.parent.parent
        / "fixtures"
        / "bank_accounts"
        / "raw"
        / "apple_savings_sample.csv"
    )


def test_handler_properties():
    """Test handler format_name and supported_extensions."""
    handler = AppleSavingsCsvHandler()

    assert handler.format_name == "apple_savings_csv"
    assert handler.supported_extensions == (".csv",)


def test_parse_transactions(sample_csv):
    """Test parsing Apple Savings CSV transactions."""
    handler = AppleSavingsCsvHandler()
    result = handler.parse(sample_csv)

    assert len(result.transactions) == 3

    # First transaction (interest - consumer positive, should be flipped to negative)
    tx1 = result.transactions[0]
    assert tx1.posted_date == FinancialDate.from_string("2024-12-31")
    assert tx1.transaction_date == FinancialDate.from_string("2024-12-30")
    assert tx1.description == "Interest Earned"
    assert tx1.amount == Money.from_cents(-125)  # Flipped sign (deposit → negative)
    assert tx1.type == "Interest"

    # Second transaction (withdrawal - consumer negative, should be flipped to positive)
    tx2 = result.transactions[1]
    assert tx2.posted_date == FinancialDate.from_string("2024-12-30")
    assert tx2.transaction_date == FinancialDate.from_string("2024-12-29")
    assert tx2.description == "Withdrawal to Apple Card"
    assert tx2.amount == Money.from_cents(50000)  # Flipped sign (withdrawal → positive)
    assert tx2.type == "Transfer"

    # Third transaction (deposit - consumer positive, should be flipped to negative)
    tx3 = result.transactions[2]
    assert tx3.posted_date == FinancialDate.from_string("2024-12-29")
    assert tx3.transaction_date == FinancialDate.from_string("2024-12-28")
    assert tx3.description == "Deposit from Checking"
    assert tx3.amount == Money.from_cents(-100000)  # Flipped sign (deposit → negative)
    assert tx3.type == "Transfer"


def test_parse_no_balances(sample_csv):
    """Test that CSV parsing returns no balance data (balance column unreliable)."""
    handler = AppleSavingsCsvHandler()
    result = handler.parse(sample_csv)

    assert len(result.balance_points) == 0
    assert result.statement_date is None


def test_validate_file_success(sample_csv):
    """Test validating a correct Apple Savings CSV file."""
    handler = AppleSavingsCsvHandler()

    assert handler.validate_file(sample_csv) is True


def test_validate_file_wrong_extension(tmp_path):
    """Test validation fails for wrong file extension."""
    handler = AppleSavingsCsvHandler()
    txt_file = tmp_path / "test.txt"
    txt_file.write_text("test")

    assert handler.validate_file(txt_file) is False


def test_parse_invalid_amount_fails(tmp_path):
    """Test parsing fails with invalid amount format."""
    csv_content = """Transaction Date,Clearing Date,Description,Amount (USD),Transaction Type,Balance (USD)
12/30/2024,12/31/2024,"TEST","---","Interest",42053.56
"""

    csv_file = tmp_path / "invalid.csv"
    csv_file.write_text(csv_content)

    handler = AppleSavingsCsvHandler()

    with pytest.raises(ValueError, match="Invalid amount format"):
        handler.parse(csv_file)
