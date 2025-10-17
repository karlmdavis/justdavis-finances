#!/usr/bin/env python3
"""
Tests for Amazon matcher with domain model signatures.

Tests the new domain model-based interface for SimplifiedMatcher:
- Accepts YnabTransaction instead of dict
- Returns AmazonMatchResult instead of dict
"""

import pytest

from finances.amazon import SimplifiedMatcher
from finances.amazon.models import AmazonMatchResult, AmazonOrderItem
from finances.core.dates import FinancialDate
from finances.core.money import Money
from finances.ynab.models import YnabTransaction


def convert_test_data_to_order_items(orders):
    """Convert simplified test data to list[AmazonOrderItem] domain models."""
    items = []
    for order in orders:
        for item in order["items"]:
            order_item = AmazonOrderItem(
                order_id=order["order_id"],
                asin=item.get("asin", "B00000000"),
                product_name=item["name"],
                quantity=item.get("quantity", 1),
                unit_price=Money.from_cents(item.get("unit_price", item["amount"])),
                total_owed=Money.from_cents(item["amount"]),
                order_date=FinancialDate.from_string(order["order_date"]),
                ship_date=FinancialDate.from_string(order["ship_date"]) if order.get("ship_date") else None,
            )
            items.append(order_item)
    return items


class TestSimplifiedMatcherDomainModels:
    """Test SimplifiedMatcher with domain model signatures."""

    @pytest.fixture
    def matcher(self):
        """Create a SimplifiedMatcher instance for testing."""
        return SimplifiedMatcher()

    @pytest.mark.amazon
    def test_match_transaction_with_domain_models(self, matcher):
        """Test matcher accepts YnabTransaction and returns AmazonMatchResult."""
        # Create YnabTransaction
        transaction = YnabTransaction.from_dict({
            "id": "tx-123",
            "date": "2024-10-15",
            "amount": -45990,  # $45.99 expense
            "payee_name": "AMZN Mktp US*TEST123",
        })

        # Create Amazon order data
        orders = [{
            "order_id": "111-2223334-5556667",
            "order_date": "2024-10-15",
            "ship_date": "2024-10-15",
            "items": [{
                "name": "Echo Dot (4th Gen) - Charcoal",
                "quantity": 1,
                "amount": 4599,
                "asin": "B084J4KNDS",
            }],
        }]

        order_items = convert_test_data_to_order_items(orders)
        account_data = {"karl": order_items}

        # Call matcher with new signature
        result = matcher.match_transaction(transaction, account_data)

        # Should return AmazonMatchResult
        assert isinstance(result, AmazonMatchResult)
        assert result.transaction == transaction
        assert result.has_matches
        assert result.best_match is not None
        # Note: best_match is still dict internally (converted in Layer 4)
        assert result.best_match["confidence"] > 0.8  # type: ignore[index]

    @pytest.mark.amazon
    def test_match_transaction_domain_models_no_match(self, matcher):
        """Test domain model signature with no Amazon transaction."""
        # Create non-Amazon transaction
        transaction = YnabTransaction.from_dict({
            "id": "tx-456",
            "date": "2024-10-15",
            "amount": -45990,
            "payee_name": "Starbucks",
        })

        # Empty account data
        account_data = {"karl": []}

        # Call matcher with new signature
        result = matcher.match_transaction(transaction, account_data)

        # Should return AmazonMatchResult with no matches
        assert isinstance(result, AmazonMatchResult)
        assert result.transaction == transaction
        assert not result.has_matches
        assert result.best_match is None
        assert result.message == "Not an Amazon transaction"
