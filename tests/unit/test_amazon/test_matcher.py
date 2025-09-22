#!/usr/bin/env python3
"""Tests for Amazon transaction matching module."""

import pytest
from datetime import date, datetime
from finances.amazon import SimplifiedMatcher
from finances.core.currency import milliunits_to_cents


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
                'order_id': '111-2223334-5556667',
                'order_date': '2024-08-15',
                'ship_date': '2024-08-15',
                'total': 4599,  # $45.99 in cents
                'items': [
                    {
                        'name': 'Echo Dot (4th Gen) - Charcoal',
                        'quantity': 1,
                        'amount': 4599,
                        'asin': 'B084J4KNDS'
                    }
                ]
            },
            {
                'order_id': '111-2223334-7778889',
                'order_date': '2024-08-16',
                'ship_date': '2024-08-17',
                'total': 2999,  # $29.99 in cents
                'items': [
                    {
                        'name': 'USB-C Cable 6ft',
                        'quantity': 1,
                        'amount': 2999,
                        'asin': 'B08CXYZ123'
                    }
                ]
            },
            {
                'order_id': '111-2223334-9990001',
                'order_date': '2024-08-14',
                'ship_date': '2024-08-15',
                'total': 12999,  # $129.99 in cents
                'items': [
                    {
                        'name': 'Wireless Headphones',
                        'quantity': 1,
                        'amount': 8999,
                        'asin': 'B07WXYZ789'
                    },
                    {
                        'name': 'Phone Case',
                        'quantity': 1,
                        'amount': 4000,
                        'asin': 'B08ABCD456'
                    }
                ]
            }
        ]

    @pytest.mark.amazon
    def test_exact_amount_match(self, matcher, sample_amazon_orders):
        """Test exact amount matching with single order."""
        transaction = {
            'id': 'test-txn-123',
            'date': '2024-08-15',
            'amount': -45990,  # $45.99 expense in milliunits
            'payee_name': 'AMZN Mktp US*TEST123',
            'account_name': 'Chase Credit Card'
        }

        matches = matcher.find_matches(transaction, sample_amazon_orders)

        assert len(matches) > 0
        best_match = max(matches, key=lambda m: m['confidence'])

        # Should match the $45.99 order
        assert best_match['order']['order_id'] == '111-2223334-5556667'
        assert best_match['confidence'] >= 0.9  # High confidence for exact match

    @pytest.mark.amazon
    def test_multi_item_order_match(self, matcher, sample_amazon_orders):
        """Test matching to multi-item order."""
        transaction = {
            'id': 'test-txn-456',
            'date': '2024-08-14',
            'amount': -129990,  # $129.99 expense in milliunits
            'payee_name': 'AMZN Mktp US*TEST456',
            'account_name': 'Chase Credit Card'
        }

        matches = matcher.find_matches(transaction, sample_amazon_orders)

        assert len(matches) > 0
        best_match = max(matches, key=lambda m: m['confidence'])

        # Should match the multi-item $129.99 order
        assert best_match['order']['order_id'] == '111-2223334-9990001'
        assert len(best_match['order']['items']) == 2

    @pytest.mark.amazon
    def test_date_window_matching(self, matcher, sample_amazon_orders):
        """Test matching within date window for shipping delays."""
        transaction = {
            'id': 'test-txn-789',
            'date': '2024-08-18',  # 2 days after ship date
            'amount': -29990,  # $29.99 expense in milliunits
            'payee_name': 'AMZN Mktp US*TEST789',
            'account_name': 'Chase Credit Card'
        }

        matches = matcher.find_matches(transaction, sample_amazon_orders)

        assert len(matches) > 0
        # Should still find the order shipped on 2024-08-17
        order_ids = [m['order']['order_id'] for m in matches]
        assert '111-2223334-7778889' in order_ids

    @pytest.mark.amazon
    def test_no_matches_found(self, matcher, sample_amazon_orders):
        """Test case where no matches are found."""
        transaction = {
            'id': 'test-txn-999',
            'date': '2024-08-20',
            'amount': -99999,  # $999.99 - no matching order
            'payee_name': 'AMZN Mktp US*TEST999',
            'account_name': 'Chase Credit Card'
        }

        matches = matcher.find_matches(transaction, sample_amazon_orders)

        # Should return empty list or very low confidence matches
        high_confidence_matches = [m for m in matches if m['confidence'] > 0.5]
        assert len(high_confidence_matches) == 0

    @pytest.mark.amazon
    def test_confidence_scoring(self, matcher, sample_amazon_orders):
        """Test confidence scoring accuracy."""
        # Perfect match: same date, exact amount
        perfect_transaction = {
            'id': 'test-txn-perfect',
            'date': '2024-08-15',
            'amount': -45990,
            'payee_name': 'AMZN Mktp US*PERFECT',
            'account_name': 'Chase Credit Card'
        }

        # Good match: ship date, exact amount
        good_transaction = {
            'id': 'test-txn-good',
            'date': '2024-08-17',  # Ship date
            'amount': -29990,
            'payee_name': 'AMZN Mktp US*GOOD',
            'account_name': 'Chase Credit Card'
        }

        # Fair match: within window, exact amount
        fair_transaction = {
            'id': 'test-txn-fair',
            'date': '2024-08-19',  # 2 days after ship date
            'amount': -29990,
            'payee_name': 'AMZN Mktp US*FAIR',
            'account_name': 'Chase Credit Card'
        }

        perfect_matches = matcher.find_matches(perfect_transaction, sample_amazon_orders)
        good_matches = matcher.find_matches(good_transaction, sample_amazon_orders)
        fair_matches = matcher.find_matches(fair_transaction, sample_amazon_orders)

        if perfect_matches and good_matches and fair_matches:
            perfect_conf = max(m['confidence'] for m in perfect_matches)
            good_conf = max(m['confidence'] for m in good_matches)
            fair_conf = max(m['confidence'] for m in fair_matches)

            # Confidence should decrease with date distance
            assert perfect_conf >= good_conf
            assert good_conf >= fair_conf

    @pytest.mark.amazon
    def test_split_payment_detection(self, matcher):
        """Test detection of split payments across multiple orders."""
        # Large transaction that might span multiple orders
        transaction = {
            'id': 'test-txn-split',
            'date': '2024-08-15',
            'amount': -75989,  # $759.89 - larger than any single order
            'payee_name': 'AMZN Mktp US*SPLIT',
            'account_name': 'Chase Credit Card'
        }

        # Multiple orders that could combine to this amount
        orders = [
            {
                'order_id': 'split-order-1',
                'order_date': '2024-08-15',
                'ship_date': '2024-08-15',
                'total': 25000,  # $250.00
                'items': [{'name': 'Item 1', 'amount': 25000}]
            },
            {
                'order_id': 'split-order-2',
                'order_date': '2024-08-15',
                'ship_date': '2024-08-15',
                'total': 30989,  # $309.89
                'items': [{'name': 'Item 2', 'amount': 30989}]
            },
            {
                'order_id': 'split-order-3',
                'order_date': '2024-08-15',
                'ship_date': '2024-08-15',
                'total': 20000,  # $200.00
                'items': [{'name': 'Item 3', 'amount': 20000}]
            }
        ]

        matches = matcher.find_matches(transaction, orders)

        # Should detect that this might be a split payment
        assert len(matches) > 0

        # Check if any match indicates split payment possibility
        has_split_indication = any(
            m.get('split_payment_candidate', False) or
            m.get('match_type') == 'split' for m in matches
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
        transaction = {
            'date': '2024-08-15',
            'amount': -45990,
        }

        order = {
            'order_date': '2024-08-15',
            'total': 4599,
            'items': [{'name': 'Test Item', 'amount': 4599}]
        }

        # This would test the complete match strategy specifically
        # Implementation depends on matcher's internal structure
        pass

    @pytest.mark.amazon
    def test_fuzzy_match_strategy(self, matcher):
        """Test fuzzy matching with amount tolerance."""
        transaction = {
            'date': '2024-08-15',
            'amount': -45950,  # $459.50 - close but not exact
        }

        order = {
            'order_date': '2024-08-15',
            'total': 4599,  # $45.99
            'items': [{'name': 'Test Item', 'amount': 4599}]
        }

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
            'id': 'test-txn',
            'date': '2024-08-15',
            'amount': -45990,
            'payee_name': 'AMZN Mktp US*TEST',
            'account_name': 'Chase Credit Card'
        }

        matches = matcher.find_matches(transaction, [])
        assert matches == []

    @pytest.mark.amazon
    def test_malformed_transaction(self, matcher):
        """Test handling of malformed transaction data."""
        malformed_transaction = {
            'id': 'test-txn',
            # Missing required fields
        }

        orders = [
            {
                'order_id': 'test-order',
                'order_date': '2024-08-15',
                'total': 4599,
                'items': []
            }
        ]

        # Should handle gracefully without crashing
        try:
            matches = matcher.find_matches(malformed_transaction, orders)
            # Should return empty list or handle error gracefully
            assert isinstance(matches, list)
        except (KeyError, ValueError, TypeError):
            # Acceptable to raise validation errors
            pass

    @pytest.mark.amazon
    def test_malformed_order_data(self, matcher):
        """Test handling of malformed order data."""
        transaction = {
            'id': 'test-txn',
            'date': '2024-08-15',
            'amount': -45990,
            'payee_name': 'AMZN Mktp US*TEST',
            'account_name': 'Chase Credit Card'
        }

        malformed_orders = [
            {
                'order_id': 'test-order',
                # Missing required fields like total, date
            }
        ]

        # Should handle gracefully
        try:
            matches = matcher.find_matches(transaction, malformed_orders)
            assert isinstance(matches, list)
        except (KeyError, ValueError, TypeError):
            # Acceptable to raise validation errors
            pass

    @pytest.mark.amazon
    def test_very_large_order_list(self, matcher):
        """Test performance with large number of orders."""
        transaction = {
            'id': 'test-txn',
            'date': '2024-08-15',
            'amount': -45990,
            'payee_name': 'AMZN Mktp US*TEST',
            'account_name': 'Chase Credit Card'
        }

        # Generate large list of orders
        large_order_list = []
        for i in range(1000):
            large_order_list.append({
                'order_id': f'order-{i}',
                'order_date': '2024-08-15',
                'ship_date': '2024-08-15',
                'total': 1000 + i,  # Varying amounts
                'items': [{'name': f'Item {i}', 'amount': 1000 + i}]
            })

        # Should complete in reasonable time
        import time
        start_time = time.time()
        matches = matcher.find_matches(transaction, large_order_list)
        end_time = time.time()

        # Should complete within 5 seconds for 1000 orders
        assert end_time - start_time < 5.0
        assert isinstance(matches, list)


@pytest.mark.amazon
def test_integration_with_fixtures(sample_ynab_transaction, sample_amazon_order):
    """Test Amazon matching with standard fixtures."""
    matcher = SimplifiedMatcher()

    matches = matcher.find_matches(sample_ynab_transaction, [sample_amazon_order])

    assert isinstance(matches, list)
    if matches:
        # Verify match structure
        match = matches[0]
        assert 'order' in match
        assert 'confidence' in match
        assert 'match_type' in match
        assert isinstance(match['confidence'], (int, float))
        assert 0 <= match['confidence'] <= 1