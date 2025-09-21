#!/usr/bin/env python3
"""
Currency conversion utilities for YNAB Transaction Updater.

Handles conversions between YNAB milliunits, cents, and dollar strings.
All financial calculations use integer arithmetic to avoid floating-point errors.

YNAB uses milliunits: 1000 milliunits = $1.00
Internal calculations use cents: 100 cents = $1.00
"""

from typing import Union


def milliunits_to_cents(milliunits: int) -> int:
    """Convert YNAB milliunits to cents (1000 milliunits = 100 cents)"""
    return abs(milliunits // 10)


def cents_to_milliunits(cents: int) -> int:
    """Convert cents to YNAB milliunits (100 cents = 1000 milliunits)"""
    return cents * 10


def cents_to_dollars_str(cents: int) -> str:
    """Convert 953 cents to '9.53' string using pure integer arithmetic"""
    dollars = cents // 100
    remainder = abs(cents % 100)  # abs() handles negative amounts
    return f"{dollars}.{remainder:02d}"


def dollars_to_cents(dollars: Union[float, str]) -> int:
    """Convert dollars (float or string) to cents - DEPRECATED, use parse_dollars_to_cents"""
    # This function is kept for backward compatibility but should not be used
    # for new code. Use parse_dollars_to_cents() instead.
    if isinstance(dollars, str):
        return parse_dollars_to_cents(dollars)
    # For float input (legacy code), convert carefully
    return int(dollars * 100 + 0.5)


def parse_dollars_to_cents(dollars_str: str) -> int:
    """Parse dollar string to cents using integer arithmetic only

    Examples:
        "12.34" -> 1234
        "$12.34" -> 1234
        "1,234.56" -> 123456
        "12" -> 1200
        "12.5" -> 1250
    """
    # Remove $ and commas
    clean = dollars_str.replace('$', '').replace(',', '').strip()

    if not clean:
        return 0

    # Handle negative amounts
    is_negative = clean.startswith('-')
    if is_negative:
        clean = clean[1:]

    if '.' in clean:
        parts = clean.split('.')
        dollars = int(parts[0]) if parts[0] else 0
        # Handle fractional cents: pad to 2 digits, truncate beyond 2
        cents_str = parts[1].ljust(2, '0')[:2]
        cents = int(cents_str)
        total = dollars * 100 + cents
    else:
        total = int(clean) * 100

    return -total if is_negative else total


def dollars_to_milliunits(dollars: Union[float, str]) -> int:
    """Convert dollars to YNAB milliunits"""
    cents = dollars_to_cents(dollars)
    return cents_to_milliunits(cents)


def validate_sum_equals_total(splits: list, total_milliunits: int, tolerance: int = 0) -> bool:
    """
    Validate that split amounts sum exactly to the transaction total.

    Args:
        splits: List of split dictionaries with 'amount' field in milliunits
        total_milliunits: Expected total in milliunits (negative for expenses)
        tolerance: Allowed difference in milliunits (default: 0 for exact match)

    Returns:
        True if sum matches within tolerance
    """
    split_sum = sum(split['amount'] for split in splits)
    difference = abs(split_sum - total_milliunits)
    return difference <= tolerance


def allocate_remainder(amounts: list, total: int) -> list:
    """
    Allocate remainder from integer division to ensure exact sum.

    The last item gets any remainder to guarantee the sum equals the total.
    This is used for tax allocation where proportional division may leave remainders.

    Args:
        amounts: List of calculated amounts before remainder allocation
        total: Target total that amounts should sum to

    Returns:
        List of amounts with remainder allocated to last item
    """
    if not amounts:
        return amounts

    current_sum = sum(amounts[:-1])
    amounts[-1] = total - current_sum
    return amounts


def format_amount_with_context(amount_milliunits: int, context: str = "") -> str:
    """
    Format amount with optional context for display.

    Args:
        amount_milliunits: Amount in YNAB milliunits
        context: Optional context string (e.g., "incl. tax")

    Returns:
        Formatted string like "$45.99" or "$45.99 (incl. tax)"
    """
    amount_str = f"${cents_to_dollars_str(milliunits_to_cents(amount_milliunits))}"
    if context:
        return f"{amount_str} ({context})"
    return amount_str


def safe_divide_proportional(numerator: int, denominator: int, total: int) -> int:
    """
    Safely calculate proportional division using integer arithmetic.

    Args:
        numerator: The amount to be allocated proportionally
        denominator: The total amount for proportion calculation
        total: The total amount to be distributed

    Returns:
        Proportional amount rounded down (remainder handled separately)
    """
    if denominator == 0:
        return 0
    return (numerator * total) // denominator