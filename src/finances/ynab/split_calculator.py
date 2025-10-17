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

from typing import Any, overload

from ..amazon.models import MatchedOrderItem
from ..apple.parser import ParsedReceipt
from ..core.currency import (
    allocate_remainder,
    cents_to_milliunits,
    safe_divide_proportional,
    validate_sum_equals_total,
)
from ..core.money import Money
from .models import YnabSplit, YnabTransaction


class SplitCalculationError(Exception):
    """Raised when split calculation fails validation"""

    pass


def calculate_amazon_splits(
    transaction: YnabTransaction,
    amazon_items: list[MatchedOrderItem],
) -> list[YnabSplit]:
    """
    Calculate splits for Amazon transaction using pre-allocated item totals.

    Match-layer items already have tax and shipping allocated in the 'amount' field.
    No additional calculation needed.

    Args:
        transaction: YNAB transaction domain model
        amazon_items: List of MatchedOrderItem from match results

    Returns:
        List of YnabSplit domain models

    Raises:
        SplitCalculationError: If split amounts don't sum to transaction total
    """
    tx_milliunits = transaction.amount.to_milliunits()
    splits: list[YnabSplit] = []

    for item in amazon_items:
        # Use amount from MatchedOrderItem (includes tax/shipping)
        item_amount_cents = item.amount.to_cents()
        item_amount_milliunits = cents_to_milliunits(item_amount_cents)

        # YNAB uses negative amounts for expenses
        split_amount = Money.from_milliunits(-item_amount_milliunits)

        memo = item.name
        if item.quantity > 1:
            memo += f" (qty: {item.quantity})"

        splits.append(YnabSplit(amount=split_amount, memo=memo))

    # Verify splits sum to transaction total
    split_dicts = [{"amount": s.amount.to_milliunits(), "memo": s.memo} for s in splits]
    if not validate_sum_equals_total(split_dicts, tx_milliunits):
        total_splits = sum(s.amount.to_milliunits() for s in splits)
        raise SplitCalculationError(
            f"Amazon splits total {total_splits} doesn't match transaction {tx_milliunits}"
        )

    return splits


@overload
def calculate_apple_splits(
    transaction_amount: YnabTransaction,
    apple_items: ParsedReceipt,
) -> list[YnabSplit]: ...


@overload
def calculate_apple_splits(
    transaction_amount: int,
    apple_items: list[dict[str, Any]],
    receipt_subtotal: int | None = None,
    receipt_tax: int | None = None,
) -> list[dict[str, Any]]: ...


def calculate_apple_splits(
    transaction_amount: int | YnabTransaction,
    apple_items: list[dict[str, Any]] | ParsedReceipt,
    receipt_subtotal: int | None = None,
    receipt_tax: int | None = None,
) -> list[dict[str, Any]] | list[YnabSplit]:
    """
    Calculate splits for Apple transaction with proportional tax allocation.

    Apple provides subtotal and tax separately, requiring proportional allocation.

    Supports two signatures:
    1. New: calculate_apple_splits(transaction: YnabTransaction, receipt: ParsedReceipt) -> list[YnabSplit]
    2. Legacy: calculate_apple_splits(amount: int, items: list[dict], subtotal, tax) -> list[dict]

    Args:
        transaction_amount: YNAB transaction (new) or amount in milliunits (legacy)
        apple_items: ParsedReceipt (new) or list of dicts (legacy)
        receipt_subtotal: Receipt subtotal in cents (legacy only)
        receipt_tax: Receipt tax in cents (legacy only)

    Returns:
        List of YnabSplit (new) or split dictionaries (legacy)

    Raises:
        SplitCalculationError: If split amounts don't sum to transaction total
    """
    # Detect which signature is being used
    if isinstance(transaction_amount, YnabTransaction):
        # New signature: domain models
        return _calculate_apple_splits_domain_models(transaction_amount, apple_items)  # type: ignore[arg-type]
    else:
        # Legacy signature: dicts
        return _calculate_apple_splits_legacy(transaction_amount, apple_items, receipt_subtotal, receipt_tax)  # type: ignore[arg-type]


def _calculate_apple_splits_domain_models(
    transaction: YnabTransaction,
    receipt: ParsedReceipt,
) -> list[YnabSplit]:
    """Calculate Apple splits using domain models (new implementation)."""
    tx_milliunits = transaction.amount.to_milliunits()

    if not receipt.items:
        raise SplitCalculationError("No Apple items provided for split calculation")

    # Extract item costs and calculate subtotal
    item_subtotals = [item.cost.to_cents() for item in receipt.items]
    calculated_subtotal = sum(item_subtotals)

    # Use receipt subtotal/tax if available, otherwise use calculated values
    total_subtotal = receipt.subtotal.to_cents() if receipt.subtotal else calculated_subtotal
    total_tax = receipt.tax.to_cents() if receipt.tax else 0

    # Calculate proportional tax for each item
    item_taxes: list[int] = []
    if total_tax > 0 and total_subtotal > 0:
        for item_subtotal in item_subtotals:
            proportional_tax = safe_divide_proportional(item_subtotal, total_subtotal, total_tax)
            item_taxes.append(proportional_tax)

        # Allocate any remainder to ensure exact total
        item_taxes = allocate_remainder(item_taxes, total_tax)
    else:
        item_taxes = [0] * len(item_subtotals)

    # Create splits
    splits: list[YnabSplit] = []
    for i, item in enumerate(receipt.items):
        item_total = item_subtotals[i] + item_taxes[i]
        item_amount_milliunits = cents_to_milliunits(item_total)

        # YNAB uses negative amounts for expenses
        split_amount = Money.from_milliunits(-item_amount_milliunits)

        splits.append(YnabSplit(amount=split_amount, memo=item.title))

    # Verify splits sum to transaction total
    split_dicts = [{"amount": s.amount.to_milliunits(), "memo": s.memo} for s in splits]
    if not validate_sum_equals_total(split_dicts, tx_milliunits):
        total_splits = sum(s.amount.to_milliunits() for s in splits)
        raise SplitCalculationError(
            f"Apple splits total {total_splits} doesn't match transaction {tx_milliunits}"
        )

    return splits


def _calculate_apple_splits_legacy(
    transaction_amount: int,
    apple_items: list[dict[str, Any]],
    receipt_subtotal: int | None = None,
    receipt_tax: int | None = None,
) -> list[dict[str, Any]]:
    """Calculate Apple splits using legacy dict format."""
    if not apple_items:
        raise SplitCalculationError("No Apple items provided for split calculation")

    # Calculate item subtotals
    item_subtotals = []
    calculated_subtotal = 0

    for item in apple_items:
        item_price = item.get("price", 0)
        item_subtotals.append(item_price)
        calculated_subtotal += item_price

    # Use provided subtotal if available, otherwise calculated
    total_subtotal = receipt_subtotal if receipt_subtotal is not None else calculated_subtotal
    total_tax = receipt_tax if receipt_tax is not None else 0

    # Calculate proportional tax for each item
    item_taxes = []
    if total_tax > 0 and total_subtotal > 0:
        for item_subtotal in item_subtotals:
            proportional_tax = safe_divide_proportional(item_subtotal, total_subtotal, total_tax)
            item_taxes.append(proportional_tax)

        # Allocate any remainder to ensure exact total
        item_taxes = allocate_remainder(item_taxes, total_tax)
    else:
        item_taxes = [0] * len(item_subtotals)

    # Create splits
    splits = []
    for i, item in enumerate(apple_items):
        item_total = item_subtotals[i] + item_taxes[i]
        item_amount_milliunits = cents_to_milliunits(item_total)

        # YNAB uses negative amounts for expenses
        split_amount = -item_amount_milliunits

        memo = item["name"]
        split = {"amount": split_amount, "memo": memo}

        splits.append(split)

    # Verify splits sum to transaction total
    if not validate_sum_equals_total(splits, transaction_amount):
        total_splits = sum(split["amount"] for split in splits)
        raise SplitCalculationError(
            f"Apple splits total {total_splits} doesn't match transaction {transaction_amount}"
        )

    return splits


def calculate_generic_splits(
    transaction_amount: int, items: list[dict[str, Any]], category_id: str | None = None
) -> list[dict[str, Any]]:
    """
    Calculate splits for generic transaction with simple item amounts.

    Args:
        transaction_amount: YNAB transaction amount in milliunits (negative for expenses)
        items: List of items with 'name', 'amount' (cents)
        category_id: Optional category ID for all splits

    Returns:
        List of split dictionaries for YNAB with amount, memo, category_id

    Raises:
        SplitCalculationError: If split amounts don't sum to transaction total
    """
    splits = []

    for item in items:
        item_amount_milliunits = cents_to_milliunits(item["amount"])

        # YNAB uses negative amounts for expenses
        split_amount = -item_amount_milliunits

        split = {"amount": split_amount, "memo": item["name"]}

        if category_id:
            split["category_id"] = category_id

        splits.append(split)

    # Verify splits sum to transaction total
    if not validate_sum_equals_total(splits, transaction_amount):
        total_splits = sum(split["amount"] for split in splits)
        raise SplitCalculationError(
            f"Generic splits total {total_splits} doesn't match transaction {transaction_amount}"
        )

    return splits


def validate_split_calculation(
    splits: list[dict[str, Any]], expected_total: int, tolerance: int = 0
) -> tuple[bool, str]:
    """
    Validate that calculated splits are correct.

    Args:
        splits: List of split dictionaries
        expected_total: Expected total amount in milliunits
        tolerance: Allowed difference in milliunits

    Returns:
        Tuple of (is_valid, error_message)
    """
    if not splits:
        return False, "No splits provided"

    total_splits = sum(split["amount"] for split in splits)
    difference = abs(total_splits - expected_total)

    if difference > tolerance:
        return False, f"Split total {total_splits} differs from expected {expected_total} by {difference}"

    # Check that all splits have required fields
    for i, split in enumerate(splits):
        if "amount" not in split:
            return False, f"Split {i} missing 'amount' field"
        if "memo" not in split:
            return False, f"Split {i} missing 'memo' field"
        if not isinstance(split["amount"], int):
            return False, f"Split {i} amount is not an integer: {type(split['amount'])}"

    return True, "Splits are valid"


def sort_splits_for_stability(splits: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Sort splits for stable, consistent ordering.

    Sorts by amount (largest first), then by memo for tie-breaking.

    Args:
        splits: List of split dictionaries

    Returns:
        Sorted list of splits
    """
    return sorted(splits, key=lambda s: (-abs(s["amount"]), s["memo"]))


def create_split_summary(splits: list[dict[str, Any]]) -> dict[str, Any]:
    """
    Create a summary of split calculation results.

    Args:
        splits: List of calculated splits

    Returns:
        Dictionary with summary statistics
    """
    if not splits:
        return {
            "split_count": 0,
            "total_amount": 0,
            "average_amount": 0,
            "largest_split": 0,
            "smallest_split": 0,
        }

    amounts = [abs(split["amount"]) for split in splits]
    total_amount = sum(split["amount"] for split in splits)

    return {
        "split_count": len(splits),
        "total_amount": total_amount,
        "average_amount": total_amount // len(splits),
        "largest_split": max(amounts),
        "smallest_split": min(amounts),
        "memo_preview": [split["memo"][:50] for split in splits[:3]],  # First 3 memos, truncated
    }
