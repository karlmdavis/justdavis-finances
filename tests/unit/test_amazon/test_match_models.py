#!/usr/bin/env python3
"""
Unit tests for Amazon matching domain models.

Tests the AmazonMatch and AmazonMatchResult models for type safety and data integrity.
"""

import pytest

from finances.amazon.models import AmazonMatch, AmazonMatchResult, AmazonOrderItem
from finances.core.dates import FinancialDate
from finances.core.money import Money
from finances.ynab.models import YnabTransaction


class TestAmazonMatch:
    """Test AmazonMatch domain model."""

    @pytest.mark.amazon
    def test_amazon_match_creation(self):
        """Test creating an AmazonMatch with required fields."""
        order_item = AmazonOrderItem(
            order_id="123-456",
            asin="B0ABC123",
            product_name="Test Product",
            quantity=1,
            unit_price=Money.from_cents(2999),
            total_owed=Money.from_cents(2999),
            order_date=FinancialDate.from_string("2024-10-15"),
            ship_date=None,
        )

        match = AmazonMatch(
            amazon_orders=[order_item],
            match_method="complete_order",
            confidence=0.95,
            account="karl",
            total_match_amount=Money.from_cents(2999),
        )

        assert len(match.amazon_orders) == 1
        assert match.match_method == "complete_order"
        assert match.confidence == 0.95
        assert match.account == "karl"
        assert match.total_match_amount.to_cents() == 2999
        assert match.unmatched_amount.to_cents() == 0

    @pytest.mark.amazon
    def test_amazon_match_with_unmatched_amount(self):
        """Test AmazonMatch with unmatched amount (split payment)."""
        order_item = AmazonOrderItem(
            order_id="123-456",
            asin="B0ABC123",
            product_name="Test Product",
            quantity=1,
            unit_price=Money.from_cents(5999),
            total_owed=Money.from_cents(5999),
            order_date=FinancialDate.from_string("2024-10-15"),
            ship_date=None,
        )

        match = AmazonMatch(
            amazon_orders=[order_item],
            match_method="split_payment",
            confidence=0.85,
            account="karl",
            total_match_amount=Money.from_cents(2999),
            unmatched_amount=Money.from_cents(3000),
            matched_item_indices=[0],
        )

        assert match.unmatched_amount.to_cents() == 3000
        assert match.matched_item_indices == [0]


class TestAmazonMatchResult:
    """Test AmazonMatchResult domain model."""

    @pytest.mark.amazon
    def test_amazon_match_result_creation(self):
        """Test creating AmazonMatchResult with transaction and matches."""
        transaction = YnabTransaction.from_dict({
            "id": "tx1",
            "date": "2024-10-15",
            "amount": -29990,  # $29.99 expense
        })

        order_item = AmazonOrderItem(
            order_id="123-456",
            asin="B0ABC123",
            product_name="Test Product",
            quantity=1,
            unit_price=Money.from_cents(2999),
            total_owed=Money.from_cents(2999),
            order_date=FinancialDate.from_string("2024-10-15"),
            ship_date=None,
        )

        match = AmazonMatch(
            amazon_orders=[order_item],
            match_method="complete_order",
            confidence=0.95,
            account="karl",
            total_match_amount=Money.from_cents(2999),
        )

        result = AmazonMatchResult(
            transaction=transaction,
            matches=[match],
            best_match=match,
        )

        assert result.transaction.id == "tx1"
        assert len(result.matches) == 1
        assert result.best_match is not None
        assert result.best_match.confidence == 0.95
        assert result.message is None

    @pytest.mark.amazon
    def test_amazon_match_result_no_matches(self):
        """Test AmazonMatchResult with no matches."""
        transaction = YnabTransaction.from_dict({
            "id": "tx1",
            "date": "2024-10-15",
            "amount": -29990,
        })

        result = AmazonMatchResult(
            transaction=transaction,
            matches=[],
            best_match=None,
            message="Not an Amazon transaction",
        )

        assert result.transaction.id == "tx1"
        assert len(result.matches) == 0
        assert result.best_match is None
        assert result.message == "Not an Amazon transaction"

    @pytest.mark.amazon
    def test_amazon_match_result_multiple_matches(self):
        """Test AmazonMatchResult with multiple match candidates."""
        transaction = YnabTransaction.from_dict({
            "id": "tx1",
            "date": "2024-10-15",
            "amount": -29990,
        })

        order_item1 = AmazonOrderItem(
            order_id="123-456",
            asin="B0ABC123",
            product_name="Test Product 1",
            quantity=1,
            unit_price=Money.from_cents(2999),
            total_owed=Money.from_cents(2999),
            order_date=FinancialDate.from_string("2024-10-15"),
            ship_date=None,
        )

        order_item2 = AmazonOrderItem(
            order_id="789-012",
            asin="B0DEF456",
            product_name="Test Product 2",
            quantity=1,
            unit_price=Money.from_cents(2999),
            total_owed=Money.from_cents(2999),
            order_date=FinancialDate.from_string("2024-10-14"),
            ship_date=None,
        )

        match1 = AmazonMatch(
            amazon_orders=[order_item1],
            match_method="complete_order",
            confidence=0.95,
            account="karl",
            total_match_amount=Money.from_cents(2999),
        )

        match2 = AmazonMatch(
            amazon_orders=[order_item2],
            match_method="complete_order",
            confidence=0.85,
            account="karl",
            total_match_amount=Money.from_cents(2999),
        )

        result = AmazonMatchResult(
            transaction=transaction,
            matches=[match1, match2],
            best_match=match1,  # Higher confidence
        )

        assert len(result.matches) == 2
        assert result.best_match == match1
        assert result.best_match.confidence > result.matches[1].confidence

    @pytest.mark.amazon
    def test_amazon_match_result_has_matches_property(self):
        """Test AmazonMatchResult has_matches property."""
        transaction = YnabTransaction.from_dict({
            "id": "tx1",
            "date": "2024-10-15",
            "amount": -29990,
        })

        order_item = AmazonOrderItem(
            order_id="123-456",
            asin="B0ABC123",
            product_name="Test Product",
            quantity=1,
            unit_price=Money.from_cents(2999),
            total_owed=Money.from_cents(2999),
            order_date=FinancialDate.from_string("2024-10-15"),
            ship_date=None,
        )

        # Result with matches
        result_with_matches = AmazonMatchResult(
            transaction=transaction,
            matches=[AmazonMatch(
                amazon_orders=[order_item],
                match_method="test",
                confidence=0.9,
                account="karl",
                total_match_amount=Money.from_cents(2999),
            )],
            best_match=None,
        )
        assert result_with_matches.has_matches is True
        assert result_with_matches.match_count == 1

        # Result without matches
        result_no_matches = AmazonMatchResult(
            transaction=transaction,
            matches=[],
            best_match=None,
        )
        assert result_no_matches.has_matches is False
        assert result_no_matches.match_count == 0
