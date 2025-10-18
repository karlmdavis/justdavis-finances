#!/usr/bin/env python3
"""
Tests for Apple matcher with domain model signatures.

Tests the new domain model-based interface for AppleMatcher:
- Accepts YnabTransaction instead of dict
- Accepts list[ParsedReceipt] instead of DataFrame
- Returns MatchResult (already domain model)
"""

import pytest

from finances.apple.matcher import AppleMatcher
from finances.apple.parser import ParsedItem, ParsedReceipt
from finances.core.dates import FinancialDate
from finances.core.models import MatchResult
from finances.core.money import Money
from finances.ynab.models import YnabTransaction


class TestAppleMatcherDomainModels:
    """Test AppleMatcher with domain model signatures."""

    @pytest.fixture
    def matcher(self):
        """Create an AppleMatcher instance for testing."""
        return AppleMatcher(date_window_days=2)

    @pytest.mark.apple
    def test_match_single_transaction_with_domain_model(self, matcher):
        """Test matcher accepts YnabTransaction and list[ParsedReceipt], returns MatchResult."""
        # Create YnabTransaction
        transaction = YnabTransaction.from_dict(
            {
                "id": "tx-123",
                "date": "2024-10-15",
                "amount": -45990,  # $45.99 expense (milliunits: 1 dollar = 1000 milliunits)
                "payee_name": "Apple.com/bill",
            }
        )

        # Create ParsedReceipt list
        receipts_list = [
            ParsedReceipt(
                format_detected="modern",
                apple_id="test@example.com",
                receipt_date=FinancialDate.from_string("2024-10-15"),
                order_id="ABC123456",
                document_number="DOC123",
                subtotal=Money.from_cents(4299),
                tax=Money.from_cents(300),
                total=Money.from_cents(4599),  # $45.99 in cents
                currency="USD",
                payment_method=None,
                billed_to=None,
                items=[
                    ParsedItem(
                        title="App Purchase",
                        cost=Money.from_cents(4299),
                        quantity=1,
                        subscription=False,
                    )
                ],
                parsing_metadata={},
                base_name="test_receipt",
            )
        ]

        # Call matcher with new signature (list[ParsedReceipt])
        result = matcher.match_single_transaction(transaction, receipts_list)

        # Should return MatchResult
        assert isinstance(result, MatchResult)
        assert result.transaction.id == transaction.id
        assert len(result.receipts) > 0
        assert result.confidence > 0.8

    @pytest.mark.apple
    def test_match_single_transaction_domain_model_no_match(self, matcher):
        """Test domain model signature with no matching receipt."""
        # Create YnabTransaction
        transaction = YnabTransaction.from_dict(
            {
                "id": "tx-456",
                "date": "2024-10-15",
                "amount": -45990,  # $45.99 expense (milliunits)
                "payee_name": "Apple.com/bill",
            }
        )

        # Empty receipts list
        receipts_list = []

        # Call matcher with new signature (empty list)
        result = matcher.match_single_transaction(transaction, receipts_list)

        # Should return MatchResult with no matches
        assert isinstance(result, MatchResult)
        assert result.transaction.id == transaction.id
        assert len(result.receipts) == 0
        assert result.confidence == 0.0
