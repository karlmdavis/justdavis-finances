#!/usr/bin/env python3
"""Tests for Amazon split payment matcher module."""

import pytest
from unittest.mock import Mock, patch

# Add the parent directory to the path for imports
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from split_payment_matcher import SplitPaymentMatcher


class TestSplitPaymentMatcher:
    """Test cases for SplitPaymentMatcher functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.matcher = SplitPaymentMatcher()

        # Large order that gets split across payments
        self.large_order = {
            'order_id': '111-2223334-5556667',
            'order_date': '2024-08-15',
            'shipment_date': '2024-08-15',
            'total': 15000,  # $150.00 in cents
            'items': [
                {
                    'name': 'Expensive Item 1',
                    'quantity': 1,
                    'amount': 8000  # $80.00
                },
                {
                    'name': 'Expensive Item 2',
                    'quantity': 1,
                    'amount': 7000  # $70.00
                }
            ]
        }

        # First payment transaction
        self.payment_1 = {
            'id': 'trans-123',
            'date': '2024-08-15',
            'amount': -8000,  # -$80.00 in milliunits
            'payee_name': 'AMZN Mktp US*RT4Y12',
            'account_name': 'Chase Credit Card'
        }

        # Second payment transaction
        self.payment_2 = {
            'id': 'trans-124',
            'date': '2024-08-16',
            'amount': -7000,  # -$70.00 in milliunits
            'payee_name': 'AMZN Mktp US*RT4Y13',
            'account_name': 'Chase Credit Card'
        }

    def test_identify_partial_match(self):
        """Test identification of partial matches for split payments."""
        # First payment should partially match large order
        is_partial = self.matcher.is_potential_split_payment(
            self.payment_1,
            self.large_order
        )

        assert is_partial is True

        # Full amount match should not be partial
        full_payment = self.payment_1.copy()
        full_payment['amount'] = -15000  # Full order amount

        is_full = self.matcher.is_potential_split_payment(
            full_payment,
            self.large_order
        )

        assert is_full is False

    def test_track_split_payment_state(self):
        """Test tracking of split payment state across transactions."""
        # Process first payment
        result_1 = self.matcher.process_split_payment(
            self.payment_1,
            self.large_order,
            'karl'
        )

        # Should create partial match
        assert result_1['matched'] is True
        assert result_1['match_strategy'] == 'split_payment'
        assert result_1['confidence'] > 0.7

        # Check that state is tracked
        order_id = self.large_order['order_id']
        assert order_id in self.matcher.split_state

        state = self.matcher.split_state[order_id]
        assert state['remaining_amount'] == 7000  # $70.00 remaining
        assert len(state['matched_items']) == 1

        # Process second payment
        result_2 = self.matcher.process_split_payment(
            self.payment_2,
            self.large_order,
            'karl'
        )

        # Should complete the split payment
        assert result_2['matched'] is True
        assert result_2['confidence'] > 0.8

        # State should show order is complete
        assert state['remaining_amount'] == 0
        assert len(state['matched_items']) == 2

    def test_item_attribution_in_splits(self):
        """Test that items are correctly attributed to split payments."""
        # Process first payment
        result_1 = self.matcher.process_split_payment(
            self.payment_1,
            self.large_order,
            'karl'
        )

        # Should match the $80 item
        matched_items = result_1['amazon_orders'][0]['items']
        assert len(matched_items) == 1
        assert matched_items[0]['amount'] == 80.00  # $80 in dollars
        assert 'Expensive Item 1' in matched_items[0]['name']

        # Process second payment
        result_2 = self.matcher.process_split_payment(
            self.payment_2,
            self.large_order,
            'karl'
        )

        # Should match the $70 item
        matched_items_2 = result_2['amazon_orders'][0]['items']
        assert len(matched_items_2) == 1
        assert matched_items_2[0]['amount'] == 70.00  # $70 in dollars
        assert 'Expensive Item 2' in matched_items_2[0]['name']

    def test_multi_item_partial_payment(self):
        """Test split payment that partially covers multiple items."""
        # Order with many small items
        multi_item_order = {
            'order_id': '222-3334445-6667778',
            'order_date': '2024-08-20',
            'shipment_date': '2024-08-20',
            'total': 12000,  # $120.00
            'items': [
                {'name': 'Item A', 'quantity': 1, 'amount': 2000},  # $20
                {'name': 'Item B', 'quantity': 1, 'amount': 3000},  # $30
                {'name': 'Item C', 'quantity': 1, 'amount': 2500},  # $25
                {'name': 'Item D', 'quantity': 1, 'amount': 4500},  # $45
            ]
        }

        # Payment that covers first 3 items ($75)
        partial_payment = {
            'id': 'trans-200',
            'date': '2024-08-20',
            'amount': -7500,  # $75.00 in milliunits
            'payee_name': 'AMZN Mktp US*RT4Y20',
            'account_name': 'Chase Credit Card'
        }

        result = self.matcher.process_split_payment(
            partial_payment,
            multi_item_order,
            'karl'
        )

        # Should match first 3 items totaling $75
        assert result['matched'] is True
        matched_items = result['amazon_orders'][0]['items']
        assert len(matched_items) == 3

        # Check remaining state
        order_id = multi_item_order['order_id']
        state = self.matcher.split_state[order_id]
        assert state['remaining_amount'] == 4500  # $45 remaining
        assert len(state['matched_items']) == 3

    def test_overpayment_handling(self):
        """Test handling of payments that exceed remaining order amount."""
        # Start with partial payment
        self.matcher.process_split_payment(
            self.payment_1,  # $80 payment
            self.large_order,  # $150 total
            'karl'
        )

        # Create overpayment (more than remaining $70)
        overpayment = {
            'id': 'trans-300',
            'date': '2024-08-17',
            'amount': -9000,  # $90.00 (more than $70 remaining)
            'payee_name': 'AMZN Mktp US*RT4Y30',
            'account_name': 'Chase Credit Card'
        }

        result = self.matcher.process_split_payment(
            overpayment,
            self.large_order,
            'karl'
        )

        # Should still match but with lower confidence
        assert result['matched'] is True
        assert result['confidence'] < 0.8  # Lower confidence for overpayment

        # Should complete the order
        order_id = self.large_order['order_id']
        state = self.matcher.split_state[order_id]
        assert state['remaining_amount'] == 0

    def test_split_payment_confidence_scoring(self):
        """Test confidence scoring for split payments."""
        # Exact item match should have high confidence
        exact_result = self.matcher.process_split_payment(
            self.payment_1,  # Exactly $80
            self.large_order,
            'karl'
        )
        assert exact_result['confidence'] > 0.85

        # Approximate match should have lower confidence
        approximate_payment = self.payment_1.copy()
        approximate_payment['amount'] = -8200  # $82 vs $80 item

        approx_result = self.matcher.process_split_payment(
            approximate_payment,
            self.large_order,
            'karl'
        )
        assert approx_result['confidence'] < exact_result['confidence']

    def test_date_tolerance_in_splits(self):
        """Test date tolerance for split payments."""
        # Payment a few days after order should still match
        delayed_payment = self.payment_2.copy()
        delayed_payment['date'] = '2024-08-18'  # 3 days after order

        result = self.matcher.process_split_payment(
            delayed_payment,
            self.large_order,
            'karl'
        )

        # Should still match but with reduced confidence
        assert result['matched'] is True
        assert result['confidence'] > 0.6

    def test_split_state_persistence(self):
        """Test that split state persists across multiple transactions."""
        order_id = self.large_order['order_id']

        # Process first payment
        self.matcher.process_split_payment(
            self.payment_1,
            self.large_order,
            'karl'
        )

        # Verify state exists
        assert order_id in self.matcher.split_state

        # Simulate processing gap (new matcher instance would reload state)
        initial_state = self.matcher.split_state[order_id].copy()

        # Process second payment
        self.matcher.process_split_payment(
            self.payment_2,
            self.large_order,
            'karl'
        )

        # State should be updated, not reset
        final_state = self.matcher.split_state[order_id]
        assert final_state['remaining_amount'] == 0
        assert len(final_state['matched_items']) == 2

    def test_multiple_order_split_tracking(self):
        """Test tracking splits for multiple orders simultaneously."""
        # Second large order
        large_order_2 = {
            'order_id': '333-4445556-7778889',
            'order_date': '2024-08-20',
            'shipment_date': '2024-08-20',
            'total': 10000,  # $100.00
            'items': [
                {'name': 'Order 2 Item 1', 'quantity': 1, 'amount': 6000},
                {'name': 'Order 2 Item 2', 'quantity': 1, 'amount': 4000}
            ]
        }

        payment_2a = {
            'id': 'trans-400',
            'date': '2024-08-20',
            'amount': -6000,  # First item from order 2
            'payee_name': 'AMZN Mktp US*RT4Y40',
            'account_name': 'Chase Credit Card'
        }

        # Process payments for both orders
        result_1a = self.matcher.process_split_payment(
            self.payment_1,  # Order 1
            self.large_order,
            'karl'
        )

        result_2a = self.matcher.process_split_payment(
            payment_2a,  # Order 2
            large_order_2,
            'karl'
        )

        # Both should be tracked separately
        assert len(self.matcher.split_state) == 2
        assert self.large_order['order_id'] in self.matcher.split_state
        assert large_order_2['order_id'] in self.matcher.split_state

        # States should be independent
        state_1 = self.matcher.split_state[self.large_order['order_id']]
        state_2 = self.matcher.split_state[large_order_2['order_id']]

        assert state_1['remaining_amount'] == 7000  # $70 remaining
        assert state_2['remaining_amount'] == 4000  # $40 remaining

    def test_reset_split_state(self):
        """Test resetting split state for completed orders."""
        # Process full split payment sequence
        self.matcher.process_split_payment(
            self.payment_1,
            self.large_order,
            'karl'
        )

        self.matcher.process_split_payment(
            self.payment_2,
            self.large_order,
            'karl'
        )

        # Order should be complete
        order_id = self.large_order['order_id']
        state = self.matcher.split_state[order_id]
        assert state['remaining_amount'] == 0

        # Reset state for new matching session
        self.matcher.reset_split_state()
        assert len(self.matcher.split_state) == 0

    def test_edge_case_zero_amount_items(self):
        """Test split payment handling with zero-amount items."""
        order_with_free_item = {
            'order_id': '444-5556667-8889990',
            'order_date': '2024-08-25',
            'shipment_date': '2024-08-25',
            'total': 5000,  # $50.00
            'items': [
                {'name': 'Paid Item', 'quantity': 1, 'amount': 5000},
                {'name': 'Free Item', 'quantity': 1, 'amount': 0}
            ]
        }

        payment = {
            'id': 'trans-500',
            'date': '2024-08-25',
            'amount': -5000,  # $50.00
            'payee_name': 'AMZN Mktp US*RT4Y50',
            'account_name': 'Chase Credit Card'
        }

        result = self.matcher.process_split_payment(
            payment,
            order_with_free_item,
            'karl'
        )

        # Should match perfectly and include free item
        assert result['matched'] is True
        assert result['confidence'] > 0.9

        matched_items = result['amazon_orders'][0]['items']
        assert len(matched_items) == 2  # Both paid and free items

        item_names = [item['name'] for item in matched_items]
        assert 'Paid Item' in item_names
        assert 'Free Item' in item_names


if __name__ == '__main__':
    pytest.main([__file__])