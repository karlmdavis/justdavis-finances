"""Unit tests for bank_accounts.models."""

import pytest

from finances.bank_accounts.models import BankTransaction
from finances.core import FinancialDate, Money


def test_bank_transaction_creation_required_fields():
    """Test creating BankTransaction with only required fields."""
    tx = BankTransaction(
        posted_date=FinancialDate.from_string("2024-12-15"),
        description="SAFEWAY 1616",
        amount=Money.from_cents(-1363),
    )

    assert tx.posted_date == FinancialDate.from_string("2024-12-15")
    assert tx.description == "SAFEWAY 1616"
    assert tx.amount == Money.from_cents(-1363)
    assert tx.merchant is None
    assert tx.transaction_date is None


def test_bank_transaction_immutability():
    """Test that BankTransaction is immutable."""
    tx = BankTransaction(
        posted_date=FinancialDate.from_string("2024-12-15"),
        description="SAFEWAY 1616",
        amount=Money.from_cents(-1363),
    )

    with pytest.raises(AttributeError):
        tx.amount = Money.from_cents(-5000)


def test_bank_transaction_to_dict():
    """Test serialization to dict."""
    tx = BankTransaction(
        posted_date=FinancialDate.from_string("2024-12-15"),
        description="SAFEWAY 1616",
        amount=Money.from_cents(-1363),
        merchant="Safeway",
    )

    result = tx.to_dict()

    assert result["posted_date"] == "2024-12-15"
    assert result["description"] == "SAFEWAY 1616"
    assert result["amount_milliunits"] == -13630
    assert result["merchant"] == "Safeway"


def test_bank_transaction_from_dict():
    """Test deserialization from dict."""
    data = {
        "posted_date": "2024-12-15",
        "description": "SAFEWAY 1616",
        "amount_milliunits": -13630,
        "merchant": "Safeway",
    }

    tx = BankTransaction.from_dict(data)

    assert tx.posted_date == FinancialDate.from_string("2024-12-15")
    assert tx.description == "SAFEWAY 1616"
    assert tx.amount == Money.from_cents(-1363)
    assert tx.merchant == "Safeway"
