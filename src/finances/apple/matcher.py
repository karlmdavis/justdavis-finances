#!/usr/bin/env python3
"""
Apple Transaction Matching Module

Core logic for matching Apple receipts to YNAB transactions.
Implements a simplified 2-strategy system optimized for Apple's 1:1 transaction model.
"""

from datetime import date, datetime, timedelta
from enum import Enum
from typing import Any, Optional, Union

import pandas as pd

from ..core.currency import format_cents, milliunits_to_cents
from ..core.models import MatchResult, Receipt, Transaction


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
        self, ynab_transaction: dict[str, Any], apple_receipts_df: pd.DataFrame
    ) -> MatchResult:
        """
        Match a single YNAB transaction to Apple receipts.

        Args:
            ynab_transaction: YNAB transaction data (normalized)
            apple_receipts_df: DataFrame of Apple receipts

        Returns:
            MatchResult with details of the match
        """
        # Convert YNAB transaction to internal format
        tx_amount_cents = milliunits_to_cents(ynab_transaction["amount"])
        tx_date = datetime.strptime(ynab_transaction["date"], "%Y-%m-%d")
        tx_id = ynab_transaction["id"]

        print(
            f"Matching transaction {tx_id}: {format_cents(tx_amount_cents)} on {tx_date.strftime('%Y-%m-%d')}"
        )

        # Create Transaction object
        transaction = Transaction(
            id=tx_id,
            date=tx_date.date(),
            amount=ynab_transaction["amount"],  # Keep original milliunits
            description=ynab_transaction.get("payee_name", ""),
            account_name=ynab_transaction.get("account_name", ""),
            memo=ynab_transaction.get("memo", ""),
            source="ynab",
        )

        # Strategy 1: Exact Date and Amount Match
        exact_match = self._find_exact_match(tx_date, tx_amount_cents, apple_receipts_df)
        if exact_match:
            receipt = self._create_receipt_from_data(exact_match)
            confidence = self._calculate_confidence(tx_amount_cents, exact_match["total"], 0)

            return MatchResult(
                transaction=transaction,
                receipts=[receipt],
                confidence=confidence,
                match_method="exact_date_amount",
                date_difference=0,
                amount_difference=0,
                strategy_used="exact_match",
            )

        # Strategy 2: Date Window Match
        window_match, date_diff = self._find_date_window_match(tx_date, tx_amount_cents, apple_receipts_df)
        if window_match:
            receipt = self._create_receipt_from_data(window_match)
            confidence = self._calculate_confidence(tx_amount_cents, window_match["total"], date_diff)

            return MatchResult(
                transaction=transaction,
                receipts=[receipt],
                confidence=confidence,
                match_method="date_window_match",
                date_difference=date_diff,
                amount_difference=0,
                strategy_used="date_window",
            )

        # No match found
        return MatchResult(
            transaction=transaction,
            receipts=[],
            confidence=0.0,
            match_method="no_match",
            unmatched_amount=tx_amount_cents,
            notes="no_matching_receipts_found",
        )

    def _find_exact_match(
        self, tx_date: datetime, tx_amount: int, receipts_df: pd.DataFrame
    ) -> Optional[dict[str, Any]]:
        """
        Find receipts that match exactly on date and amount.

        Args:
            tx_date: Transaction date
            tx_amount: Transaction amount in cents
            receipts_df: DataFrame of Apple receipts

        Returns:
            Matching receipt dictionary or None
        """
        if receipts_df.empty:
            return None

        # Filter to same date
        same_date_mask = receipts_df["receipt_date"].dt.date == tx_date.date()
        same_date_receipts = receipts_df[same_date_mask]

        if same_date_receipts.empty:
            return None

        # Find exact amount matches
        for _, receipt in same_date_receipts.iterrows():
            if receipt["total"] == tx_amount:
                print(
                    f"  Found exact match: Receipt {receipt['order_id']} for {format_cents(receipt['total'])}"
                )
                receipt_dict: dict[str, Any] = receipt.to_dict()
                return receipt_dict

        return None

    def _find_date_window_match(
        self, tx_date: datetime, tx_amount: int, receipts_df: pd.DataFrame
    ) -> tuple[Optional[dict[str, Any]], int]:
        """
        Find receipts within the date window that match the amount.

        Args:
            tx_date: Transaction date
            tx_amount: Transaction amount in cents
            receipts_df: DataFrame of Apple receipts

        Returns:
            Tuple of (matching receipt dictionary or None, date difference in days)
        """
        if receipts_df.empty:
            return None, 0

        # Define date window
        start_date = tx_date - timedelta(days=self.date_window_days)
        end_date = tx_date + timedelta(days=self.date_window_days)

        # Filter to date window
        date_mask = (receipts_df["receipt_date"] >= start_date) & (receipts_df["receipt_date"] <= end_date)
        window_receipts = receipts_df[date_mask]

        if window_receipts.empty:
            return None, 0

        # Find amount matches, prioritizing closer dates
        best_match = None
        best_date_diff = 999999  # Large integer instead of float('inf')

        for _, receipt in window_receipts.iterrows():
            if receipt["total"] == tx_amount:
                date_diff = abs((receipt["receipt_date"] - tx_date).days)
                if date_diff < best_date_diff:
                    best_match = receipt.to_dict()
                    best_date_diff = date_diff

        if best_match:
            print(
                f"  Found date window match: Receipt {best_match['order_id']} for {format_cents(best_match['total'])}, {best_date_diff} days off"
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

    def _create_receipt_from_data(self, receipt_data: dict[str, Any]) -> Receipt:
        """
        Create a Receipt object from raw receipt data.

        Args:
            receipt_data: Raw receipt data dictionary

        Returns:
            Receipt object
        """
        receipt_date_raw = receipt_data.get("receipt_date")
        receipt_date: Union[date, str]
        if isinstance(receipt_date_raw, str):
            receipt_date = datetime.strptime(receipt_date_raw, "%Y-%m-%d").date()
        elif receipt_date_raw is not None and hasattr(receipt_date_raw, "date"):
            receipt_date = receipt_date_raw.date()
        else:
            # Fallback to empty string if date is None
            receipt_date = ""

        return Receipt(
            id=receipt_data.get("order_id", ""),
            date=receipt_date,
            vendor="Apple",
            total_amount=receipt_data.get("total", 0),
            subtotal=receipt_data.get("subtotal"),
            tax_amount=receipt_data.get("tax"),
            customer_id=receipt_data.get("apple_id", ""),
            order_number=receipt_data.get("document_number", ""),
            items=receipt_data.get("items", []),
            source="apple_email",
            raw_data=receipt_data,
        )


def batch_match_transactions(
    ynab_transactions_df: pd.DataFrame,
    apple_receipts_df: pd.DataFrame,
    matcher: Optional[AppleMatcher] = None,
) -> list[MatchResult]:
    """
    Match a batch of YNAB transactions to Apple receipts.

    Args:
        ynab_transactions_df: DataFrame of YNAB transactions
        apple_receipts_df: DataFrame of Apple receipts
        matcher: Optional AppleMatcher instance

    Returns:
        List of MatchResult objects
    """
    if matcher is None:
        matcher = AppleMatcher()

    results = []

    print(
        f"Matching {len(ynab_transactions_df)} YNAB transactions to {len(apple_receipts_df)} Apple receipts"
    )

    for _, transaction in ynab_transactions_df.iterrows():
        tx_dict = transaction.to_dict()
        result = matcher.match_single_transaction(tx_dict, apple_receipts_df)
        results.append(result)

    return results


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

    # Calculate amounts
    total_amount = sum(milliunits_to_cents(r.transaction.amount) for r in results)
    matched_amount = sum(milliunits_to_cents(r.transaction.amount) for r in results if r.receipts)
    unmatched_amount = total_amount - matched_amount

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
