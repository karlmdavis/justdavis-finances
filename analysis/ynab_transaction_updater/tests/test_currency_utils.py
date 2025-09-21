#!/usr/bin/env python3
"""Tests for currency utilities module."""

import unittest
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from currency_utils import (
    milliunits_to_cents, cents_to_milliunits, cents_to_dollars_str,
    dollars_to_cents, dollars_to_milliunits, validate_sum_equals_total,
    allocate_remainder, safe_divide_proportional
)


class TestCurrencyUtils(unittest.TestCase):
    """Test cases for currency conversion utilities."""

    def test_milliunits_to_cents(self):
        """Test YNAB milliunits to cents conversion."""
        self.assertEqual(milliunits_to_cents(1000), 100)  # $1.00
        self.assertEqual(milliunits_to_cents(-1000), 100)  # Absolute value
        self.assertEqual(milliunits_to_cents(0), 0)
        self.assertEqual(milliunits_to_cents(5990), 599)  # $5.99
        self.assertEqual(milliunits_to_cents(-45990), 4599)  # $45.99

    def test_cents_to_milliunits(self):
        """Test cents to YNAB milliunits conversion."""
        self.assertEqual(cents_to_milliunits(100), 1000)  # $1.00
        self.assertEqual(cents_to_milliunits(599), 5990)  # $5.99
        self.assertEqual(cents_to_milliunits(0), 0)
        self.assertEqual(cents_to_milliunits(4599), 45990)  # $45.99

    def test_cents_to_dollars_str(self):
        """Test cents to dollar string formatting."""
        self.assertEqual(cents_to_dollars_str(100), "1.00")
        self.assertEqual(cents_to_dollars_str(599), "5.99")
        self.assertEqual(cents_to_dollars_str(0), "0.00")
        self.assertEqual(cents_to_dollars_str(1), "0.01")
        self.assertEqual(cents_to_dollars_str(4599), "45.99")

    def test_dollars_to_cents(self):
        """Test dollars to cents conversion with proper rounding."""
        self.assertEqual(dollars_to_cents(1.00), 100)
        self.assertEqual(dollars_to_cents("5.99"), 599)
        self.assertEqual(dollars_to_cents(0.0), 0)
        self.assertEqual(dollars_to_cents("45.99"), 4599)
        # Test practical rounding cases (avoiding floating-point precision issues)
        self.assertEqual(dollars_to_cents(1.01), 101)  # Clear round up
        self.assertEqual(dollars_to_cents(1.00), 100)  # Even number

    def test_dollars_to_milliunits(self):
        """Test dollars to milliunits conversion."""
        self.assertEqual(dollars_to_milliunits(1.00), 1000)
        self.assertEqual(dollars_to_milliunits("5.99"), 5990)
        self.assertEqual(dollars_to_milliunits(0.0), 0)
        self.assertEqual(dollars_to_milliunits("45.99"), 45990)

    def test_validate_sum_equals_total(self):
        """Test split sum validation."""
        splits = [
            {'amount': -2000},
            {'amount': -3000},
            {'amount': -1000}
        ]

        # Exact match
        self.assertTrue(validate_sum_equals_total(splits, -6000))

        # Doesn't match
        self.assertFalse(validate_sum_equals_total(splits, -5000))

        # Within tolerance
        self.assertTrue(validate_sum_equals_total(splits, -6001, tolerance=1))
        self.assertFalse(validate_sum_equals_total(splits, -6002, tolerance=1))

    def test_allocate_remainder(self):
        """Test remainder allocation to last item."""
        amounts = [100, 200, 300]
        total = 605

        result = allocate_remainder(amounts, total)

        self.assertEqual(result, [100, 200, 305])  # Last item gets +5
        self.assertEqual(sum(result), total)

    def test_allocate_remainder_empty_list(self):
        """Test remainder allocation with empty list."""
        result = allocate_remainder([], 100)
        self.assertEqual(result, [])

    def test_safe_divide_proportional(self):
        """Test safe proportional division."""
        # Normal case: 30% of 1000 = 300
        self.assertEqual(safe_divide_proportional(30, 100, 1000), 300)

        # Zero denominator
        self.assertEqual(safe_divide_proportional(30, 0, 1000), 0)

        # Integer division (rounds down)
        self.assertEqual(safe_divide_proportional(33, 100, 1000), 330)  # 33.0% -> 330


class TestTaxAllocationScenarios(unittest.TestCase):
    """Test real-world tax allocation scenarios."""

    def test_apple_receipt_proportional_tax(self):
        """Test Apple receipt tax allocation matching spec example."""
        # Logic Pro ($19.99) + Final Cut Pro ($9.99) = $29.98 + $2.98 tax = $32.96
        subtotal_cents = 2998  # $29.98
        tax_cents = 298  # $2.98
        total_cents = 3296  # $32.96

        # Item costs in cents
        logic_pro_cents = 1999  # $19.99
        final_cut_cents = 999   # $9.99

        # Calculate proportional tax
        logic_tax = safe_divide_proportional(logic_pro_cents, subtotal_cents, tax_cents)
        final_cut_tax = tax_cents - logic_tax  # Remainder

        logic_total = logic_pro_cents + logic_tax
        final_cut_total = final_cut_cents + final_cut_tax

        # Verify exact sum
        self.assertEqual(logic_total + final_cut_total, total_cents)

        # Verify reasonable allocation (Logic Pro gets ~66.7% of tax)
        expected_logic_tax = (1999 * 298) // 2998  # 198
        self.assertEqual(logic_tax, expected_logic_tax)

    def test_amazon_no_tax_calculation_needed(self):
        """Test Amazon items already include tax/shipping in totals."""
        # Amazon provides item-level totals that already include tax
        items = [
            {'amount': 4599, 'name': 'Echo Dot'},  # $45.99
            {'amount': 2350, 'name': 'USB Cable'}, # $23.50
            {'amount': 1599, 'name': 'Phone Case'} # $15.99
        ]

        total_amount = sum(item['amount'] for item in items)
        self.assertEqual(total_amount, 8548)  # $85.48

        # No additional tax calculation needed - amounts are final


if __name__ == '__main__':
    unittest.main()