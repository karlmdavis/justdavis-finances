"""Tests for Chase Checking CSV format handler."""

import pytest

from finances.bank_accounts.format_handlers.chase_checking_csv import ChaseCheckingCsvHandler
from finances.core import FinancialDate, Money


@pytest.fixture
def sample_csv(tmp_path):
    """Create a temporary Chase Checking CSV file."""
    csv_content = """Details,Posting Date,Description,Amount,Type,Balance,Check or Slip #
DEBIT,12/24/2024,"PROTECTIVE LIFE INS. PREM...",-103.83,ACH_DEBIT,40559.83,
CREDIT,12/23/2024,"PAYCHECK DEPOSIT",2500.00,ACH_CREDIT,40663.66,
DEBIT,12/22/2024,"SAFEWAY 1616",-42.99,DEBIT,38163.66,
"""

    csv_file = tmp_path / "chase_checking_sample.csv"
    csv_file.write_text(csv_content)
    return csv_file


def test_handler_properties():
    """Test handler format_name and supported_extensions."""
    handler = ChaseCheckingCsvHandler()

    assert handler.format_name == "chase_checking_csv"
    assert handler.supported_extensions == (".csv",)


def test_parse_transactions(sample_csv):
    """Test parsing Chase Checking CSV transactions."""
    handler = ChaseCheckingCsvHandler()
    result = handler.parse(sample_csv)

    assert len(result.transactions) == 3

    # First transaction (debit - negative in CSV, use as-is)
    tx1 = result.transactions[0]
    assert tx1.posted_date == FinancialDate.from_string("2024-12-24")
    assert tx1.description == "PROTECTIVE LIFE INS. PREM..."
    assert tx1.amount == Money.from_cents(-10383)  # Use as-is (already accounting standard)
    assert tx1.type == "ACH_DEBIT"
    assert tx1.running_balance == Money.from_cents(4055983)
    assert tx1.check_number is None  # Empty check number

    # Second transaction (credit - positive in CSV, use as-is)
    tx2 = result.transactions[1]
    assert tx2.posted_date == FinancialDate.from_string("2024-12-23")
    assert tx2.description == "PAYCHECK DEPOSIT"
    assert tx2.amount == Money.from_cents(250000)  # Use as-is
    assert tx2.type == "ACH_CREDIT"
    assert tx2.running_balance == Money.from_cents(4066366)

    # Third transaction (debit)
    tx3 = result.transactions[2]
    assert tx3.posted_date == FinancialDate.from_string("2024-12-22")
    assert tx3.description == "SAFEWAY 1616"
    assert tx3.amount == Money.from_cents(-4299)  # Use as-is
    assert tx3.type == "DEBIT"
    assert tx3.running_balance == Money.from_cents(3816366)


def test_parse_running_balances(sample_csv):
    """Test parsing running balance points from Chase CSV."""
    handler = ChaseCheckingCsvHandler()
    result = handler.parse(sample_csv)

    # Chase CSV has running balance per transaction
    assert len(result.balance_points) == 3

    # Balance points should match transaction running balances
    bp1 = result.balance_points[0]
    assert bp1.date == FinancialDate.from_string("2024-12-24")
    assert bp1.amount == Money.from_cents(4055983)
    assert bp1.available is None  # Checking accounts don't have available balance

    bp2 = result.balance_points[1]
    assert bp2.date == FinancialDate.from_string("2024-12-23")
    assert bp2.amount == Money.from_cents(4066366)

    bp3 = result.balance_points[2]
    assert bp3.date == FinancialDate.from_string("2024-12-22")
    assert bp3.amount == Money.from_cents(3816366)


def test_parse_no_statement_date(sample_csv):
    """Test that CSV parsing returns no statement date."""
    handler = ChaseCheckingCsvHandler()
    result = handler.parse(sample_csv)

    # CSV doesn't have statement date concept
    assert result.statement_date is None


def test_validate_file_success(sample_csv):
    """Test validating a correct Chase Checking CSV file."""
    handler = ChaseCheckingCsvHandler()

    assert handler.validate_file(sample_csv) is True


def test_validate_file_wrong_extension(tmp_path):
    """Test validation fails for wrong file extension."""
    handler = ChaseCheckingCsvHandler()
    txt_file = tmp_path / "test.txt"
    txt_file.write_text("test")

    assert handler.validate_file(txt_file) is False


def test_parse_invalid_amount_fails(tmp_path):
    """Test parsing fails with invalid amount format."""
    csv_content = """Details,Posting Date,Description,Amount,Type,Balance,Check or Slip #
DEBIT,12/24/2024,"TEST","---",ACH_DEBIT,40559.83,
"""

    csv_file = tmp_path / "invalid.csv"
    csv_file.write_text(csv_content)

    handler = ChaseCheckingCsvHandler()

    with pytest.raises(ValueError, match="Invalid amount format"):
        handler.parse(csv_file)
