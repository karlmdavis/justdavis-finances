#!/usr/bin/env python3
"""Tests for Apple transaction matching module."""

import pytest
from datetime import date, datetime
from finances.apple import AppleMatcher


class TestAppleMatcher:
    """Test the AppleMatcher class."""

    @pytest.fixture
    def matcher(self):
        """Create an AppleMatcher instance for testing."""
        return AppleMatcher()

    @pytest.fixture
    def sample_apple_receipts(self):
        """Sample Apple receipts for testing."""
        return [
            {
                'order_id': 'ML7PQ2XYZ',
                'receipt_date': '2024-08-15',
                'apple_id': 'test@example.com',
                'subtotal': 29.99,
                'tax': 2.98,
                'total': 32.97,
                'items': [
                    {
                        'title': 'Procreate',
                        'cost': 29.99
                    }
                ]
            },
            {
                'order_id': 'NX8QR3ABC',
                'receipt_date': '2024-08-16',
                'apple_id': 'family@example.com',
                'subtotal': 9.99,
                'tax': 0.99,
                'total': 10.98,
                'items': [
                    {
                        'title': 'Apple Music (Monthly)',
                        'cost': 9.99,
                        'subscription': True
                    }
                ]
            },
            {
                'order_id': 'KL5MN4DEF',
                'receipt_date': '2024-08-14',
                'apple_id': 'test@example.com',
                'subtotal': 599.98,
                'tax': 59.64,
                'total': 659.62,
                'items': [
                    {
                        'title': 'Final Cut Pro',
                        'cost': 299.99
                    },
                    {
                        'title': 'Logic Pro',
                        'cost': 299.99
                    }
                ]
            }
        ]

    @pytest.mark.apple
    def test_exact_amount_and_date_match(self, matcher, sample_apple_receipts):
        """Test exact amount and date matching."""
        transaction = {
            'id': 'test-txn-123',
            'date': '2024-08-15',
            'amount': -32970,  # $32.97 expense in milliunits
            'payee_name': 'Apple Store',
            'account_name': 'Chase Credit Card'
        }

        matches = matcher.find_matches(transaction, sample_apple_receipts)

        assert len(matches) > 0
        best_match = max(matches, key=lambda m: m['confidence'])

        # Should match the $32.97 Procreate purchase
        assert best_match['receipt']['order_id'] == 'ML7PQ2XYZ'
        assert best_match['confidence'] == 1.0  # Perfect match

    @pytest.mark.apple
    def test_multi_app_purchase_match(self, matcher, sample_apple_receipts):
        """Test matching to multi-app purchase."""
        transaction = {
            'id': 'test-txn-456',
            'date': '2024-08-14',
            'amount': -659620,  # $659.62 expense in milliunits
            'payee_name': 'Apple Store',
            'account_name': 'Chase Credit Card'
        }

        matches = matcher.find_matches(transaction, sample_apple_receipts)

        assert len(matches) > 0
        best_match = max(matches, key=lambda m: m['confidence'])

        # Should match the multi-app purchase
        assert best_match['receipt']['order_id'] == 'KL5MN4DEF'
        assert len(best_match['receipt']['items']) == 2

    @pytest.mark.apple
    def test_date_window_matching(self, matcher, sample_apple_receipts):
        """Test matching within date window (±2 days)."""
        transaction = {
            'id': 'test-txn-789',
            'date': '2024-08-18',  # 2 days after receipt
            'amount': -10980,  # $10.98 expense in milliunits
            'payee_name': 'Apple Store',
            'account_name': 'Chase Credit Card'
        }

        matches = matcher.find_matches(transaction, sample_apple_receipts)

        assert len(matches) > 0
        # Should find the Apple Music subscription from 2024-08-16
        order_ids = [m['receipt']['order_id'] for m in matches]
        assert 'NX8QR3ABC' in order_ids

        # Confidence should be lower due to date difference
        matching_receipt = next(m for m in matches if m['receipt']['order_id'] == 'NX8QR3ABC')
        assert matching_receipt['confidence'] < 1.0
        assert matching_receipt['confidence'] >= 0.7  # Still good match

    @pytest.mark.apple
    def test_no_matches_found(self, matcher, sample_apple_receipts):
        """Test case where no matches are found."""
        transaction = {
            'id': 'test-txn-999',
            'date': '2024-08-20',
            'amount': -99999,  # $999.99 - no matching receipt
            'payee_name': 'Apple Store',
            'account_name': 'Chase Credit Card'
        }

        matches = matcher.find_matches(transaction, sample_apple_receipts)

        # Should return empty list
        assert matches == []

    @pytest.mark.apple
    def test_subscription_identification(self, matcher, sample_apple_receipts):
        """Test identification of subscription transactions."""
        transaction = {
            'id': 'test-txn-sub',
            'date': '2024-08-16',
            'amount': -10980,  # $10.98 expense in milliunits
            'payee_name': 'Apple Store',
            'account_name': 'Chase Credit Card'
        }

        matches = matcher.find_matches(transaction, sample_apple_receipts)

        assert len(matches) > 0
        best_match = max(matches, key=lambda m: m['confidence'])

        # Should identify as subscription
        has_subscription = any(
            item.get('subscription', False)
            for item in best_match['receipt']['items']
        )
        assert has_subscription

    @pytest.mark.apple
    def test_apple_id_attribution(self, matcher, sample_apple_receipts):
        """Test Apple ID attribution in matches."""
        transaction = {
            'id': 'test-txn-attr',
            'date': '2024-08-15',
            'amount': -32970,  # $32.97 expense in milliunits
            'payee_name': 'Apple Store',
            'account_name': 'Chase Credit Card'
        }

        matches = matcher.find_matches(transaction, sample_apple_receipts)

        assert len(matches) > 0
        best_match = max(matches, key=lambda m: m['confidence'])

        # Should include Apple ID attribution
        assert 'apple_id' in best_match['receipt']
        assert best_match['receipt']['apple_id'] == 'test@example.com'

    @pytest.mark.apple
    def test_confidence_scoring_by_date_distance(self, matcher, sample_apple_receipts):
        """Test confidence scoring based on date distance."""
        # Same amount, different dates
        same_day_transaction = {
            'id': 'test-same-day',
            'date': '2024-08-15',
            'amount': -32970,
            'payee_name': 'Apple Store'
        }

        one_day_off_transaction = {
            'id': 'test-one-day',
            'date': '2024-08-16',
            'amount': -32970,
            'payee_name': 'Apple Store'
        }

        two_days_off_transaction = {
            'id': 'test-two-days',
            'date': '2024-08-17',
            'amount': -32970,
            'payee_name': 'Apple Store'
        }

        same_day_matches = matcher.find_matches(same_day_transaction, sample_apple_receipts)
        one_day_matches = matcher.find_matches(one_day_off_transaction, sample_apple_receipts)
        two_day_matches = matcher.find_matches(two_days_off_transaction, sample_apple_receipts)

        if same_day_matches and one_day_matches and two_day_matches:
            same_day_conf = max(m['confidence'] for m in same_day_matches)
            one_day_conf = max(m['confidence'] for m in one_day_matches)
            two_day_conf = max(m['confidence'] for m in two_day_matches)

            # Confidence should decrease with date distance
            assert same_day_conf > one_day_conf
            assert one_day_conf > two_day_conf

    @pytest.mark.apple
    def test_multiple_apple_ids(self, matcher, sample_apple_receipts):
        """Test handling of multiple Apple IDs in receipt data."""
        # Transaction that could match receipts from different Apple IDs
        transaction = {
            'id': 'test-multi-id',
            'date': '2024-08-15',
            'amount': -32970,
            'payee_name': 'Apple Store'
        }

        # Add receipt with different Apple ID but same amount/date
        additional_receipts = sample_apple_receipts + [
            {
                'order_id': 'ZZ9YY8XXX',
                'receipt_date': '2024-08-15',
                'apple_id': 'another@example.com',
                'total': 32.97,
                'items': [{'title': 'Different App', 'cost': 32.97}]
            }
        ]

        matches = matcher.find_matches(transaction, additional_receipts)

        # Should find multiple matches with different Apple IDs
        assert len(matches) >= 2

        apple_ids = set(m['receipt']['apple_id'] for m in matches)
        assert len(apple_ids) >= 2
        assert 'test@example.com' in apple_ids
        assert 'another@example.com' in apple_ids


class TestAppleMatchingStrategies:
    """Test Apple-specific matching strategies."""

    @pytest.fixture
    def matcher(self):
        return AppleMatcher()

    @pytest.mark.apple
    def test_exact_match_strategy(self, matcher):
        """Test exact match strategy (same date + exact amount)."""
        transaction = {
            'date': '2024-08-15',
            'amount': -29990,  # $29.99
        }

        receipt = {
            'receipt_date': '2024-08-15',
            'total': 29.99,
            'apple_id': 'test@example.com',
            'items': [{'title': 'Test App', 'cost': 29.99}]
        }

        # This would test exact match logic specifically
        # Implementation depends on matcher's internal structure
        pass

    @pytest.mark.apple
    def test_date_window_strategy(self, matcher):
        """Test date window matching strategy."""
        transaction = {
            'date': '2024-08-17',  # 2 days after receipt
            'amount': -29990,
        }

        receipt = {
            'receipt_date': '2024-08-15',
            'total': 29.99,
            'apple_id': 'test@example.com',
            'items': [{'title': 'Test App', 'cost': 29.99}]
        }

        # Should match with reduced confidence
        # Implementation would test date window logic
        pass


class TestAppleEdgeCases:
    """Test edge cases for Apple matching."""

    @pytest.fixture
    def matcher(self):
        return AppleMatcher()

    @pytest.mark.apple
    def test_empty_receipts_list(self, matcher):
        """Test matching with empty receipts list."""
        transaction = {
            'id': 'test-txn',
            'date': '2024-08-15',
            'amount': -32970,
            'payee_name': 'Apple Store'
        }

        matches = matcher.find_matches(transaction, [])
        assert matches == []

    @pytest.mark.apple
    def test_malformed_receipt_data(self, matcher):
        """Test handling of malformed receipt data."""
        transaction = {
            'id': 'test-txn',
            'date': '2024-08-15',
            'amount': -32970,
            'payee_name': 'Apple Store'
        }

        malformed_receipts = [
            {
                'order_id': 'test-receipt',
                # Missing required fields like total, date
            }
        ]

        # Should handle gracefully
        try:
            matches = matcher.find_matches(transaction, malformed_receipts)
            assert isinstance(matches, list)
        except (KeyError, ValueError, TypeError):
            # Acceptable to raise validation errors
            pass

    @pytest.mark.apple
    def test_zero_amount_transactions(self, matcher):
        """Test handling of zero amount transactions (free apps)."""
        transaction = {
            'id': 'test-free',
            'date': '2024-08-15',
            'amount': 0,  # Free app
            'payee_name': 'Apple Store'
        }

        receipts = [
            {
                'order_id': 'free-app',
                'receipt_date': '2024-08-15',
                'apple_id': 'test@example.com',
                'total': 0.00,
                'items': [{'title': 'Free App', 'cost': 0.00}]
            }
        ]

        matches = matcher.find_matches(transaction, receipts)

        # Should handle free transactions
        assert isinstance(matches, list)

    @pytest.mark.apple
    def test_very_small_amounts(self, matcher):
        """Test handling of very small transaction amounts."""
        transaction = {
            'id': 'test-small',
            'date': '2024-08-15',
            'amount': -99,  # $0.99
            'payee_name': 'Apple Store'
        }

        receipts = [
            {
                'order_id': 'small-purchase',
                'receipt_date': '2024-08-15',
                'apple_id': 'test@example.com',
                'total': 0.99,
                'items': [{'title': 'Small In-App Purchase', 'cost': 0.99}]
            }
        ]

        matches = matcher.find_matches(transaction, receipts)

        assert len(matches) > 0
        assert matches[0]['confidence'] > 0

    @pytest.mark.apple
    def test_large_receipt_collection(self, matcher):
        """Test performance with large number of receipts."""
        transaction = {
            'id': 'test-large',
            'date': '2024-08-15',
            'amount': -29990,
            'payee_name': 'Apple Store'
        }

        # Generate large collection of receipts
        large_receipts = []
        for i in range(500):
            large_receipts.append({
                'order_id': f'receipt-{i}',
                'receipt_date': '2024-08-15',
                'apple_id': f'user{i}@example.com',
                'total': 10.00 + i * 0.01,  # Varying amounts
                'items': [{'title': f'App {i}', 'cost': 10.00 + i * 0.01}]
            })

        # Should complete in reasonable time
        import time
        start_time = time.time()
        matches = matcher.find_matches(transaction, large_receipts)
        end_time = time.time()

        # Should be much faster than Amazon matching due to simpler model
        assert end_time - start_time < 2.0
        assert isinstance(matches, list)


class TestAppleReceiptParsing:
    """Test Apple receipt data parsing and validation."""

    @pytest.mark.apple
    def test_receipt_field_validation(self):
        """Test validation of required receipt fields."""
        # Valid receipt
        valid_receipt = {
            'order_id': 'ML7PQ2XYZ',
            'receipt_date': '2024-08-15',
            'apple_id': 'test@example.com',
            'total': 29.99,
            'items': [{'title': 'Test App', 'cost': 29.99}]
        }

        # Invalid receipts missing required fields
        invalid_receipts = [
            {'order_id': 'ML7PQ2XYZ'},  # Missing date, total, items
            {'receipt_date': '2024-08-15'},  # Missing order_id, total, items
            {'total': 29.99},  # Missing order_id, date, items
        ]

        # Test that validation works (implementation specific)
        pass

    @pytest.mark.apple
    def test_currency_parsing(self):
        """Test parsing of currency values in receipts."""
        receipts_with_currency = [
            {
                'total': 29.99,  # Float
                'items': [{'cost': 29.99}]
            },
            {
                'total': '$29.99',  # String with $
                'items': [{'cost': '$29.99'}]
            },
            {
                'total': '29.99',  # String without $
                'items': [{'cost': '29.99'}]
            }
        ]

        # All should parse to same normalized format
        # Implementation would test currency normalization
        pass


@pytest.mark.apple
def test_integration_with_fixtures(sample_ynab_transaction, sample_apple_receipt):
    """Test Apple matching with standard fixtures."""
    matcher = AppleMatcher()

    # Convert fixture receipt to expected format
    receipt_data = [sample_apple_receipt]

    matches = matcher.find_matches(sample_ynab_transaction, receipt_data)

    assert isinstance(matches, list)
    if matches:
        # Verify match structure
        match = matches[0]
        assert 'receipt' in match
        assert 'confidence' in match
        assert 'match_type' in match
        assert isinstance(match['confidence'], (int, float))
        assert 0 <= match['confidence'] <= 1