#!/usr/bin/env python3
"""
Unified Match Scoring System

Consolidates confidence calculation logic into a single, consistent system.
Provides match scoring for Amazon transaction matching with precise calculations.
"""

from datetime import date
from enum import Enum
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .models import AmazonMatch


class MatchType(Enum):
    """Types of matches for scoring"""

    COMPLETE_ORDER = "complete_order"
    SPLIT_PAYMENT = "split_payment"


class MatchScorer:
    """Unified match scoring system"""

    @staticmethod
    def calculate_confidence(
        ynab_amount: int,
        amazon_total: int,
        ynab_date: date,
        amazon_ship_dates: list[Any],
        match_type: MatchType,
        **kwargs: Any,
    ) -> float:
        """
        Calculate match confidence score (0.0 to 1.0).

        Args:
            ynab_amount: YNAB transaction amount in cents (positive)
            amazon_total: Amazon order/group total in cents
            ynab_date: YNAB transaction date
            amazon_ship_dates: List of ship dates for the Amazon order/group
            match_type: Type of match being scored
            **kwargs: Additional parameters for specific match types

        Returns:
            Confidence score between 0.0 and 1.0
        """
        # Base confidence
        confidence = 1.0

        # Amount accuracy scoring
        amount_diff = abs(ynab_amount - amazon_total)
        confidence *= MatchScorer._score_amount_accuracy(amount_diff, ynab_amount, match_type)

        # Date alignment scoring
        min_date_diff = MatchScorer._get_min_date_diff(ynab_date, amazon_ship_dates)
        confidence *= MatchScorer._score_date_alignment(min_date_diff, amount_diff, match_type)

        # Match type specific adjustments
        confidence *= MatchScorer._apply_match_type_adjustments(match_type, **kwargs)

        # Apply confidence floor and ceiling
        confidence = max(0.0, min(1.0, confidence))

        return round(confidence, 2)

    @staticmethod
    def _score_amount_accuracy(amount_diff: int, ynab_amount: int, match_type: MatchType) -> float:
        """Score based on amount accuracy - exact matches only"""
        if amount_diff == 0:
            return 1.0
        else:
            # No match allowed for any non-zero amount difference
            return 0.0

    @staticmethod
    def _get_min_date_diff(ynab_date: date, amazon_ship_dates: list) -> int:
        """Get minimum date difference in days"""
        if not amazon_ship_dates:
            return 7  # Default penalty for missing dates

        date_diffs = []
        for ship_date in amazon_ship_dates:
            # Handle various date formats
            try:
                if hasattr(ship_date, "date"):
                    ship_date = ship_date.date()
                elif isinstance(ship_date, str):
                    from datetime import datetime

                    ship_date = datetime.strptime(ship_date, "%Y-%m-%d").date()

                date_diffs.append(abs((ynab_date - ship_date).days))
            except (ValueError, TypeError, AttributeError):
                # Skip malformed dates - fall back to minimum from valid dates or default penalty
                continue

        return min(date_diffs) if date_diffs else 7

    @staticmethod
    def _score_date_alignment(date_diff: int, amount_diff: int, match_type: MatchType) -> float:
        """Score based on date alignment"""
        # Exact amounts get more lenient date scoring
        is_exact_amount = amount_diff <= 100

        if date_diff == 0:
            return 1.0
        elif date_diff == 1:
            return 0.98
        elif date_diff == 2:
            return 0.95 if is_exact_amount else 0.90
        elif date_diff <= 3:
            return 0.90 if is_exact_amount else 0.85
        elif date_diff <= 5:
            return 0.85 if is_exact_amount else 0.75
        elif date_diff <= 7:
            return 0.80 if is_exact_amount else 0.65
        else:
            # Steep penalty for dates too far apart
            # Use integer arithmetic to avoid floating point: 0.8 - (date_diff - 7) * 0.1
            penalty_basis = 80 - (date_diff - 7) * 10  # Scale by 100 to avoid decimals
            penalty_result = max(30, penalty_basis)  # 30 = 0.3 * 100
            return penalty_result / 100  # Convert back for compatibility

    @staticmethod
    def _apply_match_type_adjustments(match_type: MatchType, **kwargs: Any) -> float:
        """Apply match type specific confidence adjustments"""
        if match_type == MatchType.COMPLETE_ORDER:
            # Complete orders get slight boost for being simpler/more reliable
            multi_day = kwargs.get("multi_day", False)
            if multi_day:
                return 1.05  # Multi-day orders are more complex but reliable when matched
            else:
                return 1.0

        elif match_type == MatchType.SPLIT_PAYMENT:
            # Split payments get slight penalty for being more complex
            return 0.95

        # This line is unreachable but mypy doesn't recognize the else after elif
        return 1.0  # type: ignore[unreachable]

    @staticmethod
    def create_match_result(
        ynab_tx: dict[str, Any],
        amazon_orders: list,
        match_method: str,
        confidence: float,
        account: str,
        unmatched_amount: int = 0,
    ) -> "AmazonMatch":
        """
        Create standardized match result structure.

        Args:
            ynab_tx: YNAB transaction data
            amazon_orders: List of matched Amazon orders (OrderGroup dicts)
            match_method: Method used for matching
            confidence: Calculated confidence score
            account: Amazon account name
            unmatched_amount: Amount not matched (for partial matches) in cents

        Returns:
            AmazonMatch domain model instance
        """
        from ..core.money import Money
        from .models import AmazonMatch

        total_match_amount = sum(order.get("total", 0) for order in amazon_orders)

        return AmazonMatch(
            account=account,
            amazon_orders=amazon_orders,
            match_method=match_method,
            confidence=confidence,
            total_match_amount=Money.from_cents(total_match_amount),
            unmatched_amount=Money.from_cents(unmatched_amount),
        )


class ConfidenceThresholds:
    """Confidence thresholds for different match types"""

    # Minimum confidence required for each match type
    COMPLETE_MATCH_MIN = 0.75
    SPLIT_PAYMENT_MIN = 0.65

    # High confidence thresholds
    HIGH_CONFIDENCE = 0.90
    MEDIUM_CONFIDENCE = 0.75

    @staticmethod
    def meets_threshold(confidence: float, match_type: MatchType) -> bool:
        """Check if confidence meets minimum threshold for match type"""
        thresholds = {
            MatchType.COMPLETE_ORDER: ConfidenceThresholds.COMPLETE_MATCH_MIN,
            MatchType.SPLIT_PAYMENT: ConfidenceThresholds.SPLIT_PAYMENT_MIN,
        }

        return confidence >= thresholds.get(match_type, 0.60)
