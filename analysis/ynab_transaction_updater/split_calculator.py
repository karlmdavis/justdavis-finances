#!/usr/bin/env python3
"""
Split Calculator for YNAB Transaction Updater.

Calculates transaction splits with proper tax allocation for Amazon and Apple purchases.
Uses integer arithmetic throughout to avoid floating-point precision errors.

Key Features:
- Amazon: Uses pre-allocated item totals (tax/shipping included)
- Apple: Proportional tax allocation across items
- Stable sorting and remainder allocation
- Sum verification for exact total matching
"""

from typing import Dict, List, Any, Optional, Tuple
try:
    from .currency_utils import (
        milliunits_to_cents, cents_to_milliunits, dollars_to_milliunits,
        validate_sum_equals_total, allocate_remainder, safe_divide_proportional
    )
except ImportError:
    from currency_utils import (
        milliunits_to_cents, cents_to_milliunits, dollars_to_milliunits,
        validate_sum_equals_total, allocate_remainder, safe_divide_proportional
    )


class SplitCalculationError(Exception):
    """Raised when split calculation fails validation"""
    pass


def calculate_amazon_splits(
    transaction_amount: int,
    amazon_items: List[Dict[str, Any]],
    category_id: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Calculate splits for Amazon transaction using pre-allocated item totals.

    Amazon provides item-level totals in the 'amount' field that already includes
    tax and shipping allocated to each item. No additional calculation needed.

    Args:
        transaction_amount: YNAB transaction amount in milliunits (negative for expenses)
        amazon_items: List of Amazon items with 'name', 'amount' (cents), 'quantity', 'unit_price'
        category_id: Optional category ID for all splits

    Returns:
        List of split dictionaries for YNAB with amount, memo, category_id

    Raises:
        SplitCalculationError: If splits don't sum to transaction total
    """
    if not amazon_items:
        raise SplitCalculationError("No Amazon items provided for split calculation")

    # Handle single item case - no split needed, just memo update
    if len(amazon_items) == 1:
        item = amazon_items[0]
        memo = _format_amazon_item_memo(item)
        return [{
            'amount': transaction_amount,
            'memo': memo,
            'category_id': category_id
        }]

    # Multiple items - calculate splits
    splits = []
    total_cents = milliunits_to_cents(transaction_amount)

    # Sort items for stable ordering (by amount desc, then by name)
    sorted_items = sorted(
        amazon_items,
        key=lambda x: (-x['amount'], x['name'])
    )

    # Calculate splits for all items except last
    allocated_cents = 0
    for item in sorted_items[:-1]:
        item_cents = item['amount']
        split_amount = -cents_to_milliunits(item_cents)  # Negative for expense

        splits.append({
            'amount': split_amount,
            'memo': _format_amazon_item_memo(item),
            'category_id': category_id
        })
        allocated_cents += item_cents

    # Last item gets remainder to ensure exact sum
    remaining_cents = total_cents - allocated_cents
    last_split_amount = -cents_to_milliunits(remaining_cents)

    splits.append({
        'amount': last_split_amount,
        'memo': _format_amazon_item_memo(sorted_items[-1]),
        'category_id': category_id
    })

    # Verify sum equals transaction total
    if not validate_sum_equals_total(splits, transaction_amount):
        calculated_sum = sum(split['amount'] for split in splits)
        raise SplitCalculationError(
            f"Amazon splits sum ({calculated_sum}) doesn't match transaction ({transaction_amount})"
        )

    return splits


def calculate_apple_splits(
    transaction_amount: int,
    apple_items: List[Dict[str, Any]],
    subtotal: float,
    tax: float,
    category_id: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Calculate splits for Apple transaction with proportional tax allocation.

    Apple provides receipt-level tax that must be allocated proportionally across items.
    Uses integer arithmetic with remainder allocation to ensure exact sum.

    Args:
        transaction_amount: YNAB transaction amount in milliunits (negative for expenses)
        apple_items: List of Apple items with 'title', 'cost' (dollars)
        subtotal: Receipt subtotal in dollars
        tax: Receipt tax in dollars
        category_id: Optional category ID for all splits

    Returns:
        List of split dictionaries for YNAB with amount, memo, category_id

    Raises:
        SplitCalculationError: If splits don't sum to transaction total
    """
    if not apple_items:
        raise SplitCalculationError("No Apple items provided for split calculation")

    # Handle single item case - no split needed, just memo update
    if len(apple_items) == 1:
        item = apple_items[0]
        memo = _format_apple_item_memo(item, include_tax=tax > 0)
        return [{
            'amount': transaction_amount,
            'memo': memo,
            'category_id': category_id
        }]

    # Multiple items - calculate splits with tax allocation
    splits = []
    total_milliunits = abs(transaction_amount)

    # Convert to milliunits for integer arithmetic
    subtotal_milliunits = dollars_to_milliunits(subtotal)
    tax_milliunits = dollars_to_milliunits(tax)

    # Sort items for stable ordering (by cost desc, then by title)
    sorted_items = sorted(
        apple_items,
        key=lambda x: (-x['cost'], x['title'])
    )

    # Calculate splits for all items except last
    allocated_milliunits = 0

    for item in sorted_items[:-1]:
        item_base_milliunits = dollars_to_milliunits(item['cost'])

        # Calculate proportional tax allocation
        if subtotal_milliunits > 0:
            item_tax = safe_divide_proportional(
                item_base_milliunits,
                subtotal_milliunits,
                tax_milliunits
            )
        else:
            item_tax = 0

        item_total = item_base_milliunits + item_tax

        splits.append({
            'amount': -item_total,  # Negative for expense
            'memo': _format_apple_item_memo(item, include_tax=tax > 0),
            'category_id': category_id
        })
        allocated_milliunits += item_total

    # Last item gets remainder to ensure exact sum
    remaining_milliunits = total_milliunits - allocated_milliunits

    splits.append({
        'amount': -remaining_milliunits,
        'memo': _format_apple_item_memo(sorted_items[-1], include_tax=tax > 0),
        'category_id': category_id
    })

    # Verify sum equals transaction total
    if not validate_sum_equals_total(splits, transaction_amount):
        calculated_sum = sum(split['amount'] for split in splits)
        raise SplitCalculationError(
            f"Apple splits sum ({calculated_sum}) doesn't match transaction ({transaction_amount})"
        )

    return splits


def should_split_transaction(items: List[Dict[str, Any]]) -> bool:
    """
    Determine if transaction should be split based on number of items.

    Args:
        items: List of items (Amazon or Apple)

    Returns:
        True if transaction should be split (>1 item), False for memo-only update
    """
    return len(items) > 1


def _format_amazon_item_memo(item: Dict[str, Any]) -> str:
    """
    Format memo for Amazon item.

    Args:
        item: Amazon item with 'name', 'quantity', 'amount' (cents, includes shipping/tax)

    Returns:
        Formatted memo like "Echo Dot (4th Gen) - Charcoal (1x @ $45.99)"
    """
    name = item['name']
    quantity = item.get('quantity', 1)
    # Use 'amount' (includes shipping/tax) instead of 'unit_price' (base price only)
    total_cents = item.get('amount', item.get('unit_price', 0))
    # Use pure integer arithmetic for display
    dollars = total_cents // 100
    remainder = abs(total_cents % 100)
    total_str = f"${dollars}.{remainder:02d}"

    return f"{name} ({quantity}x @ {total_str})"


def _format_apple_item_memo(item: Dict[str, Any], include_tax: bool = True) -> str:
    """
    Format memo for Apple item.

    Args:
        item: Apple item with 'title'
        include_tax: Whether to include tax notation in memo

    Returns:
        Formatted memo like "Logic Pro (incl. tax)" or "Logic Pro"
    """
    title = item['title']
    if include_tax:
        return f"{title} (incl. tax)"
    return title


def validate_split_calculation(
    splits: List[Dict[str, Any]],
    transaction_amount: int,
    expected_item_count: int
) -> Tuple[bool, str]:
    """
    Validate calculated splits against requirements.

    Args:
        splits: List of calculated splits
        transaction_amount: Original transaction amount in milliunits
        expected_item_count: Expected number of items

    Returns:
        Tuple of (is_valid, error_message)
    """
    # Check split count
    if len(splits) != expected_item_count and len(splits) != 1:
        return False, f"Split count ({len(splits)}) doesn't match items ({expected_item_count})"

    # Check all splits have required fields first
    for i, split in enumerate(splits):
        if 'amount' not in split:
            return False, f"Split {i} missing amount field"
        if 'memo' not in split:
            return False, f"Split {i} missing memo field"
        # Only check sign for expense transactions (negative amounts)
        if transaction_amount < 0 and split['amount'] >= 0:
            return False, f"Split {i} amount should be negative for expense"

    # Check sum
    if not validate_sum_equals_total(splits, transaction_amount):
        split_sum = sum(split['amount'] for split in splits)
        return False, f"Split sum ({split_sum}) doesn't equal transaction ({transaction_amount})"

    return True, ""