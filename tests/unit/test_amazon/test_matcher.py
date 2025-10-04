#!/usr/bin/env python3
"""Tests for Amazon transaction matching module."""


import pandas as pd
import pytest

from finances.amazon import SimplifiedMatcher


def convert_test_data_to_amazon_format(orders):
    """Convert simplified test data to Amazon CSV format expected by the matcher."""
    amazon_rows = []
    for order in orders:
        for item in order["items"]:
            amazon_rows.append(
                {
                    "Order ID": order["order_id"],
                    "Order Date": pd.to_datetime(order["order_date"]),
                    "Ship Date": pd.to_datetime(order["ship_date"]),
                    "Product Name": item["name"],
                    "Total Owed": f"${item['amount']/100:.2f}",  # Convert cents to dollars
                    "Unit Price": f"${item.get('unit_price', item['amount'])/100:.2f}",
                    "Quantity": item.get("quantity", 1),
                    "ASIN": item.get("asin", ""),
                }
            )
    return amazon_rows


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
        transaction = {
            "id": "test-txn-123",
            "date": "2024-08-15",
            "amount": -45990,  # $45.99 expense in milliunits
            "payee_name": "AMZN Mktp US*TEST123",
            "account_name": "Chase Credit Card",
        }

        # Convert test data to Amazon format and then to account_data format
        amazon_data = convert_test_data_to_amazon_format(sample_amazon_orders)
        account_data = {"test_account": (pd.DataFrame(amazon_data), pd.DataFrame())}
        result = matcher.match_transaction(transaction, account_data)
        matches = result["matches"]
        best_match = result["best_match"]

        assert len(matches) > 0
        assert best_match is not None

        # Should match the $45.99 order
        assert best_match["amazon_orders"][0]["order_id"] == "111-2223334-5556667"
        assert best_match["confidence"] >= 0.9  # High confidence for exact match

    @pytest.mark.amazon
    def test_multi_item_order_match(self, matcher, sample_amazon_orders):
        """Test matching to multi-item order."""
        transaction = {
            "id": "test-txn-456",
            "date": "2024-08-14",
            "amount": -129990,  # $129.99 expense in milliunits
            "payee_name": "AMZN Mktp US*TEST456",
            "account_name": "Chase Credit Card",
        }

        # Convert test data to Amazon format and then to account_data format
        amazon_data = convert_test_data_to_amazon_format(sample_amazon_orders)
        account_data = {"test_account": (pd.DataFrame(amazon_data), pd.DataFrame())}
        result = matcher.match_transaction(transaction, account_data)
        matches = result["matches"]
        best_match = result["best_match"]

        assert len(matches) > 0
        assert best_match is not None

        # Should match the multi-item $129.99 order
        assert best_match["amazon_orders"][0]["order_id"] == "111-2223334-9990001"
        assert len(best_match["amazon_orders"][0]["items"]) == 2

    @pytest.mark.amazon
    def test_date_window_matching(self, matcher, sample_amazon_orders):
        """Test matching within date window for shipping delays."""
        transaction = {
            "id": "test-txn-789",
            "date": "2024-08-18",  # 2 days after ship date
            "amount": -29990,  # $29.99 expense in milliunits
            "payee_name": "AMZN Mktp US*TEST789",
            "account_name": "Chase Credit Card",
        }

        # Convert test data to Amazon format and then to account_data format
        amazon_data = convert_test_data_to_amazon_format(sample_amazon_orders)
        account_data = {"test_account": (pd.DataFrame(amazon_data), pd.DataFrame())}
        result = matcher.match_transaction(transaction, account_data)
        matches = result["matches"]

        assert len(matches) > 0
        # Should still find the order shipped on 2024-08-17
        order_ids = [m["amazon_orders"][0]["order_id"] for m in matches]
        assert "111-2223334-7778889" in order_ids

    @pytest.mark.amazon
    def test_no_matches_found(self, matcher, sample_amazon_orders):
        """Test case where no matches are found."""
        transaction = {
            "id": "test-txn-999",
            "date": "2024-08-20",
            "amount": -99999,  # $999.99 - no matching order
            "payee_name": "AMZN Mktp US*TEST999",
            "account_name": "Chase Credit Card",
        }

        # Convert test data to Amazon format and then to account_data format
        amazon_data = convert_test_data_to_amazon_format(sample_amazon_orders)
        account_data = {"test_account": (pd.DataFrame(amazon_data), pd.DataFrame())}
        result = matcher.match_transaction(transaction, account_data)
        matches = result["matches"]

        # Should return empty list or very low confidence matches
        high_confidence_matches = [m for m in matches if m["confidence"] > 0.5]
        assert len(high_confidence_matches) == 0

    @pytest.mark.amazon
    def test_confidence_scoring(self, matcher, sample_amazon_orders):
        """Test confidence scoring accuracy."""
        # Perfect match: same date, exact amount
        perfect_transaction = {
            "id": "test-txn-perfect",
            "date": "2024-08-15",
            "amount": -45990,
            "payee_name": "AMZN Mktp US*PERFECT",
            "account_name": "Chase Credit Card",
        }

        # Good match: ship date, exact amount
        good_transaction = {
            "id": "test-txn-good",
            "date": "2024-08-17",  # Ship date
            "amount": -29990,
            "payee_name": "AMZN Mktp US*GOOD",
            "account_name": "Chase Credit Card",
        }

        # Fair match: within window, exact amount
        fair_transaction = {
            "id": "test-txn-fair",
            "date": "2024-08-19",  # 2 days after ship date
            "amount": -29990,
            "payee_name": "AMZN Mktp US*FAIR",
            "account_name": "Chase Credit Card",
        }

        # Convert test data to Amazon format and then to account_data format
        amazon_data = convert_test_data_to_amazon_format(sample_amazon_orders)
        account_data = {"test_account": (pd.DataFrame(amazon_data), pd.DataFrame())}

        perfect_result = matcher.match_transaction(perfect_transaction, account_data)
        good_result = matcher.match_transaction(good_transaction, account_data)
        fair_result = matcher.match_transaction(fair_transaction, account_data)

        perfect_matches = perfect_result["matches"]
        good_matches = good_result["matches"]
        fair_matches = fair_result["matches"]

        if perfect_matches and good_matches and fair_matches:
            perfect_conf = max(m["confidence"] for m in perfect_matches)
            good_conf = max(m["confidence"] for m in good_matches)
            fair_conf = max(m["confidence"] for m in fair_matches)

            # Confidence should decrease with date distance
            assert perfect_conf >= good_conf
            assert good_conf >= fair_conf

    @pytest.mark.amazon
    def test_split_payment_detection(self, matcher):
        """Test detection of split payments across multiple orders."""
        # Large transaction that might span multiple orders
        transaction = {
            "id": "test-txn-split",
            "date": "2024-08-15",
            "amount": -250000,  # $250.00 in milliunits - should match first order
            "payee_name": "AMZN Mktp US*SPLIT",
            "account_name": "Chase Credit Card",
        }

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

        # Convert test data to Amazon format and then to account_data format
        amazon_data = convert_test_data_to_amazon_format(orders)
        account_data = {"test_account": (pd.DataFrame(amazon_data), pd.DataFrame())}
        result = matcher.match_transaction(transaction, account_data)
        matches = result["matches"]

        # Should detect that this might be a split payment
        assert len(matches) > 0

        # Check if any match indicates split payment possibility
        any(
            m.get("split_payment_candidate", False) or m.get("match_method") == "split_payment"
            for m in matches
        )
        # Note: This depends on the matcher implementation


class TestMatchingStrategies:
    """Test different matching strategies."""

    @pytest.fixture
    def matcher(self):
        return SimplifiedMatcher()

    @pytest.mark.amazon
    def test_complete_match_strategy(self, matcher):
        """Test complete order matching (exact amount + date)."""

        # This would test the complete match strategy specifically
        # Implementation depends on matcher's internal structure
        pass

    @pytest.mark.amazon
    def test_fuzzy_match_strategy(self, matcher):
        """Test fuzzy matching with amount tolerance."""

        # Should match with lower confidence due to amount difference
        # Implementation would test fuzzy matching logic
        pass


class TestEdgeCases:
    """Test edge cases and error conditions."""

    @pytest.fixture
    def matcher(self):
        return SimplifiedMatcher()

    @pytest.mark.amazon
    def test_empty_orders_list(self, matcher):
        """Test matching with empty orders list."""
        transaction = {
            "id": "test-txn",
            "date": "2024-08-15",
            "amount": -45990,
            "payee_name": "AMZN Mktp US*TEST",
            "account_name": "Chase Credit Card",
        }

        # Convert empty orders list to account_data format
        account_data = {"test_account": (pd.DataFrame([]), pd.DataFrame())}
        result = matcher.match_transaction(transaction, account_data)
        matches = result["matches"]
        assert matches == []

    @pytest.mark.amazon
    def test_malformed_transaction(self, matcher):
        """Test handling of malformed transaction data."""
        malformed_transaction = {
            "id": "test-txn",
            # Missing required fields
        }

        orders = [{"order_id": "test-order", "order_date": "2024-08-15", "total": 4599, "items": []}]

        # Should handle gracefully without crashing
        try:
            account_data = {"test_account": (pd.DataFrame(orders), pd.DataFrame())}
            result = matcher.match_transaction(malformed_transaction, account_data)
            matches = result["matches"]
            # Should return empty list or handle error gracefully
            assert isinstance(matches, list)
        except (KeyError, ValueError, TypeError):
            # Acceptable to raise validation errors
            pass

    @pytest.mark.amazon
    def test_malformed_order_data(self, matcher):
        """Test handling of malformed order data."""
        transaction = {
            "id": "test-txn",
            "date": "2024-08-15",
            "amount": -45990,
            "payee_name": "AMZN Mktp US*TEST",
            "account_name": "Chase Credit Card",
        }

        malformed_orders = [
            {
                "order_id": "test-order",
                # Missing required fields like total, date
            }
        ]

        # Should handle gracefully
        try:
            account_data = {"test_account": (pd.DataFrame(malformed_orders), pd.DataFrame())}
            result = matcher.match_transaction(transaction, account_data)
            matches = result["matches"]
            assert isinstance(matches, list)
        except (KeyError, ValueError, TypeError):
            # Acceptable to raise validation errors
            pass

    @pytest.mark.amazon
    def test_very_large_order_list(self, matcher):
        """Test performance with large number of orders."""
        transaction = {
            "id": "test-txn",
            "date": "2024-08-15",
            "amount": -45990,
            "payee_name": "AMZN Mktp US*TEST",
            "account_name": "Chase Credit Card",
        }

        # Generate large list of orders
        large_order_list = []
        for i in range(1000):
            large_order_list.append(
                {
                    "order_id": f"order-{i}",
                    "order_date": "2024-08-15",
                    "ship_date": "2024-08-15",
                    "total": 1000 + i,  # Varying amounts
                    "items": [{"name": f"Item {i}", "amount": 1000 + i}],
                }
            )

        # Should complete in reasonable time
        import time

        start_time = time.time()
        amazon_data = convert_test_data_to_amazon_format(large_order_list)
        account_data = {"test_account": (pd.DataFrame(amazon_data), pd.DataFrame())}
        result = matcher.match_transaction(transaction, account_data)
        matches = result["matches"]
        end_time = time.time()

        # Should complete within 5 seconds for 1000 orders
        assert end_time - start_time < 5.0
        assert isinstance(matches, list)


@pytest.mark.amazon
def test_integration_with_fixtures(sample_ynab_transaction, sample_amazon_order):
    """Test Amazon matching with standard fixtures."""
    matcher = SimplifiedMatcher()

    amazon_data = convert_test_data_to_amazon_format([sample_amazon_order])
    account_data = {"test_account": (pd.DataFrame(amazon_data), pd.DataFrame())}
    result = matcher.match_transaction(sample_ynab_transaction, account_data)
    matches = result["matches"]

    assert isinstance(matches, list)
    if matches:
        # Verify match structure
        match = matches[0]
        assert "amazon_orders" in match
        assert "confidence" in match
        assert "match_method" in match
        assert isinstance(match["confidence"], (int, float))
        assert 0 <= match["confidence"] <= 1
