"""Tests for Chase Credit QIF format handler."""

import pytest

from finances.bank_accounts.format_handlers.chase_credit_qif import ChaseCreditQifHandler
from finances.core import FinancialDate, Money


@pytest.fixture
def sample_qif(tmp_path):
    """Create a temporary Chase Credit QIF file."""
    qif_content = """!Type:CCard
D12/26/2024
CN/A
PCOMCAST / XFINITY
T-219.53
^
D12/25/2024
CN/A
PAMAZON.COM*ZE1234567
T-45.99
^
D12/24/2024
CN/A
PPAYMENT - THANK YOU
T500.00
^
"""

    qif_file = tmp_path / "chase_credit_sample.qif"
    qif_file.write_text(qif_content)
    return qif_file


def test_handler_properties():
    """Test handler format_name and supported_extensions."""
    handler = ChaseCreditQifHandler()

    assert handler.format_name == "chase_credit_qif"
    assert handler.supported_extensions == (".qif",)


def test_parse_transactions(sample_qif):
    """Test parsing Chase Credit QIF transactions."""
    handler = ChaseCreditQifHandler()
    result = handler.parse(sample_qif)

    assert len(result.transactions) == 3

    # First transaction (purchase - negative in QIF, use as-is)
    tx1 = result.transactions[0]
    assert tx1.posted_date == FinancialDate.from_string("2024-12-26")
    assert tx1.description == "COMCAST / XFINITY"
    assert tx1.amount == Money.from_cents(-21953)  # Use as-is (already accounting standard)
    assert tx1.cleared_status == "N/A"

    # Second transaction (purchase - negative in QIF, use as-is)
    tx2 = result.transactions[1]
    assert tx2.posted_date == FinancialDate.from_string("2024-12-25")
    assert tx2.description == "AMAZON.COM*ZE1234567"
    assert tx2.amount == Money.from_cents(-4599)  # Use as-is
    assert tx2.cleared_status == "N/A"

    # Third transaction (payment - positive in QIF, use as-is)
    tx3 = result.transactions[2]
    assert tx3.posted_date == FinancialDate.from_string("2024-12-24")
    assert tx3.description == "PAYMENT - THANK YOU"
    assert tx3.amount == Money.from_cents(50000)  # Use as-is
    assert tx3.cleared_status == "N/A"


def test_parse_no_balances(sample_qif):
    """Test that Chase Credit QIF has NO balance points."""
    handler = ChaseCreditQifHandler()
    result = handler.parse(sample_qif)

    # QIF doesn't include balance data for Chase credit
    assert len(result.balance_points) == 0


def test_parse_no_statement_date(sample_qif):
    """Test that QIF parsing returns no statement date."""
    handler = ChaseCreditQifHandler()
    result = handler.parse(sample_qif)

    # QIF doesn't have statement date concept
    assert result.statement_date is None


def test_validate_file_success(sample_qif):
    """Test validating a correct Chase Credit QIF file."""
    handler = ChaseCreditQifHandler()

    assert handler.validate_file(sample_qif) is True


def test_validate_file_wrong_extension(tmp_path):
    """Test validation fails for wrong file extension."""
    handler = ChaseCreditQifHandler()
    txt_file = tmp_path / "test.txt"
    txt_file.write_text("test")

    assert handler.validate_file(txt_file) is False


def test_parse_invalid_amount_fails(tmp_path):
    """Test parsing fails with invalid amount format."""
    qif_content = """!Type:CCard
D12/26/2024
PTEST
T---
^
"""

    qif_file = tmp_path / "invalid.qif"
    qif_file.write_text(qif_content)

    handler = ChaseCreditQifHandler()

    with pytest.raises(ValueError, match="Invalid amount format"):
        handler.parse(qif_file)


def test_parse_missing_payee_defaults_to_unknown(tmp_path):
    """Test parsing handles missing payee with default value."""
    qif_content = """!Type:CCard
D12/26/2024
T-100.00
^
"""

    qif_file = tmp_path / "missing_payee.qif"
    qif_file.write_text(qif_content)

    handler = ChaseCreditQifHandler()
    result = handler.parse(qif_file)

    assert len(result.transactions) == 1
    assert result.transactions[0].description == "Unknown"


def test_validate_file_missing_header(tmp_path):
    """Test validation fails for missing QIF header."""
    qif_content = """D12/26/2024
PTEST
T-100.00
^
"""

    qif_file = tmp_path / "no_header.qif"
    qif_file.write_text(qif_content)

    handler = ChaseCreditQifHandler()

    assert handler.validate_file(qif_file) is False
