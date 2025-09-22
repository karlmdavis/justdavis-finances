#!/usr/bin/env python3
"""Tests for Amazon match scorer module."""

import pytest
from datetime import datetime, date

# Add the parent directory to the path for imports
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from match_scorer import MatchScorer, MatchType, ConfidenceThresholds
from match_single_transaction import milliunits_to_cents


class TestMatchScorer:
    """Test cases for MatchScorer functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        # Sample YNAB transaction
        self.sample_transaction = {
            'id': 'trans-123',
            'date': '2024-08-15',
            'amount': -45990,  # -$45.99 in milliunits
            'payee_name': 'AMZN Mktp US*RT4Y12',
            'account_name': 'Chase Credit Card'
        }

        # Sample Amazon order group data
        self.sample_order_group = {
            'order_id': '111-2223334-5556667',
            'order_date': '2024-08-15',
            'ship_date': '2024-08-15',
            'total': 4599,  # $45.99 in cents
            'items': [
                {
                    'name': 'Echo Dot (4th Gen)',
                    'quantity': 1,
                    'amount': 4599
                }
            ]
        }

    def test_exact_match_scoring(self):
        """Test scoring for exact date and amount matches."""
        ynab_amount = milliunits_to_cents(self.sample_transaction['amount'])
        ynab_date = datetime.strptime(self.sample_transaction['date'], '%Y-%m-%d').date()
        amazon_ship_dates = [self.sample_order_group['ship_date']]

        confidence = MatchScorer.calculate_confidence(
            ynab_amount=ynab_amount,
            amazon_total=self.sample_order_group['total'],
            ynab_date=ynab_date,
            amazon_ship_dates=amazon_ship_dates,
            match_type=MatchType.COMPLETE_ORDER
        )

        assert confidence >= 0.95
        assert confidence <= 1.0

    def test_date_difference_scoring(self):
        """Test confidence reduction for date differences."""
        ynab_amount = milliunits_to_cents(self.sample_transaction['amount'])
        ynab_date = datetime.strptime(self.sample_transaction['date'], '%Y-%m-%d').date()

        # Order 1 day later
        ship_dates_1_day = ['2024-08-16']
        confidence_1_day = MatchScorer.calculate_confidence(
            ynab_amount=ynab_amount,
            amazon_total=self.sample_order_group['total'],
            ynab_date=ynab_date,
            amazon_ship_dates=ship_dates_1_day,
            match_type=MatchType.COMPLETE_ORDER
        )

        # Order 3 days later
        ship_dates_3_days = ['2024-08-18']
        confidence_3_days = MatchScorer.calculate_confidence(
            ynab_amount=ynab_amount,
            amazon_total=self.sample_order_group['total'],
            ynab_date=ynab_date,
            amazon_ship_dates=ship_dates_3_days,
            match_type=MatchType.COMPLETE_ORDER
        )

        # Confidence should decrease with larger date differences
        assert confidence_1_day > confidence_3_days

    def test_amount_difference_scoring(self):
        """Test that non-exact amounts get zero confidence."""
        ynab_amount = milliunits_to_cents(self.sample_transaction['amount'])
        ynab_date = datetime.strptime(self.sample_transaction['date'], '%Y-%m-%d').date()
        amazon_ship_dates = [self.sample_order_group['ship_date']]

        # Different amount should get 0 confidence (exact matches only)
        different_total = 4699  # $46.99 vs $45.99
        confidence_diff = MatchScorer.calculate_confidence(
            ynab_amount=ynab_amount,
            amazon_total=different_total,
            ynab_date=ynab_date,
            amazon_ship_dates=amazon_ship_dates,
            match_type=MatchType.COMPLETE_ORDER
        )

        # Non-exact amounts should get zero confidence
        assert confidence_diff == 0.0

    def test_match_type_confidence_differences(self):
        """Test that different match types have appropriate confidence adjustments."""
        ynab_amount = milliunits_to_cents(self.sample_transaction['amount'])
        ynab_date = datetime.strptime(self.sample_transaction['date'], '%Y-%m-%d').date()
        amazon_ship_dates = [self.sample_order_group['ship_date']]

        # Complete order match
        complete_confidence = MatchScorer.calculate_confidence(
            ynab_amount=ynab_amount,
            amazon_total=self.sample_order_group['total'],
            ynab_date=ynab_date,
            amazon_ship_dates=amazon_ship_dates,
            match_type=MatchType.COMPLETE_ORDER
        )

        # Split payment match
        split_confidence = MatchScorer.calculate_confidence(
            ynab_amount=ynab_amount,
            amazon_total=self.sample_order_group['total'],
            ynab_date=ynab_date,
            amazon_ship_dates=amazon_ship_dates,
            match_type=MatchType.SPLIT_PAYMENT
        )

        # Complete orders should have slightly higher confidence than split payments
        assert complete_confidence > split_confidence

    def test_milliunits_to_cents_conversion(self):
        """Test conversion from YNAB milliunits to cents."""
        assert milliunits_to_cents(-45990) == 4599  # $45.99
        assert milliunits_to_cents(-1000) == 100    # $1.00
        assert milliunits_to_cents(-99) == 10       # $0.099 -> 10 cents (floor division)
        assert milliunits_to_cents(0) == 0          # $0.00

        # Positive amounts (income/refunds)
        assert milliunits_to_cents(45990) == 4599

    def test_create_match_result(self):
        """Test creation of complete match result structure."""
        result = MatchScorer.create_match_result(
            ynab_tx=self.sample_transaction,
            amazon_orders=[self.sample_order_group],
            match_method='complete_match',
            confidence=0.95,
            account='karl'
        )

        # Verify structure
        assert 'account' in result
        assert 'amazon_orders' in result
        assert 'match_method' in result
        assert 'confidence' in result
        assert 'total_match_amount' in result
        assert 'unmatched_amount' in result

        # Verify values
        assert result['account'] == 'karl'
        assert result['confidence'] == 0.95
        assert result['match_method'] == 'complete_match'
        assert len(result['amazon_orders']) == 1
        assert result['total_match_amount'] == 4599
        assert result['unmatched_amount'] == 0

    def test_multi_order_match_result(self):
        """Test match result with multiple Amazon orders."""
        order_2 = {
            'order_id': '222-3334445-6667778',
            'order_date': '2024-08-15',
            'ship_date': '2024-08-16',
            'total': 2199,  # $21.99
            'items': [
                {
                    'name': 'USB Cable',
                    'quantity': 1,
                    'amount': 2199
                }
            ]
        }

        result = MatchScorer.create_match_result(
            ynab_tx=self.sample_transaction,
            amazon_orders=[self.sample_order_group, order_2],
            match_method='split_payment',
            confidence=0.85,
            account='karl'
        )

        assert len(result['amazon_orders']) == 2
        assert result['confidence'] == 0.85
        assert result['match_method'] == 'split_payment'
        assert result['total_match_amount'] == 6798  # 4599 + 2199

    def test_confidence_thresholds(self):
        """Test confidence threshold checking."""
        # Test with high confidence
        assert ConfidenceThresholds.meets_threshold(0.80, MatchType.COMPLETE_ORDER) is True
        assert ConfidenceThresholds.meets_threshold(0.70, MatchType.SPLIT_PAYMENT) is True

        # Test with low confidence
        assert ConfidenceThresholds.meets_threshold(0.70, MatchType.COMPLETE_ORDER) is False
        assert ConfidenceThresholds.meets_threshold(0.60, MatchType.SPLIT_PAYMENT) is False

    def test_multi_day_order_adjustment(self):
        """Test confidence adjustment for multi-day orders."""
        ynab_amount = milliunits_to_cents(self.sample_transaction['amount'])
        ynab_date = datetime.strptime(self.sample_transaction['date'], '%Y-%m-%d').date()
        amazon_ship_dates = [self.sample_order_group['ship_date']]

        # Multi-day order gets slight boost
        confidence_multi_day = MatchScorer.calculate_confidence(
            ynab_amount=ynab_amount,
            amazon_total=self.sample_order_group['total'],
            ynab_date=ynab_date,
            amazon_ship_dates=amazon_ship_dates,
            match_type=MatchType.COMPLETE_ORDER,
            multi_day=True
        )

        # Single day order
        confidence_single_day = MatchScorer.calculate_confidence(
            ynab_amount=ynab_amount,
            amazon_total=self.sample_order_group['total'],
            ynab_date=ynab_date,
            amazon_ship_dates=amazon_ship_dates,
            match_type=MatchType.COMPLETE_ORDER,
            multi_day=False
        )

        # Multi-day orders should get slight boost
        assert confidence_multi_day >= confidence_single_day

    def test_large_date_difference_penalty(self):
        """Test steep penalty for large date differences."""
        ynab_amount = milliunits_to_cents(self.sample_transaction['amount'])
        ynab_date = datetime.strptime(self.sample_transaction['date'], '%Y-%m-%d').date()

        # Order 10 days later (should have very low confidence)
        ship_dates_large_diff = ['2024-08-25']
        confidence_large_diff = MatchScorer.calculate_confidence(
            ynab_amount=ynab_amount,
            amazon_total=self.sample_order_group['total'],
            ynab_date=ynab_date,
            amazon_ship_dates=ship_dates_large_diff,
            match_type=MatchType.COMPLETE_ORDER
        )

        # Large date differences should have very low confidence
        assert confidence_large_diff <= 0.5


if __name__ == '__main__':
    pytest.main([__file__])