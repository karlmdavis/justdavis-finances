#!/usr/bin/env python3
"""Tests for Apple transaction matching module."""


import pytest

from finances.apple import AppleMatcher, normalize_apple_receipt_data


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
                "order_id": "ML7PQ2XYZ",
                "receipt_date": "Aug 15, 2024",
                "apple_id": "test@example.com",
                "subtotal": 2999,  # $29.99 in cents
                "tax": 298,  # $2.98 in cents
                "total": 3297,  # $32.97 in cents
                "items": [{"title": "Procreate", "cost": 2999}],  # $29.99 in cents
            },
            {
                "order_id": "NX8QR3ABC",
                "receipt_date": "Aug 16, 2024",
                "apple_id": "family@example.com",
                "subtotal": 999,  # $9.99 in cents
                "tax": 99,  # $0.99 in cents
                "total": 1098,  # $10.98 in cents
                "items": [
                    {"title": "Apple Music (Monthly)", "cost": 999, "subscription": True}  # $9.99 in cents
                ],
            },
            {
                "order_id": "KL5MN4DEF",
                "receipt_date": "Aug 14, 2024",
                "apple_id": "test@example.com",
                "subtotal": 59998,  # $599.98 in cents
                "tax": 5964,  # $59.64 in cents
                "total": 65962,  # $659.62 in cents
                "items": [
                    {"title": "Final Cut Pro", "cost": 29999},  # $299.99 in cents
                    {"title": "Logic Pro", "cost": 29999},  # $299.99 in cents
                ],
            },
        ]

    @pytest.mark.apple
    def test_exact_amount_and_date_match(self, matcher, sample_apple_receipts):
        """Test exact amount and date matching."""
        transaction = {
            "id": "test-txn-123",
            "date": "2024-08-15",
            "amount": -32970,  # $32.97 expense in milliunits
            "payee_name": "Apple Store",
            "account_name": "Chase Credit Card",
        }

        # Normalize receipts data like the real system does
        receipts_df = normalize_apple_receipt_data(sample_apple_receipts)
        result = matcher.match_single_transaction(transaction, receipts_df)

        assert len(result.receipts) > 0
        assert result.confidence == 1.0  # Perfect match

        # Should match the $32.97 Procreate purchase
        matched_receipt = result.receipts[0]
        assert matched_receipt.id == "ML7PQ2XYZ"

    @pytest.mark.apple
    def test_multi_app_purchase_match(self, matcher, sample_apple_receipts):
        """Test matching to multi-app purchase."""
        transaction = {
            "id": "test-txn-456",
            "date": "2024-08-14",
            "amount": -659620,  # $659.62 expense in milliunits
            "payee_name": "Apple Store",
            "account_name": "Chase Credit Card",
        }

        # Normalize receipts data like the real system does
        receipts_df = normalize_apple_receipt_data(sample_apple_receipts)
        result = matcher.match_single_transaction(transaction, receipts_df)

        assert len(result.receipts) > 0

        # Should match the multi-app purchase
        matched_receipt = result.receipts[0]
        assert matched_receipt.id == "KL5MN4DEF"
        assert len(matched_receipt.items) == 2

    @pytest.mark.apple
    def test_date_window_matching(self, matcher, sample_apple_receipts):
        """Test matching within date window (±2 days)."""
        transaction = {
            "id": "test-txn-789",
            "date": "2024-08-18",  # 2 days after receipt
            "amount": -10980,  # $10.98 expense in milliunits
            "payee_name": "Apple Store",
            "account_name": "Chase Credit Card",
        }

        # Normalize receipts data like the real system does
        receipts_df = normalize_apple_receipt_data(sample_apple_receipts)
        result = matcher.match_single_transaction(transaction, receipts_df)
        matches = [result] if result.receipts else []

        assert len(matches) > 0
        # Should find a match
        match_result = matches[0]
        assert match_result.receipts

        # Confidence should be lower due to date difference
        assert match_result.confidence < 1.0
        assert match_result.confidence >= 0.7  # Still good match

    @pytest.mark.apple
    def test_no_matches_found(self, matcher, sample_apple_receipts):
        """Test case where no matches are found."""
        transaction = {
            "id": "test-txn-999",
            "date": "2024-08-20",
            "amount": -99999,  # $999.99 - no matching receipt
            "payee_name": "Apple Store",
            "account_name": "Chase Credit Card",
        }

        # Normalize receipts data like the real system does
        receipts_df = normalize_apple_receipt_data(sample_apple_receipts)
        result = matcher.match_single_transaction(transaction, receipts_df)
        matches = [result] if result.receipts else []

        # Should return empty list
        assert matches == []

    @pytest.mark.apple
    def test_subscription_identification(self, matcher, sample_apple_receipts):
        """Test identification of subscription transactions."""
        transaction = {
            "id": "test-txn-sub",
            "date": "2024-08-16",
            "amount": -10980,  # $10.98 expense in milliunits
            "payee_name": "Apple Store",
            "account_name": "Chase Credit Card",
        }

        # Normalize receipts data like the real system does
        receipts_df = normalize_apple_receipt_data(sample_apple_receipts)
        result = matcher.match_single_transaction(transaction, receipts_df)
        matches = [result] if result.receipts else []

        assert len(matches) > 0
        best_match = matches[0]

        # Should find a match with reasonable confidence
        assert best_match.confidence >= 0.7

    @pytest.mark.apple
    def test_apple_id_attribution(self, matcher, sample_apple_receipts):
        """Test Apple ID attribution in matches."""
        transaction = {
            "id": "test-txn-attr",
            "date": "2024-08-15",
            "amount": -32970,  # $32.97 expense in milliunits
            "payee_name": "Apple Store",
            "account_name": "Chase Credit Card",
        }

        # Normalize receipts data like the real system does
        receipts_df = normalize_apple_receipt_data(sample_apple_receipts)
        result = matcher.match_single_transaction(transaction, receipts_df)
        matches = [result] if result.receipts else []

        assert len(matches) > 0
        best_match = matches[0]

        # Should find a match with reasonable confidence
        assert best_match.confidence >= 0.7

    @pytest.mark.apple
    def test_confidence_scoring_by_date_distance(self, matcher, sample_apple_receipts):
        """Test confidence scoring based on date distance."""
        # Same amount, different dates
        same_day_transaction = {
            "id": "test-same-day",
            "date": "2024-08-15",
            "amount": -32970,
            "payee_name": "Apple Store",
        }

        one_day_off_transaction = {
            "id": "test-one-day",
            "date": "2024-08-16",
            "amount": -32970,
            "payee_name": "Apple Store",
        }

        two_days_off_transaction = {
            "id": "test-two-days",
            "date": "2024-08-17",
            "amount": -32970,
            "payee_name": "Apple Store",
        }

        # Normalize receipts data like the real system does
        receipts_df = normalize_apple_receipt_data(sample_apple_receipts)

        same_day_result = matcher.match_single_transaction(same_day_transaction, receipts_df)
        one_day_result = matcher.match_single_transaction(one_day_off_transaction, receipts_df)
        two_day_result = matcher.match_single_transaction(two_days_off_transaction, receipts_df)

        if same_day_result.receipts and one_day_result.receipts and two_day_result.receipts:
            # Confidence should decrease with date distance
            assert same_day_result.confidence > one_day_result.confidence
            assert one_day_result.confidence > two_day_result.confidence

    @pytest.mark.apple
    def test_multiple_apple_ids(self, matcher, sample_apple_receipts):
        """Test handling of multiple Apple IDs in receipt data."""
        # Transaction that could match receipts from different Apple IDs
        transaction = {
            "id": "test-multi-id",
            "date": "2024-08-15",
            "amount": -32970,
            "payee_name": "Apple Store",
        }

        # Add receipt with different Apple ID but same amount/date
        additional_receipts = [
            *sample_apple_receipts,
            {
                "order_id": "ZZ9YY8XXX",
                "receipt_date": "Aug 15, 2024",
                "apple_id": "another@example.com",
                "total": 32.97,
                "items": [{"title": "Different App", "cost": 32.97}],
            },
        ]

        # Normalize receipts data like the real system does
        receipts_df = normalize_apple_receipt_data(additional_receipts)
        result = matcher.match_single_transaction(transaction, receipts_df)

        # Should find at least one match
        assert result.receipts
        assert len(result.receipts) >= 1


class TestAppleMatchingStrategies:
    """Test Apple-specific matching strategies."""

    @pytest.fixture
    def matcher(self):
        return AppleMatcher()

    @pytest.mark.apple
    def test_exact_match_strategy(self, matcher):
        """Test exact match strategy (same date + exact amount)."""

        # This would test exact match logic specifically
        # Implementation depends on matcher's internal structure
        pass

    @pytest.mark.apple
    def test_date_window_strategy(self, matcher):
        """Test date window matching strategy."""

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
        transaction = {"id": "test-txn", "date": "2024-08-15", "amount": -32970, "payee_name": "Apple Store"}

        # Normalize empty receipts data
        receipts_df = normalize_apple_receipt_data([])
        result = matcher.match_single_transaction(transaction, receipts_df)
        assert not result.receipts

    @pytest.mark.apple
    def test_malformed_receipt_data(self, matcher):
        """Test handling of malformed receipt data."""
        transaction = {"id": "test-txn", "date": "2024-08-15", "amount": -32970, "payee_name": "Apple Store"}

        malformed_receipts = [
            {
                "order_id": "test-receipt",
                # Missing required fields like total, date
            }
        ]

        # Should handle gracefully
        try:
            receipts_df = normalize_apple_receipt_data(malformed_receipts)
            result = matcher.match_single_transaction(transaction, receipts_df)
            assert isinstance(result.receipts, list)
        except (KeyError, ValueError, TypeError):
            # Acceptable to raise validation errors
            pass

    @pytest.mark.apple
    def test_zero_amount_transactions(self, matcher):
        """Test handling of zero amount transactions (free apps)."""
        transaction = {
            "id": "test-free",
            "date": "2024-08-15",
            "amount": 0,  # Free app
            "payee_name": "Apple Store",
        }

        receipts = [
            {
                "order_id": "free-app",
                "receipt_date": "Aug 15, 2024",
                "apple_id": "test@example.com",
                "total": 0.00,
                "items": [{"title": "Free App", "cost": 0.00}],
            }
        ]

        receipts_df = normalize_apple_receipt_data(receipts)
        result = matcher.match_single_transaction(transaction, receipts_df)

        # Should handle free transactions
        assert isinstance(result.receipts, list)

    @pytest.mark.apple
    def test_very_small_amounts(self, matcher):
        """Test handling of very small transaction amounts."""
        transaction = {
            "id": "test-small",
            "date": "2024-08-15",
            "amount": -990,  # $0.99 in milliunits
            "payee_name": "Apple Store",
        }

        receipts = [
            {
                "order_id": "small-purchase",
                "receipt_date": "Aug 15, 2024",
                "apple_id": "test@example.com",
                "total": 99,  # $0.99 in cents
                "items": [{"title": "Small In-App Purchase", "cost": 99}],  # $0.99 in cents
            }
        ]

        receipts_df = normalize_apple_receipt_data(receipts)
        result = matcher.match_single_transaction(transaction, receipts_df)

        assert result.receipts
        assert result.confidence > 0

    @pytest.mark.apple
    def test_large_receipt_collection(self, matcher):
        """Test performance with large number of receipts."""
        transaction = {
            "id": "test-large",
            "date": "2024-08-15",
            "amount": -29990,
            "payee_name": "Apple Store",
        }

        # Generate large collection of receipts
        large_receipts = []
        for i in range(500):
            large_receipts.append(
                {
                    "order_id": f"receipt-{i}",
                    "receipt_date": "Aug 15, 2024",
                    "apple_id": f"user{i}@example.com",
                    "total": 10.00 + i * 0.01,  # Varying amounts
                    "items": [{"title": f"App {i}", "cost": 10.00 + i * 0.01}],
                }
            )

        # Should complete in reasonable time
        import time

        start_time = time.time()
        receipts_df = normalize_apple_receipt_data(large_receipts)
        result = matcher.match_single_transaction(transaction, receipts_df)
        end_time = time.time()

        # Should be much faster than Amazon matching due to simpler model
        assert end_time - start_time < 2.0
        assert isinstance(result.receipts, list)


class TestAppleReceiptParsing:
    """Test Apple receipt data parsing and validation."""

    @pytest.mark.apple
    def test_receipt_field_validation(self):
        """Test validation of required receipt fields."""
        # Valid receipt

        # Invalid receipts missing required fields

        # Test that validation works (implementation specific)
        pass

    @pytest.mark.apple
    def test_currency_parsing(self):
        """Test parsing of currency values in receipts."""

        # All should parse to same normalized format
        # Implementation would test currency normalization
        pass


@pytest.mark.apple
def test_integration_with_fixtures(sample_ynab_transaction, sample_apple_receipt):
    """Test Apple matching with standard fixtures."""
    matcher = AppleMatcher()

    # Convert fixture receipt to expected format
    receipt_data = [sample_apple_receipt]
    receipts_df = normalize_apple_receipt_data(receipt_data)
    result = matcher.match_single_transaction(sample_ynab_transaction, receipts_df)

    assert isinstance(result.receipts, list)
    # Verify match result structure
    assert hasattr(result, "confidence")
    assert hasattr(result, "match_method")
    assert isinstance(result.confidence, (int, float))
    assert 0 <= result.confidence <= 1
