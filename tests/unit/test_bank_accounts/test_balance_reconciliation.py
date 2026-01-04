"""Tests for balance reconciliation logic."""

from finances.bank_accounts.balance_reconciliation import (
    build_balance_reconciliation,
    reconcile_balance_point,
)
from finances.bank_accounts.matching import YnabTransaction
from finances.bank_accounts.models import BalancePoint, BankTransaction
from finances.core import FinancialDate, Money


def test_reconcile_balance_point_exact_match():
    """Test reconciliation when balances match exactly."""
    date = FinancialDate.from_string("2024-01-15")
    bank_balance = Money.from_cents(100000)  # $1000.00
    ynab_balance = Money.from_cents(100000)
    unmatched_bank = Money.from_cents(0)
    unmatched_ynab = Money.from_cents(0)

    point = reconcile_balance_point(date, bank_balance, ynab_balance, unmatched_bank, unmatched_ynab)

    assert point.date == date
    assert point.bank_balance == bank_balance
    assert point.ynab_balance == ynab_balance
    assert point.bank_txs_not_in_ynab == Money.from_cents(0)
    assert point.ynab_txs_not_in_bank == Money.from_cents(0)
    assert point.adjusted_bank_balance == Money.from_cents(100000)
    assert point.adjusted_ynab_balance == Money.from_cents(100000)
    assert point.is_reconciled is True
    assert point.difference == Money.from_cents(0)


def test_reconcile_balance_point_with_bank_adjustment():
    """Test reconciliation with missing bank transaction adjustment."""
    date = FinancialDate.from_string("2024-01-15")
    bank_balance = Money.from_cents(100000)  # $1000.00
    ynab_balance = Money.from_cents(95000)  # $950.00
    unmatched_bank = Money.from_cents(-5000)  # Missing $50 expense

    point = reconcile_balance_point(date, bank_balance, ynab_balance, unmatched_bank, Money.from_cents(0))

    assert point.adjusted_bank_balance == Money.from_cents(95000)
    assert point.adjusted_ynab_balance == Money.from_cents(95000)
    assert point.is_reconciled is True
    assert point.difference == Money.from_cents(0)


def test_reconcile_balance_point_with_ynab_adjustment():
    """Test reconciliation with missing YNAB transaction adjustment."""
    date = FinancialDate.from_string("2024-01-15")
    bank_balance = Money.from_cents(95000)  # $950.00
    ynab_balance = Money.from_cents(100000)  # $1000.00
    unmatched_ynab = Money.from_cents(-5000)  # Missing $50 expense

    point = reconcile_balance_point(date, bank_balance, ynab_balance, Money.from_cents(0), unmatched_ynab)

    assert point.adjusted_bank_balance == Money.from_cents(95000)
    assert point.adjusted_ynab_balance == Money.from_cents(95000)
    assert point.is_reconciled is True
    assert point.difference == Money.from_cents(0)


def test_reconcile_balance_point_diverged():
    """Test reconciliation when balances diverge."""
    date = FinancialDate.from_string("2024-01-15")
    bank_balance = Money.from_cents(100000)  # $1000.00
    ynab_balance = Money.from_cents(95000)  # $950.00

    point = reconcile_balance_point(
        date, bank_balance, ynab_balance, Money.from_cents(0), Money.from_cents(0)
    )

    assert point.adjusted_bank_balance == Money.from_cents(100000)
    assert point.adjusted_ynab_balance == Money.from_cents(95000)
    assert point.is_reconciled is False
    assert point.difference == Money.from_cents(5000)  # $50 difference


def test_reconcile_balance_point_with_both_adjustments():
    """Test reconciliation with both bank and YNAB adjustments."""
    date = FinancialDate.from_string("2024-01-15")
    bank_balance = Money.from_cents(100000)  # $1000.00
    ynab_balance = Money.from_cents(98000)  # $980.00
    unmatched_bank = Money.from_cents(-3000)  # Missing $30 expense in bank
    unmatched_ynab = Money.from_cents(1000)  # Missing $10 income in YNAB

    point = reconcile_balance_point(date, bank_balance, ynab_balance, unmatched_bank, unmatched_ynab)

    assert point.adjusted_bank_balance == Money.from_cents(97000)  # 100000 - 3000
    assert point.adjusted_ynab_balance == Money.from_cents(99000)  # 98000 + 1000
    assert point.is_reconciled is False
    assert point.difference == Money.from_cents(-2000)  # 97000 - 99000


def test_build_balance_reconciliation_all_reconciled():
    """Test building reconciliation when all points reconcile."""
    account_id = "chase-checking"

    balance_points = [
        BalancePoint(
            date=FinancialDate.from_string("2024-01-10"),
            amount=Money.from_cents(100000),
        ),
        BalancePoint(
            date=FinancialDate.from_string("2024-01-20"),
            amount=Money.from_cents(95000),
        ),
        BalancePoint(
            date=FinancialDate.from_string("2024-01-30"),
            amount=Money.from_cents(90000),
        ),
    ]

    ynab_balances = {
        FinancialDate.from_string("2024-01-10"): Money.from_cents(100000),
        FinancialDate.from_string("2024-01-20"): Money.from_cents(95000),
        FinancialDate.from_string("2024-01-30"): Money.from_cents(90000),
    }

    reconciliation = build_balance_reconciliation(account_id, balance_points, ynab_balances, [], [])

    assert reconciliation.account_id == account_id
    assert len(reconciliation.points) == 3
    assert all(p.is_reconciled for p in reconciliation.points)
    assert reconciliation.last_reconciled_date == FinancialDate.from_string("2024-01-30")
    assert reconciliation.first_diverged_date is None


def test_build_balance_reconciliation_with_divergence():
    """Test building reconciliation with diverged points."""
    account_id = "chase-checking"

    balance_points = [
        BalancePoint(
            date=FinancialDate.from_string("2024-01-10"),
            amount=Money.from_cents(100000),
        ),
        BalancePoint(
            date=FinancialDate.from_string("2024-01-20"),
            amount=Money.from_cents(95000),
        ),
        BalancePoint(
            date=FinancialDate.from_string("2024-01-30"),
            amount=Money.from_cents(90000),
        ),
    ]

    ynab_balances = {
        FinancialDate.from_string("2024-01-10"): Money.from_cents(100000),
        FinancialDate.from_string("2024-01-20"): Money.from_cents(96000),  # Different
        FinancialDate.from_string("2024-01-30"): Money.from_cents(91000),  # Different
    }

    reconciliation = build_balance_reconciliation(account_id, balance_points, ynab_balances, [], [])

    assert reconciliation.account_id == account_id
    assert len(reconciliation.points) == 3
    assert reconciliation.points[0].is_reconciled is True
    assert reconciliation.points[1].is_reconciled is False
    assert reconciliation.points[2].is_reconciled is False
    assert reconciliation.last_reconciled_date == FinancialDate.from_string("2024-01-10")
    assert reconciliation.first_diverged_date == FinancialDate.from_string("2024-01-20")


def test_build_balance_reconciliation_with_unmatched_transactions():
    """Test building reconciliation with unmatched transactions."""
    account_id = "chase-checking"

    balance_points = [
        BalancePoint(
            date=FinancialDate.from_string("2024-01-10"),
            amount=Money.from_cents(100000),
        ),
        BalancePoint(
            date=FinancialDate.from_string("2024-01-20"),
            amount=Money.from_cents(95000),
        ),
    ]

    ynab_balances = {
        FinancialDate.from_string("2024-01-10"): Money.from_cents(100000),
        FinancialDate.from_string("2024-01-20"): Money.from_cents(96000),
    }

    # Bank transaction not in YNAB
    unmatched_bank_txs = [
        BankTransaction(
            posted_date=FinancialDate.from_string("2024-01-15"),
            description="Missing in YNAB",
            amount=Money.from_cents(-1000),  # $10 expense
        )
    ]

    # YNAB transaction not in bank (shouldn't affect this example)
    unmatched_ynab_txs: list[YnabTransaction] = []

    reconciliation = build_balance_reconciliation(
        account_id, balance_points, ynab_balances, unmatched_bank_txs, unmatched_ynab_txs
    )

    # First point: before unmatched tx
    assert reconciliation.points[0].bank_txs_not_in_ynab == Money.from_cents(0)
    assert reconciliation.points[0].is_reconciled is True

    # Second point: after unmatched tx
    # Adjusted bank = 95000 + (-1000) = 94000
    # YNAB = 96000
    # Still doesn't match
    assert reconciliation.points[1].bank_txs_not_in_ynab == Money.from_cents(-1000)
    assert reconciliation.points[1].adjusted_bank_balance == Money.from_cents(94000)
    assert reconciliation.points[1].is_reconciled is False


def test_build_balance_reconciliation_cumulative_unmatched():
    """Test that unmatched transactions accumulate over time."""
    account_id = "chase-checking"

    balance_points = [
        BalancePoint(
            date=FinancialDate.from_string("2024-01-10"),
            amount=Money.from_cents(100000),
        ),
        BalancePoint(
            date=FinancialDate.from_string("2024-01-20"),
            amount=Money.from_cents(95000),
        ),
        BalancePoint(
            date=FinancialDate.from_string("2024-01-30"),
            amount=Money.from_cents(90000),
        ),
    ]

    ynab_balances = {
        FinancialDate.from_string("2024-01-10"): Money.from_cents(100000),
        FinancialDate.from_string("2024-01-20"): Money.from_cents(97000),
        FinancialDate.from_string("2024-01-30"): Money.from_cents(92000),
    }

    # Multiple unmatched bank transactions
    unmatched_bank_txs = [
        BankTransaction(
            posted_date=FinancialDate.from_string("2024-01-15"),
            description="Missing 1",
            amount=Money.from_cents(-1000),
        ),
        BankTransaction(
            posted_date=FinancialDate.from_string("2024-01-25"),
            description="Missing 2",
            amount=Money.from_cents(-1000),
        ),
    ]

    reconciliation = build_balance_reconciliation(
        account_id, balance_points, ynab_balances, unmatched_bank_txs, []
    )

    # Point 1 (Jan 10): No unmatched txs yet
    assert reconciliation.points[0].bank_txs_not_in_ynab == Money.from_cents(0)

    # Point 2 (Jan 20): One unmatched tx (-$10)
    # Adjusted bank = 95000 + (-1000) = 94000
    # YNAB = 97000
    assert reconciliation.points[1].bank_txs_not_in_ynab == Money.from_cents(-1000)
    assert reconciliation.points[1].adjusted_bank_balance == Money.from_cents(94000)

    # Point 3 (Jan 30): Two unmatched txs (-$20 total)
    # Adjusted bank = 90000 + (-2000) = 88000
    # YNAB = 92000
    assert reconciliation.points[2].bank_txs_not_in_ynab == Money.from_cents(-2000)
    assert reconciliation.points[2].adjusted_bank_balance == Money.from_cents(88000)
