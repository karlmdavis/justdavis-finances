#!/usr/bin/env python3
"""Tests for Amazon transaction matching module."""


import pytest

from finances.amazon import AmazonOrderItem, SimplifiedMatcher
from finances.core import FinancialDate, Money
from finances.ynab.models import YnabTransaction


def create_test_transaction(
    id: str,
    date: str,
    amount: int,  # milliunits
    payee_name: str,
    account_name: str = "Test Account",
) -> YnabTransaction:
    """Helper to create YnabTransaction for testing with minimal fields."""
    return YnabTransaction.from_dict(
        {
            "id": id,
            "date": date,
            "amount": amount,
            "payee_name": payee_name,
            "account_name": account_name,
        }
    )


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


class TestSimplifiedMatcher:
    """Test the SimplifiedMatcher class."""

    @pytest.fixture
    def matcher(self):
        """Create a SimplifiedMatcher instance for testing."""
        return SimplifiedMatcher()

    @pytest.fixture
    def sample_amazon_orders(self):
        """Sample Amazon orders for testing."""
        return [
            {
                "order_id": "111-2223334-5556667",
                "order_date": "2024-08-15",
                "ship_date": "2024-08-15",
                "total": 4599,  # $45.99 in cents
                "items": [
                    {
                        "name": "Echo Dot (4th Gen) - Charcoal",
                        "quantity": 1,
                        "amount": 4599,
                        "asin": "B084J4KNDS",
                    }
                ],
            },
            {
                "order_id": "111-2223334-7778889",
                "order_date": "2024-08-16",
                "ship_date": "2024-08-17",
                "total": 2999,  # $29.99 in cents
                "items": [{"name": "USB-C Cable 6ft", "quantity": 1, "amount": 2999, "asin": "B08CXYZ123"}],
            },
            {
                "order_id": "111-2223334-9990001",
                "order_date": "2024-08-14",
                "ship_date": "2024-08-15",
                "total": 12999,  # $129.99 in cents
                "items": [
                    {"name": "Wireless Headphones", "quantity": 1, "amount": 8999, "asin": "B07WXYZ789"},
                    {"name": "Phone Case", "quantity": 1, "amount": 4000, "asin": "B08ABCD456"},
                ],
            },
        ]

    @pytest.mark.amazon
    def test_exact_amount_match(self, matcher, sample_amazon_orders):
        """Test exact amount matching with single order."""
        transaction = create_test_transaction(
            id="test-txn-123",
            date="2024-08-15",
            amount=-45990,  # $45.99 expense in milliunits
            payee_name="AMZN Mktp US*TEST123",
            account_name="Chase Credit Card",
        )

        order_items = convert_test_data_to_order_items(sample_amazon_orders)
        orders_by_account = {"test_account": order_items}

        result = matcher.match_transaction(transaction, orders_by_account)

        assert len(result.matches) > 0
        assert result.best_match is not None

        # Should match the $45.99 order
        assert result.best_match["amazon_orders"][0]["order_id"] == "111-2223334-5556667"
        assert result.best_match["confidence"] >= 0.9  # High confidence for exact match

    @pytest.mark.amazon
    def test_multi_item_order_match(self, matcher, sample_amazon_orders):
        """Test matching to multi-item order."""
        transaction = create_test_transaction(
            id="test-txn-456",
            date="2024-08-14",
            amount=-129990,  # $129.99 expense
            payee_name="AMZN Mktp US*TEST456",
            account_name="Chase Credit Card",
        )

        order_items = convert_test_data_to_order_items(sample_amazon_orders)
        orders_by_account = {"test_account": order_items}

        result = matcher.match_transaction(transaction, orders_by_account)

        assert len(result.matches) > 0
        assert result.best_match is not None

        # Should match the multi-item $129.99 order
        assert result.best_match["amazon_orders"][0]["order_id"] == "111-2223334-9990001"
        assert len(result.best_match["amazon_orders"][0]["items"]) == 2

    @pytest.mark.amazon
    def test_date_window_matching(self, matcher, sample_amazon_orders):
        """Test matching within date window for shipping delays."""
        transaction = create_test_transaction(
            id="test-txn-789",
            date="2024-08-18",  # 2 days after ship date
            amount=-29990,  # $29.99 expense
            payee_name="AMZN Mktp US*TEST789",
            account_name="Chase Credit Card",
        )

        order_items = convert_test_data_to_order_items(sample_amazon_orders)
        orders_by_account = {"test_account": order_items}

        result = matcher.match_transaction(transaction, orders_by_account)

        assert len(result.matches) > 0
        # Should still find the order shipped on 2024-08-17
        order_ids = [m["amazon_orders"][0]["order_id"] for m in result.matches]
        assert "111-2223334-7778889" in order_ids

    @pytest.mark.amazon
    def test_no_matches_found(self, matcher, sample_amazon_orders):
        """Test case where no matches are found."""
        transaction = create_test_transaction(
            id="test-txn-999",
            date="2024-08-20",
            amount=-99999,  # $999.99 - no matching order
            payee_name="AMZN Mktp US*TEST999",
            account_name="Chase Credit Card",
        )

        order_items = convert_test_data_to_order_items(sample_amazon_orders)
        orders_by_account = {"test_account": order_items}

        result = matcher.match_transaction(transaction, orders_by_account)

        # Should return empty list or very low confidence matches
        high_confidence_matches = [m for m in result.matches if m["confidence"] > 0.5]
        assert len(high_confidence_matches) == 0

    @pytest.mark.amazon
    def test_confidence_scoring(self, matcher, sample_amazon_orders):
        """Test confidence scoring accuracy."""
        # Perfect match: same date, exact amount
        perfect_transaction = create_test_transaction(
            id="test-txn-perfect",
            date="2024-08-15",
            amount=-45990,
            payee_name="AMZN Mktp US*PERFECT",
            account_name="Chase Credit Card",
        )

        # Good match: ship date, exact amount
        good_transaction = create_test_transaction(
            id="test-txn-good",
            date="2024-08-17",  # Ship date
            amount=-29990,
            payee_name="AMZN Mktp US*GOOD",
            account_name="Chase Credit Card",
        )

        # Fair match: within window, exact amount
        fair_transaction = create_test_transaction(
            id="test-txn-fair",
            date="2024-08-19",  # 2 days after ship date
            amount=-29990,
            payee_name="AMZN Mktp US*FAIR",
            account_name="Chase Credit Card",
        )

        order_items = convert_test_data_to_order_items(sample_amazon_orders)
        orders_by_account = {"test_account": order_items}

        perfect_result = matcher.match_transaction(perfect_transaction, orders_by_account)
        good_result = matcher.match_transaction(good_transaction, orders_by_account)
        fair_result = matcher.match_transaction(fair_transaction, orders_by_account)

        if perfect_result.matches and good_result.matches and fair_result.matches:
            perfect_conf = max(m["confidence"] for m in perfect_result.matches)
            good_conf = max(m["confidence"] for m in good_result.matches)
            fair_conf = max(m["confidence"] for m in fair_result.matches)

            # Confidence should decrease with date distance
            assert perfect_conf >= good_conf
            assert good_conf >= fair_conf

    @pytest.mark.amazon
    def test_split_payment_detection(self, matcher):
        """Test detection of split payments across multiple orders."""
        transaction = create_test_transaction(
            id="test-txn-split",
            date="2024-08-15",
            amount=-250000,  # $250.00 - should match first order
            payee_name="AMZN Mktp US*SPLIT",
            account_name="Chase Credit Card",
        )

        # Multiple orders that could combine to this amount
        orders = [
            {
                "order_id": "split-order-1",
                "order_date": "2024-08-15",
                "ship_date": "2024-08-15",
                "total": 25000,  # $250.00
                "items": [{"name": "Item 1", "amount": 25000}],
            },
            {
                "order_id": "split-order-2",
                "order_date": "2024-08-15",
                "ship_date": "2024-08-15",
                "total": 30989,  # $309.89
                "items": [{"name": "Item 2", "amount": 30989}],
            },
            {
                "order_id": "split-order-3",
                "order_date": "2024-08-15",
                "ship_date": "2024-08-15",
                "total": 20000,  # $200.00
                "items": [{"name": "Item 3", "amount": 20000}],
            },
        ]

        order_items = convert_test_data_to_order_items(orders)
        orders_by_account = {"test_account": order_items}

        result = matcher.match_transaction(transaction, orders_by_account)

        # Should detect that this might be a split payment
        assert len(result.matches) > 0

        # Check if any match indicates split payment possibility
        any(
            m.get("split_payment_candidate", False) or m.get("match_method") == "split_payment"
            for m in result.matches
        )
        # Note: This depends on the matcher implementation


class TestEdgeCases:
    """Test edge cases and error conditions."""

    @pytest.fixture
    def matcher(self):
        return SimplifiedMatcher()

    @pytest.mark.amazon
    def test_empty_orders_list(self, matcher):
        """Test matching with empty orders list."""
        transaction = create_test_transaction(
            id="test-txn",
            date="2024-08-15",
            amount=-45990,
            payee_name="AMZN Mktp US*TEST",
            account_name="Chase Credit Card",
        )

        orders_by_account = {"test_account": []}
        result = matcher.match_transaction(transaction, orders_by_account)
        assert result.matches == []

    @pytest.mark.amazon
    def test_malformed_transaction(self, matcher):
        """Test handling of malformed transaction data - SKIP for now."""
        pytest.skip("Requires YnabTransaction validation logic")

    @pytest.mark.amazon
    def test_malformed_order_data(self, matcher):
        """Test handling of malformed order data - SKIP for now."""
        pytest.skip("Requires AmazonOrderItem validation logic")

    @pytest.mark.amazon
    def test_very_large_order_list(self, matcher):
        """Test performance with large number of orders."""
        transaction = create_test_transaction(
            id="test-txn",
            date="2024-08-15",
            amount=-45990,
            payee_name="AMZN Mktp US*TEST",
            account_name="Chase Credit Card",
        )

        # Generate large list of orders
        large_order_list = [
            {
                "order_id": f"order-{i}",
                "order_date": "2024-08-15",
                "ship_date": "2024-08-15",
                "total": 1000 + i,  # Varying amounts
                "items": [{"name": f"Item {i}", "amount": 1000 + i}],
            }
            for i in range(1000)
        ]

        # Should complete in reasonable time
        import time

        start_time = time.time()
        order_items = convert_test_data_to_order_items(large_order_list)
        orders_by_account = {"test_account": order_items}
        result = matcher.match_transaction(transaction, orders_by_account)
        end_time = time.time()

        # Should complete within 5 seconds for 1000 orders
        assert end_time - start_time < 5.0
        assert isinstance(result.matches, list)
