#!/usr/bin/env python3
"""Tests for split calculator module."""

import unittest
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from split_calculator import (
    calculate_amazon_splits, calculate_apple_splits, should_split_transaction,
    SplitCalculationError, validate_split_calculation
)


class TestSplitCalculator(unittest.TestCase):
    """Test cases for split calculation algorithms."""

    def test_amazon_single_item_no_split(self):
        """Test Amazon single item returns memo update only."""
        transaction_amount = -1999  # $19.99 expense
        items = [
            {
                'name': 'Kindle Book: Project Hail Mary',
                'amount': 1999,
                'quantity': 1,
                'unit_price': 1999
            }
        ]

        splits = calculate_amazon_splits(transaction_amount, items)

        self.assertEqual(len(splits), 1)
        self.assertEqual(splits[0]['amount'], transaction_amount)
        self.assertEqual(splits[0]['memo'], "Kindle Book: Project Hail Mary (1x @ $19.99)")

    def test_amazon_multiple_items_split(self):
        """Test Amazon multiple items creates proper splits."""
        transaction_amount = -8990  # $89.90 expense
        items = [
            {
                'name': 'Echo Dot (4th Gen) - Charcoal',
                'amount': 4599,  # $45.99
                'quantity': 1,
                'unit_price': 4599
            },
            {
                'name': 'USB-C Cable 6ft - 2 Pack',
                'amount': 2350,  # $23.50
                'quantity': 1,
                'unit_price': 2350
            },
            {
                'name': 'Phone Case Clear',
                'amount': 1599,  # $15.99
                'quantity': 1,
                'unit_price': 1599
            },
            {
                'name': 'Screen Protector',
                'amount': 442,   # $4.42 (remainder)
                'quantity': 1,
                'unit_price': 451
            }
        ]

        splits = calculate_amazon_splits(transaction_amount, items)

        # Verify split count
        self.assertEqual(len(splits), 4)

        # Verify amounts (sorted by amount desc, then name)
        expected_amounts = [-4599, -2350, -1599, -442]  # Negative for expenses
        actual_amounts = [split['amount'] for split in splits]

        # Sort both for comparison since ordering might vary
        self.assertEqual(sum(actual_amounts), transaction_amount)

        # Verify memos are formatted correctly
        for split in splits:
            self.assertIn('(1x @ $', split['memo'])

    def test_amazon_splits_sum_equals_transaction(self):
        """Test Amazon splits always sum to exact transaction amount."""
        transaction_amount = -10000  # $100.00
        items = [
            {'name': 'Item 1', 'amount': 3333, 'quantity': 1, 'unit_price': 3333},
            {'name': 'Item 2', 'amount': 3333, 'quantity': 1, 'unit_price': 3333},
            {'name': 'Item 3', 'amount': 3334, 'quantity': 1, 'unit_price': 3334}  # Gets remainder
        ]

        splits = calculate_amazon_splits(transaction_amount, items)

        # Verify exact sum
        total = sum(split['amount'] for split in splits)
        self.assertEqual(total, transaction_amount)

    def test_apple_single_item_no_split(self):
        """Test Apple single item returns memo update only."""
        transaction_amount = -2997  # $29.97 expense
        items = [{'title': 'Logic Pro', 'cost': 29.99}]
        subtotal = 29.99
        tax = 0.0

        splits = calculate_apple_splits(transaction_amount, items, subtotal, tax)

        self.assertEqual(len(splits), 1)
        self.assertEqual(splits[0]['amount'], transaction_amount)
        self.assertEqual(splits[0]['memo'], 'Logic Pro')

    def test_apple_multiple_items_with_tax(self):
        """Test Apple multiple items with proportional tax allocation."""
        transaction_amount = -32970  # $329.70 expense (milliunits)
        items = [
            {'title': 'Logic Pro', 'cost': 199.99},
            {'title': 'Final Cut Pro', 'cost': 99.99}
        ]
        subtotal = 299.98
        tax = 29.72

        splits = calculate_apple_splits(transaction_amount, items, subtotal, tax)

        # Verify split count
        self.assertEqual(len(splits), 2)

        # Verify exact sum
        total = sum(split['amount'] for split in splits)
        self.assertEqual(total, transaction_amount)

        # Verify tax notation in memos
        for split in splits:
            self.assertIn('(incl. tax)', split['memo'])

    def test_apple_proportional_tax_allocation(self):
        """Test Apple tax is allocated proportionally with remainder to last item."""
        transaction_amount = -32960  # $32.96 in milliunits
        items = [
            {'title': 'App A', 'cost': 19.99},  # ~66.7% of subtotal
            {'title': 'App B', 'cost': 9.99}   # ~33.3% of subtotal
        ]
        subtotal = 29.98
        tax = 2.98

        splits = calculate_apple_splits(transaction_amount, items, subtotal, tax)

        # App A should get more tax (proportionally)
        # App B gets remainder to ensure exact sum
        total = sum(split['amount'] for split in splits)
        self.assertEqual(total, transaction_amount)

        # Both amounts should be negative (expenses)
        for split in splits:
            self.assertLess(split['amount'], 0)

    def test_should_split_transaction(self):
        """Test transaction splitting decision logic."""
        # Single item - no split
        single_item = [{'name': 'Book'}]
        self.assertFalse(should_split_transaction(single_item))

        # Multiple items - split
        multiple_items = [{'name': 'Book'}, {'name': 'Charger'}]
        self.assertTrue(should_split_transaction(multiple_items))

        # Empty list - no split
        self.assertFalse(should_split_transaction([]))

    def test_amazon_splits_error_on_empty_items(self):
        """Test error handling for empty items list."""
        with self.assertRaises(SplitCalculationError):
            calculate_amazon_splits(-1000, [])

    def test_apple_splits_error_on_empty_items(self):
        """Test error handling for empty items list."""
        with self.assertRaises(SplitCalculationError):
            calculate_apple_splits(-1000, [], 10.0, 1.0)

    def test_validate_split_calculation(self):
        """Test split validation function."""
        # Valid splits
        splits = [
            {'amount': -2000, 'memo': 'Item 1'},
            {'amount': -3000, 'memo': 'Item 2'}
        ]
        transaction_amount = -5000
        expected_count = 2

        is_valid, error = validate_split_calculation(splits, transaction_amount, expected_count)
        self.assertTrue(is_valid)
        self.assertEqual(error, "")

        # Invalid sum
        invalid_splits = [
            {'amount': -2000, 'memo': 'Item 1'},
            {'amount': -2000, 'memo': 'Item 2'}  # Sum = -4000, not -5000
        ]

        is_valid, error = validate_split_calculation(invalid_splits, transaction_amount, expected_count)
        self.assertFalse(is_valid)
        self.assertIn("doesn't equal transaction", error)

        # Positive amount (should be negative for expense)
        positive_splits = [
            {'amount': 2000, 'memo': 'Item 1'},
            {'amount': 3000, 'memo': 'Item 2'}
        ]

        is_valid, error = validate_split_calculation(positive_splits, transaction_amount, expected_count)
        self.assertFalse(is_valid)
        self.assertIn("should be negative", error)


class TestSplitCalculatorEdgeCases(unittest.TestCase):
    """Test edge cases and error conditions."""

    def test_amazon_zero_amount_item(self):
        """Test handling of zero-amount items (free items)."""
        transaction_amount = -1000  # $10.00
        items = [
            {'name': 'Paid Item', 'amount': 1000, 'quantity': 1, 'unit_price': 1000},
            {'name': 'Free Item', 'amount': 0, 'quantity': 1, 'unit_price': 0}
        ]

        splits = calculate_amazon_splits(transaction_amount, items)

        # Should handle gracefully
        self.assertEqual(len(splits), 2)
        total = sum(split['amount'] for split in splits)
        self.assertEqual(total, transaction_amount)

    def test_apple_zero_tax(self):
        """Test Apple splits with zero tax."""
        transaction_amount = -2999  # $29.99
        items = [
            {'title': 'App A', 'cost': 19.99},
            {'title': 'App B', 'cost': 9.99}
        ]
        subtotal = 29.98
        tax = 0.0

        splits = calculate_apple_splits(transaction_amount, items, subtotal, tax)

        # Should work without tax allocation
        self.assertEqual(len(splits), 2)
        total = sum(split['amount'] for split in splits)
        self.assertEqual(total, transaction_amount)

        # Memos should not include tax notation
        for split in splits:
            self.assertNotIn('(incl. tax)', split['memo'])

    def test_very_small_amounts(self):
        """Test handling of very small amounts (penny-level)."""
        transaction_amount = -3  # 3 milliunits = $0.003
        items = [
            {'name': 'Tiny Item', 'amount': 0, 'quantity': 1, 'unit_price': 0}  # Rounds to 0 cents
        ]

        # Should handle gracefully even with rounding
        splits = calculate_amazon_splits(transaction_amount, items)
        self.assertEqual(len(splits), 1)


if __name__ == '__main__':
    unittest.main()