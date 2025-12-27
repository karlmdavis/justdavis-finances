#!/usr/bin/env python3
"""
Apple Transaction Matching Module

Core logic for matching Apple receipts to YNAB transactions.
Implements a simplified 2-strategy system optimized for Apple's 1:1 transaction model.
"""

import logging
from datetime import datetime, timedelta
from enum import Enum
from typing import TYPE_CHECKING, Any

from ..core.currency import format_cents
from ..core.models import MatchResult, Receipt, ReceiptItem, Transaction
from ..core.money import Money
from ..ynab.models import YnabTransaction

if TYPE_CHECKING:
    from .parser import ParsedReceipt

logger = logging.getLogger(__name__)


class MatchStrategy(Enum):
    """Different matching strategies"""

    EXACT_MATCH = "exact_date_amount"
    DATE_WINDOW = "date_window_match"


class AppleMatcher:
    """Core Apple receipt to YNAB transaction matcher"""

    def __init__(self, date_window_days: int = 3):
        """
        Initialize the matcher.

        Args:
            date_window_days: Number of days to search before/after transaction date
        """
        self.date_window_days = date_window_days

    def match_single_transaction(
        self, transaction: YnabTransaction, apple_receipts: list["ParsedReceipt"]
    ) -> MatchResult:
        """
        Match a single YNAB transaction to Apple receipts.

        Args:
            transaction: YnabTransaction domain model
            apple_receipts: List of ParsedReceipt domain models

        Returns:
            MatchResult with details of the match
        """
        # Filter to receipts with required fields (date and total)
        valid_receipts = [r for r in apple_receipts if r.receipt_date is not None and r.total is not None]

        # DIAGNOSTIC: Log filtering results
        logger.debug(
            "Filtering receipts: %d total receipts, %d valid receipts (have date and total)",
            len(apple_receipts),
            len(valid_receipts),
        )
        if len(valid_receipts) < len(apple_receipts):
            invalid_count = len(apple_receipts) - len(valid_receipts)
            logger.debug("Filtered out %d receipts missing date or total", invalid_count)

        # Get absolute value for matching (receipts are always positive, transactions are negative for expenses)
        tx_amount_cents = transaction.amount.abs().to_cents()
        tx_date = datetime.combine(transaction.date.date, datetime.min.time())

        logger.debug(
            "Matching transaction %s: %s on %s",
            transaction.id,
            format_cents(tx_amount_cents),
            transaction.date.to_iso_string(),
        )

        # Create Transaction object for MatchResult
        tx_obj = Transaction(
            id=transaction.id,
            date=transaction.date,
            amount=transaction.amount,
            description=transaction.payee_name or "",
            account_name=transaction.account_name or "",
            memo=transaction.memo or "",
            source="ynab",
        )

        # Strategy 1: Exact Date and Amount Match
        exact_match = self._find_exact_match(tx_date, tx_amount_cents, valid_receipts)
        if exact_match:
            receipt = self._create_receipt_from_parsed(exact_match)
            confidence = self._calculate_confidence(tx_amount_cents, exact_match.total.to_cents(), 0)  # type: ignore[union-attr]

            return MatchResult(
                transaction=tx_obj,
                receipts=[receipt],
                confidence=confidence,
                match_method="exact_date_amount",
                date_difference=0,
                amount_difference=0,
                strategy_used="exact_match",
            )

        # Strategy 2: Date Window Match
        window_match, date_diff = self._find_date_window_match(tx_date, tx_amount_cents, valid_receipts)
        if window_match:
            receipt = self._create_receipt_from_parsed(window_match)
            confidence = self._calculate_confidence(tx_amount_cents, window_match.total.to_cents(), date_diff)  # type: ignore[union-attr]

            return MatchResult(
                transaction=tx_obj,
                receipts=[receipt],
                confidence=confidence,
                match_method="date_window_match",
                date_difference=date_diff,
                amount_difference=0,
                strategy_used="date_window",
            )

        # No match found
        return MatchResult(
            transaction=tx_obj,
            receipts=[],
            confidence=0.0,
            match_method="no_match",
            unmatched_amount=tx_amount_cents,
            notes="no_matching_receipts_found",
        )

    def _find_exact_match(
        self, tx_date: datetime, tx_amount: int, receipts: list["ParsedReceipt"]
    ) -> "ParsedReceipt | None":
        """
        Find receipts that match exactly on date and amount.

        Args:
            tx_date: Transaction date
            tx_amount: Transaction amount in cents
            receipts: List of ParsedReceipt domain models

        Returns:
            Matching ParsedReceipt or None
        """
        if not receipts:
            return None

        # DIAGNOSTIC: Log what we're looking for
        logger.debug(
            "Looking for exact match: date=%s, amount=%s (%d cents)",
            tx_date.date(),
            format_cents(tx_amount),
            tx_amount,
        )

        # Find exact date and amount matches
        matches_by_date = []
        matches_by_amount = []
        for receipt in receipts:
            # We know receipt_date and total are not None due to filter in match_single_transaction
            receipt_datetime = datetime.combine(receipt.receipt_date.date, datetime.min.time())  # type: ignore[union-attr]
            receipt_amount_cents = receipt.total.to_cents()  # type: ignore[union-attr]

            # Check date match
            if receipt_datetime.date() == tx_date.date():
                matches_by_date.append(f"{receipt.order_id}:{format_cents(receipt_amount_cents)}")

            # Check amount match
            if receipt_amount_cents == tx_amount:
                matches_by_amount.append(f"{receipt.order_id}:{receipt_datetime.date()}")

            # Check both
            if receipt_datetime.date() == tx_date.date() and receipt_amount_cents == tx_amount:
                logger.debug(
                    "Found exact match: Receipt %s for %s on %s",
                    receipt.order_id or receipt.base_name,
                    format_cents(receipt.total.to_cents()),  # type: ignore[union-attr]
                    receipt_datetime.date(),
                )
                return receipt

        # DIAGNOSTIC: Log near-misses
        if matches_by_date:
            logger.debug(
                "  Found %d receipts on same date but wrong amount: %s",
                len(matches_by_date),
                ", ".join(matches_by_date[:5]),
            )
        if matches_by_amount:
            logger.debug(
                "  Found %d receipts with same amount but wrong date: %s",
                len(matches_by_amount),
                ", ".join(matches_by_amount[:5]),
            )

        return None

    def _find_date_window_match(
        self, tx_date: datetime, tx_amount: int, receipts: list["ParsedReceipt"]
    ) -> tuple["ParsedReceipt | None", int]:
        """
        Find receipts within the date window that match the amount.

        Args:
            tx_date: Transaction date
            tx_amount: Transaction amount in cents
            receipts: List of ParsedReceipt domain models

        Returns:
            Tuple of (matching ParsedReceipt or None, date difference in days)
        """
        if not receipts:
            return None, 0

        # Define date window
        start_date = tx_date - timedelta(days=self.date_window_days)
        end_date = tx_date + timedelta(days=self.date_window_days)

        # Find amount matches within date window, prioritizing closer dates
        best_match = None
        best_date_diff = 999999  # Large integer instead of float('inf')

        for receipt in receipts:
            # We know receipt_date and total are not None due to filter in match_single_transaction
            receipt_datetime = datetime.combine(receipt.receipt_date.date, datetime.min.time())  # type: ignore[union-attr]

            # Check if within date window and exact amount match
            if (
                start_date <= receipt_datetime <= end_date
                and receipt.total.to_cents() == tx_amount  # type: ignore[union-attr]
            ):
                date_diff = abs((receipt_datetime - tx_date).days)
                if date_diff < best_date_diff:
                    best_match = receipt
                    best_date_diff = date_diff

        if best_match:
            logger.debug(
                "Found date window match: Receipt %s for %s, %d days off",
                best_match.order_id or best_match.base_name,
                format_cents(best_match.total.to_cents()),  # type: ignore[union-attr]
                best_date_diff,
            )
            return best_match, best_date_diff

        return None, 0

    def _calculate_confidence(self, ynab_amount: int, apple_amount: int, date_diff_days: int) -> float:
        """
        Calculate confidence score for a match.

        Confidence scoring is based on empirical analysis of matched Apple receipts
        from December 2025 analysis:
        - Dataset: 229 matched Apple Card transactions (2024-03-11 to 2025-11-03)
        - Analysis date: 2025-12-26
        - Distribution of date differences in successful matches:
          * 0 days: 52 matches (22.7% - exact same-day posting)
          * 1 day: 149 matches (65.1% - normal Apple posting delay, most common)
          * 2 days: 24 matches (10.5% - less common but reasonable)
          * 3 days: 4 matches (1.7% - unusual edge cases but real)

        Key insight: 1-day posting delay is Apple's normal behavior, not an uncertainty
        indicator. This informed the confidence scoring to reflect actual posting patterns.

        Args:
            ynab_amount: YNAB transaction amount in cents
            apple_amount: Apple receipt amount in cents
            date_diff_days: Difference in days between transaction and receipt

        Returns:
            Confidence score between 0.0 and 1.0
        """
        # Require exact amount match - no tolerance for differences
        amount_diff = abs(ynab_amount - apple_amount)
        if amount_diff != 0:
            return 0.0

        # Confidence based on date difference with empirical justification
        if date_diff_days == 0:
            confidence = 1.0  # Exact match (22.7% of cases)
        elif date_diff_days == 1:
            confidence = 0.95  # Normal 1-day posting delay (65.1% of cases - most common)
        elif date_diff_days == 2:
            confidence = 0.85  # Less common 2-day delay (10.5% of cases)
        elif date_diff_days == 3:
            confidence = 0.75  # Unusual 3-day delay (1.7% of cases - edge cases)
        else:
            confidence = 0.0  # Outside ±3 day window

        return confidence

    def _create_receipt_from_parsed(self, parsed_receipt: "ParsedReceipt") -> Receipt:
        """
        Create a Receipt object from ParsedReceipt domain model.

        Args:
            parsed_receipt: ParsedReceipt domain model

        Returns:
            Receipt object

        Raises:
            ValueError: If parsed_receipt.base_name is None or empty
        """
        # We know receipt_date and total are not None due to filter in match_single_transaction
        # but for creating Receipt, we need to handle other optional fields properly

        # Validate base_name exists (should always be set by parser)
        if not parsed_receipt.base_name:
            raise ValueError(
                f"Receipt missing base_name (order_id={parsed_receipt.order_id}). "
                "This indicates a parser bug - all receipts must have base_name set."
            )

        # Convert ParsedItem list to list of ReceiptItem
        receipt_items = [
            ReceiptItem(
                name=item.title,
                cost=item.cost,
                quantity=item.quantity,
                metadata={
                    "subscription": item.subscription,
                    "item_type": item.item_type,
                    **item.metadata,
                },
            )
            for item in parsed_receipt.items
        ]

        return Receipt(
            id=parsed_receipt.base_name,
            date=parsed_receipt.receipt_date,  # type: ignore[arg-type]
            vendor="Apple",
            total=parsed_receipt.total,  # type: ignore[arg-type]
            subtotal=parsed_receipt.subtotal,
            tax=parsed_receipt.tax,
            customer_id=parsed_receipt.apple_id or "",
            order_number=parsed_receipt.document_number or "",
            items=receipt_items,
            source="apple_email",
            raw_data=parsed_receipt.to_dict(),
        )


def generate_match_summary(results: list[MatchResult]) -> dict[str, Any]:
    """
    Generate summary statistics for match results.

    Args:
        results: List of MatchResult objects

    Returns:
        Dictionary with summary statistics
    """
    total_transactions = len(results)
    matched_transactions = sum(1 for r in results if r.receipts)

    if total_transactions == 0:
        return {"total_transactions": 0}

    # Calculate amounts using Money type directly
    total_money = Money.from_cents(sum(r.transaction.amount.abs().to_cents() for r in results))
    matched_money = Money.from_cents(
        sum(r.transaction.amount.abs().to_cents() for r in results if r.receipts)
    )
    unmatched_money = Money.from_cents(total_money.to_cents() - matched_money.to_cents())

    # Convert to cents for JSON serialization
    matched_amount = matched_money.to_cents()
    unmatched_amount = unmatched_money.to_cents()

    # Confidence statistics
    matched_confidences = [r.confidence for r in results if r.receipts]
    avg_confidence = sum(matched_confidences) / len(matched_confidences) if matched_confidences else 0

    # Strategy breakdown
    strategy_counts: dict[str, int] = {}
    for result in results:
        if result.match_method and result.receipts:
            strategy_counts[result.match_method] = strategy_counts.get(result.match_method, 0) + 1

    summary = {
        "total_transactions": total_transactions,
        "matched": matched_transactions,
        "unmatched": total_transactions - matched_transactions,
        "match_rate": matched_transactions / total_transactions if total_transactions > 0 else 0,
        "average_confidence": round(avg_confidence, 3),
        "total_amount_matched": matched_amount,
        "total_amount_unmatched": unmatched_amount,
        "strategy_breakdown": strategy_counts,
    }

    return summary
