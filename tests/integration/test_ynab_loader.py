#!/usr/bin/env python3
"""
Integration tests for YNAB data loaders.

Tests YNAB data loading using existing test data fixtures.
"""

from pathlib import Path

import pytest

from finances.ynab.loader import load_accounts, load_categories, load_transactions

# Use existing test data fixtures
TEST_DATA_DIR = Path(__file__).parent.parent / "test_data" / "ynab"


@pytest.mark.integration
@pytest.mark.ynab
class TestYnabLoaders:
    """Test YNAB data loading with real test data fixtures."""

    def test_load_transactions_from_test_data(self):
        """Test loading transactions from test data."""
        transactions = load_transactions(TEST_DATA_DIR)

        assert len(transactions) > 0
        # Verify first transaction has expected structure
        tx = transactions[0]
        assert hasattr(tx, "id")
        assert hasattr(tx, "date")
        assert hasattr(tx, "amount")
        assert hasattr(tx, "account_id")

    def test_load_accounts_from_test_data(self):
        """Test loading accounts from test data."""
        accounts = load_accounts(TEST_DATA_DIR)

        assert len(accounts) > 0
        # Verify first account has expected structure
        account = accounts[0]
        assert hasattr(account, "id")
        assert hasattr(account, "name")
        assert hasattr(account, "type")
        assert hasattr(account, "balance")

    @pytest.mark.skip(reason="Test data fixture missing category_group_id field")
    def test_load_categories_from_test_data(self):
        """Test loading categories from test data."""
        categories = load_categories(TEST_DATA_DIR)

        assert len(categories) > 0
        # Verify first category has expected structure
        category = categories[0]
        assert hasattr(category, "id")
        assert hasattr(category, "name")
        assert hasattr(category, "category_group_id")

    def test_load_transactions_preserves_money_types(self):
        """Test that transactions have Money types for amounts."""
        from finances.core import Money

        transactions = load_transactions(TEST_DATA_DIR)

        assert len(transactions) > 0
        tx = transactions[0]
        assert isinstance(tx.amount, Money)

    def test_load_accounts_preserves_money_types(self):
        """Test that accounts have Money types for balances."""
        from finances.core import Money

        accounts = load_accounts(TEST_DATA_DIR)

        assert len(accounts) > 0
        account = accounts[0]
        assert isinstance(account.balance, Money)
        assert isinstance(account.cleared_balance, Money)

    def test_load_transactions_missing_cache_raises_error(self, tmp_path):
        """Test that loading from missing cache raises FileNotFoundError."""
        nonexistent_path = tmp_path / "nonexistent"

        with pytest.raises(FileNotFoundError):
            load_transactions(nonexistent_path)
