#!/usr/bin/env python3
"""
Tests for Apple matcher with domain model signatures.

Tests the new domain model-based interface for AppleMatcher:
- Accepts YnabTransaction instead of dict
- Returns MatchResult (already domain model)
"""

import pandas as pd
import pytest

from finances.apple.matcher import AppleMatcher
from finances.core.models import MatchResult
from finances.ynab.models import YnabTransaction


class TestAppleMatcherDomainModels:
    """Test AppleMatcher with domain model signatures."""

    @pytest.fixture
    def matcher(self):
        """Create an AppleMatcher instance for testing."""
        return AppleMatcher(date_window_days=2)

    @pytest.mark.apple
    def test_match_single_transaction_with_domain_model(self, matcher):
        """Test matcher accepts YnabTransaction and returns MatchResult."""
        # Create YnabTransaction
        transaction = YnabTransaction.from_dict({
            "id": "tx-123",
            "date": "2024-10-15",
            "amount": -45990,  # $45.99 expense (milliunits: 1 dollar = 1000 milliunits)
            "payee_name": "Apple.com/bill",
        })

        # Create Apple receipts DataFrame
        receipts_data = [{
            "order_id": "ABC123456",
            "receipt_date": pd.Timestamp("2024-10-15"),
            "total": 4599,  # $45.99 in cents
            "subtotal": 4299,
            "tax": 300,
            "items": [{"name": "App Purchase", "cost": 4299}],
        }]
        receipts_df = pd.DataFrame(receipts_data)

        # Call matcher with new signature
        result = matcher.match_single_transaction(transaction, receipts_df)

        # Should return MatchResult
        assert isinstance(result, MatchResult)
        assert result.transaction.id == transaction.id
        assert len(result.receipts) > 0
        assert result.confidence > 0.8

    @pytest.mark.apple
    def test_match_single_transaction_domain_model_no_match(self, matcher):
        """Test domain model signature with no matching receipt."""
        # Create YnabTransaction
        transaction = YnabTransaction.from_dict({
            "id": "tx-456",
            "date": "2024-10-15",
            "amount": -45990,  # $45.99 expense (milliunits)
            "payee_name": "Apple.com/bill",
        })

        # Empty receipts DataFrame
        receipts_df = pd.DataFrame()

        # Call matcher with new signature
        result = matcher.match_single_transaction(transaction, receipts_df)

        # Should return MatchResult with no matches
        assert isinstance(result, MatchResult)
        assert result.transaction.id == transaction.id
        assert len(result.receipts) == 0
        assert result.confidence == 0.0

    @pytest.mark.apple
    def test_legacy_dict_signature_still_works(self, matcher):
        """Test that legacy dict signature still works (backward compatibility)."""
        # Create dict transaction (legacy)
        transaction = {
            "id": "tx-legacy",
            "date": "2024-10-15",
            "amount": -45990,  # $45.99 expense (milliunits)
            "payee_name": "Apple.com/bill",
        }

        # Create Apple receipts DataFrame
        receipts_data = [{
            "order_id": "ABC123456",
            "receipt_date": pd.Timestamp("2024-10-15"),
            "total": 4599,
            "subtotal": 4299,
            "tax": 300,
            "items": [{"name": "App Purchase", "cost": 4299}],
        }]
        receipts_df = pd.DataFrame(receipts_data)

        # Call matcher with legacy signature
        result = matcher.match_single_transaction(transaction, receipts_df)

        # Should return MatchResult
        assert isinstance(result, MatchResult)
        assert result.transaction.id == "tx-legacy"
        assert len(result.receipts) > 0
