#!/usr/bin/env python3
"""Tests for Apple transaction matcher module."""

import pytest
from datetime import datetime, timedelta

# Add the parent directory to the path for imports
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from apple_matcher import AppleMatcher


class TestAppleMatcher:
    """Test cases for AppleMatcher functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        # Sample Apple receipts
        self.sample_receipts = [
            {
                'order_id': 'ML7PQ2XYZ',
                'receipt_date': '2024-08-15',
                'apple_id': '***REMOVED***',
                'subtotal': 29.99,
                'tax': 2.98,
                'total': 32.97,
                'items': [
                    {
                        'title': 'Logic Pro',
                        'cost': 199.99
                    }
                ]
            },
            {
                'order_id': 'ABCDEF123',
                'receipt_date': '2024-08-16',
                'apple_id': 'erica_apple@***REMOVED***',
                'subtotal': 19.98,
                'tax': 1.98,
                'total': 21.96,
                'items': [
                    {
                        'title': 'TestFlight',
                        'cost': 0.00
                    },
                    {
                        'title': 'Productivity App',
                        'cost': 4.99
                    },
                    {
                        'title': 'Game Add-on',
                        'cost': 14.99
                    }
                ]
            }
        ]

        # Sample YNAB transactions
        self.sample_transactions = [
            {
                'id': 'ynab-trans-1',
                'date': '2024-08-15',
                'amount': -32970,  # -$32.97 in milliunits
                'payee_name': 'APPLE.COM/BILL',
                'account_name': 'Apple Card',
                'memo': '',
                'category_name': 'Software'
            },
            {
                'id': 'ynab-trans-2',
                'date': '2024-08-17',  # 1 day after receipt
                'amount': -21960,  # -$21.96 in milliunits
                'payee_name': 'Apple Services',
                'account_name': 'Chase Credit Card',
                'memo': '',
                'category_name': 'Entertainment'
            },
            {
                'id': 'ynab-trans-3',
                'date': '2024-08-20',
                'amount': -9990,  # -$9.99 - no matching receipt
                'payee_name': 'APPLE.COM/BILL',
                'account_name': 'Apple Card',
                'memo': '',
                'category_name': 'Software'
            }
        ]

        self.matcher = AppleMatcher(date_window_days=2)

        # Convert receipts to DataFrame as expected by the actual interface
        import pandas as pd
        self.receipts_df = pd.DataFrame(self.sample_receipts)

    def test_exact_date_amount_match(self):
        """Test exact match on same date with exact amount."""
        transaction = self.sample_transactions[0]  # 2024-08-15, $32.97
        receipt = self.sample_receipts[0]  # 2024-08-15, $32.97

        match_result = self.matcher.match_transaction_to_receipt(transaction, receipt)

        assert match_result is not None
        assert match_result['confidence'] == 1.0
        assert match_result['strategy'] == 'exact_match'
        assert match_result['date_difference'] == 0

    def test_date_window_match(self):
        """Test matching within date window with exact amount."""
        transaction = self.sample_transactions[1]  # 2024-08-17, $21.96
        receipt = self.sample_receipts[1]  # 2024-08-16, $21.96 (1 day difference)

        match_result = self.matcher.match_transaction_to_receipt(transaction, receipt)

        assert match_result is not None
        assert 0.85 <= match_result['confidence'] <= 0.95  # High confidence for 1-day difference
        assert match_result['strategy'] == 'date_window_match'
        assert match_result['date_difference'] == 1

    def test_amount_mismatch_rejection(self):
        """Test that transactions with mismatched amounts are rejected."""
        transaction = self.sample_transactions[2]  # $9.99
        receipt = self.sample_receipts[0]  # $32.97

        match_result = self.matcher.match_transaction_to_receipt(transaction, receipt)

        assert match_result is None  # No match due to amount mismatch

    def test_date_window_boundary(self):
        """Test date window boundaries."""
        # Create transaction 3 days after receipt (should still match with lower confidence)
        transaction_3_days = self.sample_transactions[1].copy()
        transaction_3_days['date'] = '2024-08-19'  # 3 days after receipt date

        receipt = self.sample_receipts[1]  # 2024-08-16

        match_result = self.matcher.match_transaction_to_receipt(transaction_3_days, receipt)

        assert match_result is not None
        assert match_result['confidence'] < 0.85  # Lower confidence for 3-day difference
        assert match_result['date_difference'] == 3

        # Test beyond window (should not match)
        transaction_too_far = self.sample_transactions[1].copy()
        transaction_too_far['date'] = '2024-08-26'  # 10 days after receipt

        no_match = self.matcher.match_transaction_to_receipt(transaction_too_far, receipt)
        assert no_match is None

    def test_milliunits_to_dollars_conversion(self):
        """Test conversion from YNAB milliunits to dollars."""
        assert self.matcher.milliunits_to_dollars(-32970) == 32.97
        assert self.matcher.milliunits_to_dollars(-1000) == 1.00
        assert self.matcher.milliunits_to_dollars(-99) == 0.099
        assert self.matcher.milliunits_to_dollars(0) == 0.00

        # Positive amounts (refunds)
        assert self.matcher.milliunits_to_dollars(32970) == 32.97

    def test_date_difference_calculation(self):
        """Test date difference calculation."""
        # Same date
        assert self.matcher.calculate_date_difference('2024-08-15', '2024-08-15') == 0

        # Transaction after receipt (positive difference)
        assert self.matcher.calculate_date_difference('2024-08-17', '2024-08-15') == 2

        # Transaction before receipt (negative difference, but absolute value)
        assert self.matcher.calculate_date_difference('2024-08-13', '2024-08-15') == 2

    def test_confidence_scoring_by_date_difference(self):
        """Test confidence scoring based on date differences."""
        transaction = self.sample_transactions[0].copy()
        receipt = self.sample_receipts[0].copy()

        # Same date should give confidence 1.0
        transaction['date'] = '2024-08-15'
        receipt['receipt_date'] = '2024-08-15'
        match_0_days = self.matcher.match_transaction_to_receipt(transaction, receipt)
        assert match_0_days['confidence'] == 1.0

        # 1 day difference should give high confidence
        transaction['date'] = '2024-08-16'
        match_1_day = self.matcher.match_transaction_to_receipt(transaction, receipt)
        assert 0.85 <= match_1_day['confidence'] <= 0.95

        # 2 day difference should give lower confidence
        transaction['date'] = '2024-08-17'
        match_2_days = self.matcher.match_transaction_to_receipt(transaction, receipt)
        assert 0.75 <= match_2_days['confidence'] <= 0.85

        # Confidence should decrease with larger differences
        assert match_0_days['confidence'] > match_1_day['confidence']
        assert match_1_day['confidence'] > match_2_days['confidence']

    def test_multi_apple_id_support(self):
        """Test handling of multiple Apple IDs."""
        # Should find receipts for both karl and erica
        karl_receipts = [r for r in self.sample_receipts if 'karl' in r['apple_id']]
        erica_receipts = [r for r in self.sample_receipts if 'erica' in r['apple_id']]

        assert len(karl_receipts) == 1
        assert len(erica_receipts) == 1

        # Matching should work regardless of Apple ID
        karl_transaction = self.sample_transactions[0]
        karl_receipt = karl_receipts[0]

        match_result = self.matcher.match_transaction_to_receipt(karl_transaction, karl_receipt)
        assert match_result is not None
        assert match_result['apple_id'] == '***REMOVED***'

    def test_zero_cost_items_handling(self):
        """Test handling of zero-cost items (free apps)."""
        receipt_with_free = self.sample_receipts[1]  # Has TestFlight with $0.00 cost

        # Verify free item is included in receipt
        free_items = [item for item in receipt_with_free['items'] if item['cost'] == 0.00]
        assert len(free_items) == 1
        assert free_items[0]['title'] == 'TestFlight'

        # Transaction should still match total correctly
        transaction = self.sample_transactions[1]
        match_result = self.matcher.match_transaction_to_receipt(transaction, receipt_with_free)

        assert match_result is not None
        # Should preserve all items including free ones
        assert len(match_result['receipt']['items']) == 3

    def test_find_best_match_for_transaction(self):
        """Test finding the best receipt match for a transaction."""
        transaction = self.sample_transactions[0]  # Should match first receipt exactly

        best_match = self.matcher.find_best_match_for_transaction(transaction)

        assert best_match is not None
        assert best_match['confidence'] == 1.0
        assert best_match['receipt']['order_id'] == 'ML7PQ2XYZ'

    def test_no_match_scenario(self):
        """Test transaction with no matching receipts."""
        unmatched_transaction = self.sample_transactions[2]  # $9.99 with no matching receipt

        best_match = self.matcher.find_best_match_for_transaction(unmatched_transaction)

        assert best_match is None

    def test_multiple_potential_matches(self):
        """Test scenario where multiple receipts could potentially match."""
        # Create duplicate receipt with same amount but different date
        duplicate_receipt = self.sample_receipts[0].copy()
        duplicate_receipt['receipt_date'] = '2024-08-17'  # 2 days later
        duplicate_receipt['order_id'] = 'DUPLICATE123'

        matcher_with_duplicate = AppleMatcher(
            receipts=self.sample_receipts + [duplicate_receipt],
            transactions=self.sample_transactions
        )

        transaction = self.sample_transactions[0]  # 2024-08-15
        best_match = matcher_with_duplicate.find_best_match_for_transaction(transaction)

        # Should choose the exact date match over the 2-day difference
        assert best_match is not None
        assert best_match['confidence'] == 1.0
        assert best_match['receipt']['order_id'] == 'ML7PQ2XYZ'  # Original, not duplicate

    def test_tax_allocation_preservation(self):
        """Test that tax information is preserved in match results."""
        transaction = self.sample_transactions[0]
        receipt = self.sample_receipts[0]

        match_result = self.matcher.match_transaction_to_receipt(transaction, receipt)

        assert match_result is not None
        assert match_result['receipt']['subtotal'] == 29.99
        assert match_result['receipt']['tax'] == 2.98
        assert match_result['receipt']['total'] == 32.97

    def test_item_details_preservation(self):
        """Test that item details are preserved in match results."""
        transaction = self.sample_transactions[1]
        receipt = self.sample_receipts[1]  # Multi-item receipt

        match_result = self.matcher.match_transaction_to_receipt(transaction, receipt)

        assert match_result is not None
        items = match_result['receipt']['items']
        assert len(items) == 3

        # Check item details
        item_titles = [item['title'] for item in items]
        assert 'TestFlight' in item_titles
        assert 'Productivity App' in item_titles
        assert 'Game Add-on' in item_titles

        item_costs = [item['cost'] for item in items]
        assert 0.00 in item_costs
        assert 4.99 in item_costs
        assert 14.99 in item_costs

    def test_edge_case_same_day_different_amounts(self):
        """Test handling of multiple transactions on same day with different amounts."""
        # Create another transaction on same day but different amount
        same_day_transaction = {
            'id': 'ynab-trans-same-day',
            'date': '2024-08-15',
            'amount': -19990,  # Different amount
            'payee_name': 'APPLE.COM/BILL',
            'account_name': 'Apple Card',
            'memo': '',
            'category_name': 'Software'
        }

        # First transaction should still match first receipt
        match_1 = self.matcher.match_transaction_to_receipt(
            self.sample_transactions[0],
            self.sample_receipts[0]
        )
        assert match_1 is not None
        assert match_1['confidence'] == 1.0

        # Same-day transaction with different amount should not match
        match_2 = self.matcher.match_transaction_to_receipt(
            same_day_transaction,
            self.sample_receipts[0]
        )
        assert match_2 is None

    def test_confidence_threshold_filtering(self):
        """Test filtering matches by confidence threshold."""
        # Create matcher with higher confidence threshold
        strict_matcher = AppleMatcher(
            receipts=self.sample_receipts,
            transactions=self.sample_transactions,
            min_confidence=0.90
        )

        # Exact match should pass threshold
        exact_transaction = self.sample_transactions[0]
        best_match = strict_matcher.find_best_match_for_transaction(exact_transaction)
        assert best_match is not None

        # Date window match might not pass strict threshold
        window_transaction = self.sample_transactions[1].copy()
        window_transaction['date'] = '2024-08-19'  # 3 days after receipt

        window_match = strict_matcher.find_best_match_for_transaction(window_transaction)
        # Might be None if confidence is below 0.90

    def test_receipt_date_formats(self):
        """Test handling of different receipt date formats."""
        # Test with various date string formats
        receipt_alt_format = self.sample_receipts[0].copy()
        receipt_alt_format['receipt_date'] = '2024-08-15'  # ISO format

        transaction = self.sample_transactions[0]
        transaction['date'] = '2024-08-15'

        match_result = self.matcher.match_transaction_to_receipt(transaction, receipt_alt_format)
        assert match_result is not None
        assert match_result['date_difference'] == 0


if __name__ == '__main__':
    pytest.main([__file__])