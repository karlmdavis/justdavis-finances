"""Unit tests for bank_accounts.models."""

import pytest

from finances.bank_accounts.models import BalancePoint, BalanceReconciliationPoint, BankTransaction
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

    # Test immutability - frozen dataclass should prevent attribute assignment
    with pytest.raises(AttributeError):
        tx.amount = Money.from_cents(-5000)  # type: ignore[misc,unused-ignore]


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


def test_balance_point_creation():
    """Test creating BalancePoint with required fields."""
    balance = BalancePoint(date=FinancialDate.from_string("2024-12-31"), amount=Money.from_cents(-18283090))

    assert balance.date == FinancialDate.from_string("2024-12-31")
    assert balance.amount == Money.from_cents(-18283090)
    assert balance.available is None


def test_balance_point_with_available():
    """Test BalancePoint with available balance (credit accounts)."""
    balance = BalancePoint(
        date=FinancialDate.from_string("2024-12-31"),
        amount=Money.from_cents(-18283090),
        available=Money.from_cents(21716910),
    )

    assert balance.available == Money.from_cents(21716910)


def test_balance_point_serialization():
    """Test to_dict and from_dict."""
    balance = BalancePoint(
        date=FinancialDate.from_string("2024-12-31"),
        amount=Money.from_cents(-18283090),
        available=Money.from_cents(21716910),
    )

    data = balance.to_dict()
    assert data["date"] == "2024-12-31"
    assert data["amount_milliunits"] == -182830900
    assert data["available_milliunits"] == 217169100

    restored = BalancePoint.from_dict(data)
    assert restored == balance


def test_balance_reconciliation_point_reconciled():
    """Test BalanceReconciliationPoint when balances match."""
    point = BalanceReconciliationPoint(
        date=FinancialDate.from_string("2024-11-30"),
        bank_balance=Money.from_cents(-1523456),
        ynab_balance=Money.from_cents(-1523456),
        bank_txs_not_in_ynab=Money.from_cents(0),
        ynab_txs_not_in_bank=Money.from_cents(0),
        adjusted_bank_balance=Money.from_cents(-1523456),
        adjusted_ynab_balance=Money.from_cents(-1523456),
        is_reconciled=True,
        difference=Money.from_cents(0),
    )

    assert point.is_reconciled is True
    assert point.difference == Money.from_cents(0)


def test_balance_reconciliation_point_diverged():
    """Test BalanceReconciliationPoint when balances differ."""
    point = BalanceReconciliationPoint(
        date=FinancialDate.from_string("2024-12-31"),
        bank_balance=Money.from_cents(-1828309),
        ynab_balance=Money.from_cents(-1814606),
        bank_txs_not_in_ynab=Money.from_cents(-13703),
        ynab_txs_not_in_bank=Money.from_cents(0),
        adjusted_bank_balance=Money.from_cents(-1814606),
        adjusted_ynab_balance=Money.from_cents(-1814606),
        is_reconciled=True,
        difference=Money.from_cents(0),
    )

    # Even though raw balances differ, adjusted balances match
    assert point.is_reconciled is True


def test_balance_reconciliation_point_serialization():
    """Test to_dict and from_dict round-trip."""
    point = BalanceReconciliationPoint(
        date=FinancialDate.from_string("2024-12-31"),
        bank_balance=Money.from_cents(-1828309),
        ynab_balance=Money.from_cents(-1814606),
        bank_txs_not_in_ynab=Money.from_cents(-13703),
        ynab_txs_not_in_bank=Money.from_cents(0),
        adjusted_bank_balance=Money.from_cents(-1814606),
        adjusted_ynab_balance=Money.from_cents(-1814606),
        is_reconciled=True,
        difference=Money.from_cents(0),
    )

    data = point.to_dict()
    assert data["date"] == "2024-12-31"
    assert data["bank_balance_milliunits"] == -18283090
    assert data["ynab_balance_milliunits"] == -18146060
    assert data["bank_txs_not_in_ynab_milliunits"] == -137030
    assert data["ynab_txs_not_in_bank_milliunits"] == 0
    assert data["adjusted_bank_balance_milliunits"] == -18146060
    assert data["adjusted_ynab_balance_milliunits"] == -18146060
    assert data["is_reconciled"] is True
    assert data["difference_milliunits"] == 0

    restored = BalanceReconciliationPoint.from_dict(data)
    assert restored == point
