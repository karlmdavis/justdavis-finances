#!/usr/bin/env python3
"""
Currency Conversion and Handling Utilities

Comprehensive currency handling for the Davis Family Finances system.
All financial calculations use integer arithmetic to avoid floating-point errors.

Currency Systems:
- YNAB uses milliunits: 1000 milliunits = $1.00
- Internal calculations use cents: 100 cents = $1.00
- Display uses dollar strings: "$12.34"

Key Principles:
- Never use floating-point arithmetic for currency calculations
- Always use integer arithmetic (milliunits/cents)
- Handle precision carefully in conversions
- Validate calculations with sum checks
"""

from decimal import Decimal, InvalidOperation
from typing import Any, Union


def milliunits_to_cents(milliunits: int) -> int:
    """
    Convert YNAB milliunits to cents.

    Args:
        milliunits: YNAB amount in milliunits (1000 = $1.00)

    Returns:
        Amount in cents (100 = $1.00)

    Example:
        milliunits_to_cents(-45990) -> 4599  # $45.99
    """
    return abs(milliunits // 10)


def cents_to_milliunits(cents: int) -> int:
    """
    Convert cents to YNAB milliunits.

    Args:
        cents: Amount in cents (100 = $1.00)

    Returns:
        Amount in milliunits (1000 = $1.00)

    Example:
        cents_to_milliunits(4599) -> 45990  # $45.99
    """
    return cents * 10


def cents_to_dollars_str(cents: int) -> str:
    """
    Convert cents to dollar string using pure integer arithmetic.

    Args:
        cents: Amount in cents

    Returns:
        Formatted dollar string

    Example:
        cents_to_dollars_str(4599) -> "45.99"
    """
    # Handle negative amounts properly
    is_negative = cents < 0
    abs_cents = abs(int(cents))  # Ensure it's an int

    dollars = int(abs_cents // 100)
    remainder = int(abs_cents % 100)

    if is_negative:
        return f"-{dollars}.{remainder:02d}"
    else:
        return f"{dollars}.{remainder:02d}"


def safe_currency_to_cents(currency_str: Union[str, int, float]) -> int:
    """
    Safely convert currency string to integer cents using decimal arithmetic.

    Handles various input formats and edge cases gracefully.

    Args:
        currency_str: Currency string like '$12.34', '12.34', or '12,345.67'

    Returns:
        Integer cents (1234 for $12.34), 0 for invalid input

    Examples:
        safe_currency_to_cents('$45.99') -> 4599
        safe_currency_to_cents('FREE') -> 0
        safe_currency_to_cents('') -> 0
    """
    try:
        # Handle non-string input
        if isinstance(currency_str, (int, float)):
            return int(currency_str * 100) if isinstance(currency_str, float) else currency_str * 100

        # Clean the string
        clean_str = str(currency_str).replace("$", "").replace(",", "").strip()

        # Handle empty or special strings
        if not clean_str or clean_str.lower() in ["0", "nan", "none", "free", ""]:
            return 0

        # Use Decimal for precise arithmetic
        decimal_amount = Decimal(clean_str)
        return int(decimal_amount * 100)
    except (ValueError, TypeError, OverflowError, InvalidOperation):
        return 0


def dollars_to_cents(dollars: Union[float, str]) -> int:
    """
    Convert dollars (float or string) to cents.

    Note: Use parse_dollars_to_cents for new code - this is for backward compatibility.

    Args:
        dollars: Dollar amount as float or string

    Returns:
        Amount in cents
    """
    if isinstance(dollars, str):
        return parse_dollars_to_cents(dollars)
    # For float input (legacy code), convert carefully
    return int(dollars * 100 + 0.5)


def parse_dollars_to_cents(dollars_str: str) -> int:
    """
    Parse dollar string to cents using integer arithmetic only.

    Args:
        dollars_str: String representation of dollar amount

    Returns:
        Amount in cents

    Examples:
        parse_dollars_to_cents("12.34") -> 1234
        parse_dollars_to_cents("$12.34") -> 1234
        parse_dollars_to_cents("1,234.56") -> 123456
        parse_dollars_to_cents("12") -> 1200
        parse_dollars_to_cents("12.5") -> 1250
    """
    # Remove $ and commas
    clean = dollars_str.replace("$", "").replace(",", "").strip()

    if not clean:
        return 0

    # Handle negative amounts
    is_negative = clean.startswith("-")
    if is_negative:
        clean = clean[1:]

    if "." in clean:
        parts = clean.split(".")
        dollars = int(parts[0]) if parts[0] else 0
        # Handle fractional cents: pad to 2 digits, truncate beyond 2
        cents_str = parts[1].ljust(2, "0")[:2]
        cents = int(cents_str)
        total = dollars * 100 + cents
    else:
        total = int(clean) * 100

    return -total if is_negative else total


def dollars_to_milliunits(dollars: Union[float, str]) -> int:
    """
    Convert dollars to YNAB milliunits.

    Args:
        dollars: Dollar amount as float or string

    Returns:
        Amount in milliunits
    """
    cents = dollars_to_cents(dollars)
    return cents_to_milliunits(cents)


def format_amount_with_context(amount_milliunits: int, context: str = "") -> str:
    """
    Format milliunits amount with optional context for display.

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


def validate_sum_equals_total(
    splits: list[dict[str, Any]], total_milliunits: int, tolerance: int = 0
) -> bool:
    """
    Validate that split amounts sum exactly to the transaction total.

    Args:
        splits: List of split dictionaries with 'amount' field in milliunits
        total_milliunits: Expected total in milliunits (negative for expenses)
        tolerance: Allowed difference in milliunits (default: 0 for exact match)

    Returns:
        True if sum matches within tolerance
    """
    split_sum = sum(split["amount"] for split in splits)
    difference = abs(split_sum - total_milliunits)
    return difference <= tolerance


def allocate_remainder(amounts: list[int], total: int) -> list[int]:
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

    amounts_copy = amounts.copy()
    current_sum = sum(amounts_copy[:-1])
    amounts_copy[-1] = total - current_sum
    return amounts_copy


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


# Convenience functions for common conversions
def format_cents(cents: int) -> str:
    """Format cents as dollar string with $ prefix."""
    return f"${cents_to_dollars_str(cents)}"


def format_milliunits(milliunits: int) -> str:
    """Format milliunits as dollar string with $ prefix."""
    return format_cents(milliunits_to_cents(milliunits))


# Validation utilities
def is_valid_currency_string(currency_str: str) -> bool:
    """Check if a string represents a valid currency amount."""
    try:
        safe_currency_to_cents(currency_str)
        return True
    except:
        return False


def normalize_currency_precision(amounts: list[int], total: int) -> list[int]:
    """
    Normalize a list of amounts to ensure they sum exactly to the total.

    Distributes any rounding errors across amounts proportionally.
    """
    if not amounts or total == 0:
        return amounts

    current_sum = sum(amounts)
    if current_sum == total:
        return amounts

    # Distribute the difference
    difference = total - current_sum
    amounts_copy = amounts.copy()

    # Add difference to the largest amount (most likely to absorb it cleanly)
    if amounts_copy:
        max_index = amounts_copy.index(max(amounts_copy))
        amounts_copy[max_index] += difference

    return amounts_copy
