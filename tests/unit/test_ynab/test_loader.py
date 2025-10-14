#!/usr/bin/env python3
"""Tests for YNAB loader module."""

import pytest

from finances.core import FinancialDate, Money
from finances.ynab import filter_transactions_by_payee
from finances.ynab.models import YnabTransaction


def create_test_transaction(
    tx_id: str,
    date_str: str,
    amount_milliunits: int,
    payee_name: str | None,
) -> YnabTransaction:
    """Helper to create minimal test transaction."""
    return YnabTransaction(
        id=tx_id,
        date=FinancialDate.from_string(date_str),
        amount=Money.from_milliunits(amount_milliunits),
        memo=None,
        cleared="cleared",
        approved=True,
        account_id="acct1",
        account_name="Checking",
        payee_id=None,
        payee_name=payee_name,
        category_id=None,
        category_name=None,
        transfer_account_id=None,
        transfer_transaction_id=None,
        matched_transaction_id=None,
        import_id=None,
        import_payee_name=None,
        import_payee_name_original=None,
        debt_transaction_type=None,
        deleted=False,
    )


class TestFilterTransactions:
    """Test transaction filtering functionality."""

    @pytest.mark.ynab
    def test_filter_by_payee_with_normal_data(self):
        """Test filtering by payee with normal transaction data."""
        transactions = [
            create_test_transaction("tx1", "2025-01-01", -1000, "Apple"),
            create_test_transaction("tx2", "2025-01-02", -2000, "Amazon"),
            create_test_transaction("tx3", "2025-01-03", -3000, "Apple Store"),
        ]

        filtered = filter_transactions_by_payee(transactions, payee="Apple")

        assert len(filtered) == 2
        assert filtered[0].payee_name == "Apple"
        assert filtered[1].payee_name == "Apple Store"

    @pytest.mark.ynab
    def test_filter_by_payee_case_insensitive(self):
        """Test that payee filtering is case-insensitive."""
        transactions = [
            create_test_transaction("tx1", "2025-01-01", -1000, "APPLE"),
            create_test_transaction("tx2", "2025-01-02", -2000, "apple"),
            create_test_transaction("tx3", "2025-01-03", -3000, "ApPlE"),
        ]

        filtered = filter_transactions_by_payee(transactions, payee="apple")

        assert len(filtered) == 3

    @pytest.mark.ynab
    def test_filter_by_payee_with_null_payee_name(self):
        """Test filtering by payee when some transactions have null payee_name."""
        transactions = [
            create_test_transaction("tx1", "2025-01-01", -1000, "Apple"),
            create_test_transaction("tx2", "2025-01-02", -2000, None),  # Split transaction
            create_test_transaction("tx3", "2025-01-03", -3000, "Amazon"),
            create_test_transaction("tx4", "2025-01-04", -4000, "Apple Store"),
        ]

        # Should not crash on null payee_name
        filtered = filter_transactions_by_payee(transactions, payee="Apple")

        assert len(filtered) == 2
        assert filtered[0].payee_name == "Apple"
        assert filtered[1].payee_name == "Apple Store"

    @pytest.mark.ynab
    def test_filter_by_payee_with_empty_string_payee_name(self):
        """Test filtering by payee when some transactions have empty string payee_name."""
        transactions = [
            create_test_transaction("tx1", "2025-01-01", -1000, "Apple"),
            create_test_transaction("tx2", "2025-01-02", -2000, ""),
            create_test_transaction("tx3", "2025-01-03", -3000, "Amazon"),
        ]

        filtered = filter_transactions_by_payee(transactions, payee="Apple")

        assert len(filtered) == 1
        assert filtered[0].payee_name == "Apple"

    @pytest.mark.ynab
    def test_filter_by_payee_multiple_transactions(self):
        """Test filtering by payee with multiple matching transactions."""
        transactions = [
            create_test_transaction("tx1", "2024-12-31", -1000, "Apple"),
            create_test_transaction("tx2", "2025-01-01", -2000, "Apple"),
            create_test_transaction("tx3", "2025-01-15", -3000, "Amazon"),
            create_test_transaction("tx4", "2025-01-31", -4000, "Apple"),
            create_test_transaction("tx5", "2025-02-01", -5000, "Apple"),
        ]

        filtered = filter_transactions_by_payee(transactions, payee="Apple")

        assert len(filtered) == 4
        assert all(tx.payee_name == "Apple" for tx in filtered)

    @pytest.mark.ynab
    def test_filter_with_no_criteria(self):
        """Test that no filtering returns all transactions."""
        transactions = [
            create_test_transaction("tx1", "2025-01-01", -1000, "Apple"),
            create_test_transaction("tx2", "2025-01-02", -2000, "Amazon"),
        ]

        filtered = filter_transactions_by_payee(transactions)

        assert len(filtered) == 2
        assert filtered == transactions
