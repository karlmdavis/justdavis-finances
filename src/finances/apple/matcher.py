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
from ..core.models import MatchResult, Receipt, Transaction
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

    def __init__(self, date_window_days: int = 2):
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
        valid_receipts = [
            r for r in apple_receipts
            if r.receipt_date is not None and r.total is not None
        ]

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
            date_obj=transaction.date,
            amount_money=transaction.amount,
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

        # Find exact date and amount matches
        for receipt in receipts:
            # We know receipt_date and total are not None due to filter in match_single_transaction
            receipt_datetime = datetime.combine(receipt.receipt_date.date, datetime.min.time())  # type: ignore[union-attr]
            if receipt_datetime.date() == tx_date.date() and receipt.total.to_cents() == tx_amount:  # type: ignore[union-attr]
                logger.debug(
                    "Found exact match: Receipt %s for %s",
                    receipt.order_id or receipt.base_name,
                    format_cents(receipt.total.to_cents()),  # type: ignore[union-attr]
                )
                return receipt

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

            # Check if within date window
            if start_date <= receipt_datetime <= end_date:
                # Check for exact amount match
                if receipt.total.to_cents() == tx_amount:  # type: ignore[union-attr]
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

        Args:
            ynab_amount: YNAB transaction amount in cents
            apple_amount: Apple receipt amount in cents
            date_diff_days: Difference in days between transaction and receipt

        Returns:
            Confidence score between 0.0 and 1.0
        """
        confidence = 1.0

        # Amount matching penalty (now only exact matches are allowed)
        amount_diff = abs(ynab_amount - apple_amount)
        amount_penalty = 0 if amount_diff == 0 else 1.0  # No tolerance for amount differences

        # Date matching penalty
        date_penalty = min(0.3, date_diff_days * 0.15)

        # Calculate final confidence
        confidence = max(0, confidence - amount_penalty - date_penalty)

        # Boost for exact amount match despite date difference, but still apply date penalty
        if amount_diff == 0 and date_diff_days <= 2:
            # Minimum confidence for exact amount matches, but still differentiate by date
            base_confidence = 0.85
            confidence = max(confidence, base_confidence - (date_diff_days * 0.05))

        return round(confidence, 2)

    def _create_receipt_from_parsed(self, parsed_receipt: "ParsedReceipt") -> Receipt:
        """
        Create a Receipt object from ParsedReceipt domain model.

        Args:
            parsed_receipt: ParsedReceipt domain model

        Returns:
            Receipt object
        """
        # We know receipt_date and total are not None due to filter in match_single_transaction
        # but for creating Receipt, we need to handle other optional fields properly

        # Convert ParsedItem list to list of dicts for Receipt.items
        items_dicts = [
            {
                "title": item.title,
                "cost": item.cost.to_cents(),
                "quantity": item.quantity,
                "subscription": item.subscription,
                "item_type": item.item_type,
                "metadata": item.metadata,
            }
            for item in parsed_receipt.items
        ]

        return Receipt(
            id=parsed_receipt.order_id or parsed_receipt.base_name or "",
            date_obj=parsed_receipt.receipt_date,  # type: ignore[arg-type]
            vendor="Apple",
            total_money=parsed_receipt.total,  # type: ignore[arg-type]
            subtotal_money=parsed_receipt.subtotal,
            tax_money=parsed_receipt.tax,
            customer_id=parsed_receipt.apple_id or "",
            order_number=parsed_receipt.document_number or "",
            items=items_dicts,
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
    total_money = Money.from_cents(sum(r.transaction.amount_money.abs().to_cents() for r in results))
    matched_money = Money.from_cents(
        sum(r.transaction.amount_money.abs().to_cents() for r in results if r.receipts)
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
