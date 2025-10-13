#!/usr/bin/env python3
"""Tests for core currency utilities."""

import pytest

from finances.core.currency import (
    allocate_remainder,
    cents_to_dollars_str,
    cents_to_milliunits,
    format_cents,
    format_milliunits,
    parse_dollars_to_cents,
    safe_currency_to_cents,
    validate_sum_equals_total,
)


class TestCurrencyConversions:
    """Test core currency conversion functions."""

    @pytest.mark.currency
    def test_cents_to_milliunits(self):
        """Test conversion from cents to YNAB milliunits."""
        assert cents_to_milliunits(4599) == 45990  # $45.99
        assert cents_to_milliunits(100) == 1000  # $1.00
        assert cents_to_milliunits(0) == 0  # $0.00

    @pytest.mark.currency
    def test_cents_to_dollars_str(self):
        """Test formatting cents as dollar strings."""
        assert cents_to_dollars_str(4599) == "45.99"
        assert cents_to_dollars_str(100) == "1.00"
        assert cents_to_dollars_str(0) == "0.00"
        assert cents_to_dollars_str(5) == "0.05"
        assert cents_to_dollars_str(-4599) == "-45.99"

    @pytest.mark.currency
    def test_safe_currency_to_cents(self):
        """Test safe currency string parsing."""
        assert safe_currency_to_cents("$45.99") == 4599
        assert safe_currency_to_cents("45.99") == 4599
        assert safe_currency_to_cents("$0.00") == 0
        assert safe_currency_to_cents("") == 0
        assert safe_currency_to_cents("FREE") == 0
        assert safe_currency_to_cents("invalid") == 0
        assert safe_currency_to_cents(45.99) == 4599  # Float input

    @pytest.mark.currency
    def test_parse_dollars_to_cents(self):
        """Test detailed dollar string parsing."""
        assert parse_dollars_to_cents("12.34") == 1234
        assert parse_dollars_to_cents("$12.34") == 1234
        assert parse_dollars_to_cents("1,234.56") == 123456
        assert parse_dollars_to_cents("12") == 1200
        assert parse_dollars_to_cents("12.5") == 1250
        assert parse_dollars_to_cents("-12.34") == -1234

    @pytest.mark.currency
    def test_format_functions(self):
        """Test formatting convenience functions."""
        assert format_cents(4599) == "$45.99"
        assert format_milliunits(45990) == "$45.99"

    @pytest.mark.currency
    def test_validation_functions(self):
        """Test currency validation utilities."""
        splits = [
            {"amount": 2000},
            {"amount": 3000},
        ]
        assert validate_sum_equals_total(splits, 5000) is True
        assert validate_sum_equals_total(splits, 5010) is False
        assert validate_sum_equals_total(splits, 5005, tolerance=10) is True

    @pytest.mark.currency
    def test_allocate_remainder(self):
        """Test remainder allocation for precise sums."""
        amounts = [3333, 3333, 3333]  # Sum: 9999
        allocated = allocate_remainder(amounts, 10000)
        assert sum(allocated) == 10000
        assert allocated[-1] == 3334  # Last item gets remainder


class TestCurrencyPrecision:
    """Test currency precision and edge cases."""

    @pytest.mark.currency
    def test_negative_amounts(self):
        """Test handling of negative amounts (expenses)."""
        # Formatting preserves sign
        assert cents_to_dollars_str(-4599) == "-45.99"

    @pytest.mark.currency
    def test_cents_to_dollars_str_with_commas(self):
        """Test comma separators in large dollar amounts using pure integer operations."""
        # Verify comma placement for various amounts
        assert cents_to_dollars_str(10000000) == "100,000.00"  # $100k
        assert cents_to_dollars_str(123456789) == "1,234,567.89"  # $1.2M
        assert cents_to_dollars_str(-10000000) == "-100,000.00"  # Negative
        assert cents_to_dollars_str(100) == "1.00"  # No comma for small amounts

        # Test million+ amounts to verify comma placement
        assert cents_to_dollars_str(100000000) == "1,000,000.00"  # $1M exactly
        assert cents_to_dollars_str(543210987) == "5,432,109.87"  # $5.4M
        assert cents_to_dollars_str(1000) == "10.00"  # No comma needed
        assert cents_to_dollars_str(100000) == "1,000.00"  # First comma at thousands


@pytest.mark.currency
def test_integration_with_fixtures(currency_test_cases):
    """Test currency functions with fixture data."""
    for case in currency_test_cases:
        input_str = case["input"]
        expected_cents = case["cents"]
        expected_milliunits = case["milliunits"]

        # Test string to cents conversion
        cents = safe_currency_to_cents(input_str)
        assert cents == expected_cents

        # Test milliunits conversion
        milliunits = cents_to_milliunits(cents)
        assert milliunits == expected_milliunits

        # Test round-trip formatting
        formatted = format_cents(cents)
        assert formatted.replace("$", "") == input_str.replace("$", "")
