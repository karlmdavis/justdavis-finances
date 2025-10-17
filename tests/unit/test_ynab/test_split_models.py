#!/usr/bin/env python3
"""
Unit tests for YNAB split generation domain models.

Tests the YnabSplit, TransactionSplitEdit, and SplitEditBatch models to ensure
proper type safety and JSON serialization for split generation output.
"""

import pytest

from finances.core.dates import FinancialDate
from finances.core.money import Money
from finances.ynab.models import (
    SplitEditBatch,
    TransactionSplitEdit,
    YnabSplit,
    YnabTransaction,
)


class TestYnabSplit:
    """Test YnabSplit domain model."""

    @pytest.mark.ynab
    def test_ynab_split_creation(self):
        """Test creating a YnabSplit with required fields."""
        split = YnabSplit(
            amount=Money.from_dollars("-$12.99"),
            memo="Test Item 1",
        )

        assert split.amount.to_cents() == -1299
        assert split.memo == "Test Item 1"
        assert split.category_id is None
        assert split.payee_id is None

    @pytest.mark.ynab
    def test_ynab_split_with_category(self):
        """Test YnabSplit with category_id."""
        split = YnabSplit(
            amount=Money.from_dollars("-$12.99"),
            memo="Test Item 1",
            category_id="cat_123",
        )

        assert split.category_id == "cat_123"

    @pytest.mark.ynab
    def test_ynab_split_to_ynab_dict(self):
        """Test conversion to YNAB API format (milliunits dict)."""
        split = YnabSplit(
            amount=Money.from_dollars("-$12.99"),
            memo="Item 1",
            category_id="cat_123",
        )

        ynab_dict = split.to_ynab_dict()

        assert ynab_dict["amount"] == -12990  # milliunits
        assert ynab_dict["memo"] == "Item 1"
        assert ynab_dict["category_id"] == "cat_123"
        assert "payee_id" not in ynab_dict  # Not included if None

    @pytest.mark.ynab
    def test_ynab_split_to_ynab_dict_with_payee(self):
        """Test YNAB dict includes payee_id when present."""
        split = YnabSplit(
            amount=Money.from_dollars("-$12.99"),
            memo="Item 1",
            payee_id="payee_456",
        )

        ynab_dict = split.to_ynab_dict()

        assert ynab_dict["payee_id"] == "payee_456"


class TestTransactionSplitEdit:
    """Test TransactionSplitEdit domain model."""

    @pytest.mark.ynab
    def test_transaction_split_edit_creation(self):
        """Test creating a TransactionSplitEdit."""
        transaction = YnabTransaction(
            id="tx1",
            date=FinancialDate.today(),
            amount=Money.from_dollars("-$15.99"),
            memo=None,
            cleared="uncleared",
            approved=True,
            account_id="acct1",
            account_name="Test Account",
            payee_id=None,
            payee_name=None,
            category_id=None,
            category_name=None,
            transfer_account_id=None,
            transfer_transaction_id=None,
            matched_transaction_id=None,
            import_id=None,
            import_payee_name=None,
            import_payee_name_original=None,
            debt_transaction_type=None,
        )
        splits = [
            YnabSplit(amount=Money.from_dollars("-$10.00"), memo="Item 1"),
            YnabSplit(amount=Money.from_dollars("-$5.99"), memo="Item 2"),
        ]

        edit = TransactionSplitEdit(
            transaction_id="tx1",
            transaction=transaction,
            splits=splits,
            source="amazon",
        )

        assert edit.transaction_id == "tx1"
        assert len(edit.splits) == 2
        assert edit.source == "amazon"
        assert edit.confidence is None

    @pytest.mark.ynab
    def test_transaction_split_edit_to_dict(self):
        """Test conversion to JSON-serializable dict."""
        transaction = YnabTransaction.from_dict(
            {
                "id": "tx1",
                "date": "2024-10-15",
                "amount": -15990,  # milliunits
                "memo": None,
            }
        )
        splits = [
            YnabSplit(amount=Money.from_dollars("-$10.00"), memo="Item 1"),
            YnabSplit(amount=Money.from_dollars("-$5.99"), memo="Item 2"),
        ]

        edit = TransactionSplitEdit(
            transaction_id="tx1",
            transaction=transaction,
            splits=splits,
            source="amazon",
            confidence=0.95,
        )

        edit_dict = edit.to_dict()

        assert edit_dict["transaction_id"] == "tx1"
        assert len(edit_dict["splits"]) == 2
        assert edit_dict["splits"][0]["amount"] == -10000  # milliunits
        assert edit_dict["splits"][0]["memo"] == "Item 1"
        assert edit_dict["source"] == "amazon"
        assert edit_dict["confidence"] == 0.95

    @pytest.mark.ynab
    def test_transaction_split_edit_dict_excludes_none_confidence(self):
        """Test that confidence is not included in dict when None."""
        transaction = YnabTransaction.from_dict(
            {
                "id": "tx1",
                "date": "2024-10-15",
                "amount": -15990,  # milliunits
            }
        )
        splits = [YnabSplit(amount=Money.from_dollars("-$15.99"), memo="Item")]

        edit = TransactionSplitEdit(
            transaction_id="tx1",
            transaction=transaction,
            splits=splits,
            source="amazon",
            # confidence is None (default)
        )

        edit_dict = edit.to_dict()

        assert "confidence" not in edit_dict


class TestSplitEditBatch:
    """Test SplitEditBatch domain model."""

    @pytest.mark.ynab
    def test_split_edit_batch_creation(self):
        """Test creating a SplitEditBatch."""
        tx1 = YnabTransaction.from_dict(
            {
                "id": "tx1",
                "date": "2024-10-15",
                "amount": -10000,  # milliunits
            }
        )
        tx2 = YnabTransaction.from_dict(
            {
                "id": "tx2",
                "date": "2024-10-15",
                "amount": -20000,  # milliunits
            }
        )

        edits = [
            TransactionSplitEdit(
                transaction_id="tx1",
                transaction=tx1,
                splits=[YnabSplit(amount=Money.from_dollars("-$10.00"), memo="Item")],
                source="amazon",
            ),
            TransactionSplitEdit(
                transaction_id="tx2",
                transaction=tx2,
                splits=[YnabSplit(amount=Money.from_dollars("-$20.00"), memo="App")],
                source="apple",
            ),
        ]

        batch = SplitEditBatch(
            edits=edits,
            timestamp="2025-10-16_14-30-00",
            amazon_count=1,
            apple_count=1,
        )

        assert len(batch.edits) == 2
        assert batch.timestamp == "2025-10-16_14-30-00"
        assert batch.amazon_count == 1
        assert batch.apple_count == 1

    @pytest.mark.ynab
    def test_split_edit_batch_to_dict(self):
        """Test batch conversion to JSON format for file output."""
        tx1 = YnabTransaction.from_dict(
            {
                "id": "tx1",
                "date": "2024-10-15",
                "amount": -10000,  # milliunits
            }
        )
        tx2 = YnabTransaction.from_dict(
            {
                "id": "tx2",
                "date": "2024-10-15",
                "amount": -20000,  # milliunits
            }
        )

        edits = [
            TransactionSplitEdit(
                transaction_id="tx1",
                transaction=tx1,
                splits=[YnabSplit(amount=Money.from_dollars("-$10.00"), memo="Item")],
                source="amazon",
            ),
            TransactionSplitEdit(
                transaction_id="tx2",
                transaction=tx2,
                splits=[YnabSplit(amount=Money.from_dollars("-$20.00"), memo="App")],
                source="apple",
            ),
        ]

        batch = SplitEditBatch(
            edits=edits,
            timestamp="2025-10-16_14-30-00",
            amazon_count=1,
            apple_count=1,
        )

        batch_dict = batch.to_dict()

        assert "metadata" in batch_dict
        assert batch_dict["metadata"]["timestamp"] == "2025-10-16_14-30-00"
        assert batch_dict["metadata"]["amazon_matches_processed"] == 1
        assert batch_dict["metadata"]["apple_matches_processed"] == 1
        assert batch_dict["metadata"]["total_edits"] == 2

        assert "edits" in batch_dict
        assert len(batch_dict["edits"]) == 2
        assert batch_dict["edits"][0]["transaction_id"] == "tx1"
        assert batch_dict["edits"][1]["transaction_id"] == "tx2"
