#!/usr/bin/env python3
"""Tests for YNAB loader module."""

import pytest

from finances.ynab import filter_transactions


class TestFilterTransactions:
    """Test transaction filtering functionality."""

    @pytest.mark.ynab
    def test_filter_by_payee_with_normal_data(self):
        """Test filtering by payee with normal transaction data."""
        transactions = [
            {"date": "2025-01-01", "payee_name": "Apple", "amount": -1000},
            {"date": "2025-01-02", "payee_name": "Amazon", "amount": -2000},
            {"date": "2025-01-03", "payee_name": "Apple Store", "amount": -3000},
        ]

        filtered = filter_transactions(transactions, payee="Apple")

        assert len(filtered) == 2
        assert filtered[0]["payee_name"] == "Apple"
        assert filtered[1]["payee_name"] == "Apple Store"

    @pytest.mark.ynab
    def test_filter_by_payee_case_insensitive(self):
        """Test that payee filtering is case-insensitive."""
        transactions = [
            {"date": "2025-01-01", "payee_name": "APPLE", "amount": -1000},
            {"date": "2025-01-02", "payee_name": "apple", "amount": -2000},
            {"date": "2025-01-03", "payee_name": "ApPlE", "amount": -3000},
        ]

        filtered = filter_transactions(transactions, payee="apple")

        assert len(filtered) == 3

    @pytest.mark.ynab
    def test_filter_by_payee_with_null_payee_name(self):
        """Test filtering by payee when some transactions have null payee_name."""
        transactions = [
            {"date": "2025-01-01", "payee_name": "Apple", "amount": -1000},
            {"date": "2025-01-02", "payee_name": None, "amount": -2000},  # Split transaction
            {"date": "2025-01-03", "payee_name": "Amazon", "amount": -3000},
            {"date": "2025-01-04", "payee_name": "Apple Store", "amount": -4000},
        ]

        # Should not crash on null payee_name
        filtered = filter_transactions(transactions, payee="Apple")

        assert len(filtered) == 2
        assert filtered[0]["payee_name"] == "Apple"
        assert filtered[1]["payee_name"] == "Apple Store"

    @pytest.mark.ynab
    def test_filter_by_payee_with_empty_string_payee_name(self):
        """Test filtering by payee when some transactions have empty string payee_name."""
        transactions = [
            {"date": "2025-01-01", "payee_name": "Apple", "amount": -1000},
            {"date": "2025-01-02", "payee_name": "", "amount": -2000},
            {"date": "2025-01-03", "payee_name": "Amazon", "amount": -3000},
        ]

        filtered = filter_transactions(transactions, payee="Apple")

        assert len(filtered) == 1
        assert filtered[0]["payee_name"] == "Apple"

    @pytest.mark.ynab
    def test_filter_by_payee_multiple_transactions(self):
        """Test filtering by payee with multiple matching transactions."""
        transactions = [
            {"date": "2024-12-31", "payee_name": "Apple", "amount": -1000},
            {"date": "2025-01-01", "payee_name": "Apple", "amount": -2000},
            {"date": "2025-01-15", "payee_name": "Amazon", "amount": -3000},
            {"date": "2025-01-31", "payee_name": "Apple", "amount": -4000},
            {"date": "2025-02-01", "payee_name": "Apple", "amount": -5000},
        ]

        filtered = filter_transactions(transactions, payee="Apple")

        assert len(filtered) == 4
        assert all(tx["payee_name"] == "Apple" for tx in filtered)

    @pytest.mark.ynab
    def test_filter_with_no_criteria(self):
        """Test that no filtering returns all transactions."""
        transactions = [
            {"date": "2025-01-01", "payee_name": "Apple", "amount": -1000},
            {"date": "2025-01-02", "payee_name": "Amazon", "amount": -2000},
        ]

        filtered = filter_transactions(transactions)

        assert len(filtered) == 2
        assert filtered == transactions
