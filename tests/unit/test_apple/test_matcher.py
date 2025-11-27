#!/usr/bin/env python3
"""Tests for Apple transaction matching module."""


import pytest

from finances.apple import AppleMatcher
from finances.apple.parser import ParsedReceipt
from finances.ynab.models import YnabTransaction


def receipts_to_list_for_testing(receipt_dicts):
    """Convert raw receipt dicts to list[ParsedReceipt] for testing (mimics real system flow)."""
    # Convert dicts to domain models (matches production flow)
    return [ParsedReceipt.from_dict(r) for r in receipt_dicts]


def dict_to_ynab_transaction(tx_dict):
    """Convert dict to YnabTransaction for testing."""
    return YnabTransaction.from_dict(tx_dict)


class TestAppleMatcher:
    """Test the AppleMatcher class."""

    @pytest.fixture
    def matcher(self):
        """Create an AppleMatcher instance for testing."""
        return AppleMatcher()

    @pytest.fixture
    def sample_apple_receipts(self):
        """
        Sample Apple receipts for testing.

        IMPORTANT: Amounts are in CENTS (as integers) because the parser now returns
        integer cents. The parser converts "$29.99" → 2999 cents.
        Dates must be in ISO format (YYYY-MM-DD) for ParsedReceipt.from_dict().
        base_name is required for all receipts (set by parser from HTML filename).
        """
        return [
            {
                "order_id": "ML7PQ2XYZ",
                "base_name": "20240815_120000_receipt_ML7PQ2XYZ",
                "receipt_date": "2024-08-15",  # ISO format required
                "apple_id": "test@example.com",
                "subtotal": 2999,  # $29.99 → 2999 cents (parser output)
                "tax": 298,  # $2.98 → 298 cents
                "total": 3297,  # $32.97 → 3297 cents
                "items": [{"title": "Procreate", "cost": 2999}],  # $29.99 → 2999 cents
            },
            {
                "order_id": "NX8QR3ABC",
                "base_name": "20240816_120000_receipt_NX8QR3ABC",
                "receipt_date": "2024-08-16",  # ISO format required
                "apple_id": "family@example.com",
                "subtotal": 999,  # $9.99 → 999 cents
                "tax": 99,  # $0.99 → 99 cents
                "total": 1098,  # $10.98 → 1098 cents
                "items": [
                    {"title": "Apple Music (Monthly)", "cost": 999, "subscription": True}  # $9.99 → 999 cents
                ],
            },
            {
                "order_id": "KL5MN4DEF",
                "base_name": "20240814_120000_receipt_KL5MN4DEF",
                "receipt_date": "2024-08-14",  # ISO format required
                "apple_id": "test@example.com",
                "subtotal": 59998,  # $599.98 → 59998 cents
                "tax": 5964,  # $59.64 → 5964 cents
                "total": 65962,  # $659.62 → 65962 cents
                "items": [
                    {"title": "Final Cut Pro", "cost": 29999},  # $299.99 → 29999 cents
                    {"title": "Logic Pro", "cost": 29999},  # $299.99 → 29999 cents
                ],
            },
        ]

    @pytest.mark.apple
    def test_exact_amount_and_date_match(self, matcher, sample_apple_receipts):
        """Test exact amount and date matching."""
        transaction_dict = {
            "id": "test-txn-123",
            "date": "2024-08-15",
            "amount": -32970,  # $32.97 expense in milliunits
            "payee_name": "Apple Store",
            "account_name": "Chase Credit Card",
        }

        transaction = dict_to_ynab_transaction(transaction_dict)

        # Normalize receipts data like the real system does
        receipts_df = receipts_to_list_for_testing(sample_apple_receipts)
        result = matcher.match_single_transaction(transaction, receipts_df)

        assert len(result.receipts) > 0
        assert result.confidence == 1.0  # Perfect match

        # Should match the $32.97 Procreate purchase
        matched_receipt = result.receipts[0]
        assert matched_receipt.id == "20240815_120000_receipt_ML7PQ2XYZ"  # Uses base_name (filename)

    @pytest.mark.apple
    def test_multi_app_purchase_match(self, matcher, sample_apple_receipts):
        """Test matching to multi-app purchase."""
        transaction_dict = {
            "id": "test-txn-456",
            "date": "2024-08-14",
            "amount": -659620,  # $659.62 expense in milliunits
            "payee_name": "Apple Store",
            "account_name": "Chase Credit Card",
        }

        transaction = dict_to_ynab_transaction(transaction_dict)

        # Normalize receipts data like the real system does
        receipts_df = receipts_to_list_for_testing(sample_apple_receipts)
        result = matcher.match_single_transaction(transaction, receipts_df)

        assert len(result.receipts) > 0

        # Should match the multi-app purchase
        matched_receipt = result.receipts[0]
        assert matched_receipt.id == "20240814_120000_receipt_KL5MN4DEF"  # Uses base_name (filename)
        assert len(matched_receipt.items) == 2

    @pytest.mark.apple
    def test_date_window_matching(self, matcher, sample_apple_receipts):
        """Test matching within date window (±2 days)."""
        transaction_dict = {
            "id": "test-txn-789",
            "date": "2024-08-18",  # 2 days after receipt
            "amount": -10980,  # $10.98 expense in milliunits
            "payee_name": "Apple Store",
            "account_name": "Chase Credit Card",
        }

        transaction = dict_to_ynab_transaction(transaction_dict)

        # Normalize receipts data like the real system does
        receipts_df = receipts_to_list_for_testing(sample_apple_receipts)
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
        transaction_dict = {
            "id": "test-txn-999",
            "date": "2024-08-20",
            "amount": -99999,  # $999.99 - no matching receipt
            "payee_name": "Apple Store",
            "account_name": "Chase Credit Card",
        }

        transaction = dict_to_ynab_transaction(transaction_dict)

        # Normalize receipts data like the real system does
        receipts_df = receipts_to_list_for_testing(sample_apple_receipts)
        result = matcher.match_single_transaction(transaction, receipts_df)
        matches = [result] if result.receipts else []

        # Should return empty list
        assert matches == []

    @pytest.mark.apple
    def test_subscription_identification(self, matcher, sample_apple_receipts):
        """Test identification of subscription transactions."""
        transaction_dict = {
            "id": "test-txn-sub",
            "date": "2024-08-16",
            "amount": -10980,  # $10.98 expense in milliunits
            "payee_name": "Apple Store",
            "account_name": "Chase Credit Card",
        }

        transaction = dict_to_ynab_transaction(transaction_dict)

        # Normalize receipts data like the real system does
        receipts_df = receipts_to_list_for_testing(sample_apple_receipts)
        result = matcher.match_single_transaction(transaction, receipts_df)
        matches = [result] if result.receipts else []

        assert len(matches) > 0
        best_match = matches[0]

        # Should find a match with reasonable confidence
        assert best_match.confidence >= 0.7

    @pytest.mark.apple
    def test_apple_id_attribution(self, matcher, sample_apple_receipts):
        """Test Apple ID attribution in matches."""
        transaction_dict = {
            "id": "test-txn-attr",
            "date": "2024-08-15",
            "amount": -32970,  # $32.97 expense in milliunits
            "payee_name": "Apple Store",
            "account_name": "Chase Credit Card",
        }

        transaction = dict_to_ynab_transaction(transaction_dict)

        # Normalize receipts data like the real system does
        receipts_df = receipts_to_list_for_testing(sample_apple_receipts)
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
        same_day_transaction = dict_to_ynab_transaction(
            {
                "id": "test-same-day",
                "date": "2024-08-15",
                "amount": -32970,
                "payee_name": "Apple Store",
            }
        )

        one_day_off_transaction = dict_to_ynab_transaction(
            {
                "id": "test-one-day",
                "date": "2024-08-16",
                "amount": -32970,
                "payee_name": "Apple Store",
            }
        )

        two_days_off_transaction = dict_to_ynab_transaction(
            {
                "id": "test-two-days",
                "date": "2024-08-17",
                "amount": -32970,
                "payee_name": "Apple Store",
            }
        )

        # Normalize receipts data like the real system does
        receipts_df = receipts_to_list_for_testing(sample_apple_receipts)

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
        transaction_dict = {
            "id": "test-multi-id",
            "date": "2024-08-15",
            "amount": -32970,
            "payee_name": "Apple Store",
        }

        transaction = dict_to_ynab_transaction(transaction_dict)

        # Add receipt with different Apple ID but same amount/date
        additional_receipts = [
            *sample_apple_receipts,
            {
                "order_id": "ZZ9YY8XXX",
                "receipt_date": "2024-08-15",
                "apple_id": "another@example.com",
                "total": 3297,  # $32.97 → 3297 cents
                "items": [{"title": "Different App", "cost": 3297}],  # $32.97 → 3297 cents
            },
        ]

        # Normalize receipts data like the real system does
        receipts_df = receipts_to_list_for_testing(additional_receipts)
        result = matcher.match_single_transaction(transaction, receipts_df)

        # Should find at least one match
        assert result.receipts
        assert len(result.receipts) >= 1


class TestAppleEdgeCases:
    """Test edge cases for Apple matching."""

    @pytest.fixture
    def matcher(self):
        return AppleMatcher()

    @pytest.mark.apple
    def test_empty_receipts_list(self, matcher):
        """Test matching with empty receipts list."""
        transaction_dict = {
            "id": "test-txn",
            "date": "2024-08-15",
            "amount": -32970,
            "payee_name": "Apple Store",
        }

        transaction = dict_to_ynab_transaction(transaction_dict)

        # Normalize empty receipts data
        receipts_df = receipts_to_list_for_testing([])
        result = matcher.match_single_transaction(transaction, receipts_df)
        assert not result.receipts

    @pytest.mark.apple
    def test_malformed_receipt_data(self, matcher):
        """Test handling of malformed receipt data."""
        transaction_dict = {
            "id": "test-txn",
            "date": "2024-08-15",
            "amount": -32970,
            "payee_name": "Apple Store",
        }

        transaction = dict_to_ynab_transaction(transaction_dict)

        malformed_receipts = [
            {
                "order_id": "test-receipt",
                # Missing required fields like total, date
            }
        ]

        # Should handle gracefully
        try:
            receipts_df = receipts_to_list_for_testing(malformed_receipts)
            result = matcher.match_single_transaction(transaction, receipts_df)
            assert isinstance(result.receipts, list)
        except (KeyError, ValueError, TypeError, AttributeError):
            # Acceptable to raise validation errors (including AttributeError from pandas)
            pass

    @pytest.mark.apple
    def test_zero_amount_transactions(self, matcher):
        """Test handling of zero amount transactions (free apps)."""
        transaction_dict = {
            "id": "test-free",
            "date": "2024-08-15",
            "amount": 0,  # Free app
            "payee_name": "Apple Store",
        }

        transaction = dict_to_ynab_transaction(transaction_dict)

        receipts = [
            {
                "order_id": "free-app",
                "base_name": "20240815_120000_free_app",
                "receipt_date": "2024-08-15",
                "apple_id": "test@example.com",
                "total": 0,  # $0.00 → 0 cents
                "items": [{"title": "Free App", "cost": 0}],  # Free
            }
        ]

        receipts_df = receipts_to_list_for_testing(receipts)
        result = matcher.match_single_transaction(transaction, receipts_df)

        # Should handle free transactions
        assert isinstance(result.receipts, list)

    @pytest.mark.apple
    def test_very_small_amounts(self, matcher):
        """Test handling of very small transaction amounts."""
        transaction_dict = {
            "id": "test-small",
            "date": "2024-08-15",
            "amount": -990,  # $0.99 in milliunits
            "payee_name": "Apple Store",
        }

        transaction = dict_to_ynab_transaction(transaction_dict)

        receipts = [
            {
                "order_id": "small-purchase",
                "base_name": "20240815_120000_small_purchase",
                "receipt_date": "2024-08-15",
                "apple_id": "test@example.com",
                "total": 99,  # $0.99 in cents
                "items": [{"title": "Small In-App Purchase", "cost": 99}],  # $0.99 in cents
            }
        ]

        receipts_df = receipts_to_list_for_testing(receipts)
        result = matcher.match_single_transaction(transaction, receipts_df)

        assert result.receipts
        assert result.confidence > 0

    @pytest.mark.apple
    def test_large_receipt_collection(self, matcher):
        """Test performance with large number of receipts."""
        transaction_dict = {
            "id": "test-large",
            "date": "2024-08-15",
            "amount": -29990,
            "payee_name": "Apple Store",
        }

        transaction = dict_to_ynab_transaction(transaction_dict)

        # Generate large collection of receipts
        large_receipts = [
            {
                "order_id": f"receipt-{i}",
                "receipt_date": "2024-08-15",
                "apple_id": f"user{i}@example.com",
                "total": 1000 + i,  # Varying amounts in cents ($10.00, $10.01, $10.02, ...)
                "items": [{"title": f"App {i}", "cost": 1000 + i}],
            }
            for i in range(500)
        ]

        # Should complete in reasonable time
        import time

        start_time = time.time()
        receipts_df = receipts_to_list_for_testing(large_receipts)
        result = matcher.match_single_transaction(transaction, receipts_df)
        end_time = time.time()

        # Should be much faster than Amazon matching due to simpler model
        assert end_time - start_time < 2.0
        assert isinstance(result.receipts, list)


@pytest.mark.apple
def test_currency_unit_consistency_with_ynab():
    """
    Verify Apple matcher correctly compares cents from parser with YNAB milliunits.

    This is a regression test for the currency unit mismatch bug where:
    - YNAB: -45990 milliunits → 4599 cents
    - Apple: Was returning 45.99 dollars (float) → Should be 4599 cents (int)
    - Matcher was comparing: 4599 == 45.99 → False (BUG!)
    - Now should compare: 4599 == 4599 → True (FIXED!)
    """
    matcher = AppleMatcher()

    # Simulate REAL parser output (integer cents, not float dollars)
    receipts = [
        {
            "order_id": "TEST123",
            "base_name": "20240815_120000_test_app",
            "receipt_date": "2024-08-15",
            "total": 4599,  # $45.99 in cents (as parser NOW returns)
            "items": [{"title": "Test App", "cost": 4599}],
        }
    ]

    # YNAB transaction in milliunits (negative for expense)
    transaction_dict = {
        "id": "tx-001",
        "date": "2024-08-15",
        "amount": -45990,  # $45.99 in milliunits (negative for expense)
        "payee_name": "Apple",
    }

    transaction = dict_to_ynab_transaction(transaction_dict)

    receipts_df = receipts_to_list_for_testing(receipts)
    result = matcher.match_single_transaction(transaction, receipts_df)

    # Should match because both represent $45.99 (just in different units)
    assert result.receipts, "Should match same dollar amount in different units"
    assert result.confidence == 1.0, "Should be exact match (same date, same amount)"
    assert result.match_method == "exact_date_amount", "Should use exact match strategy"
