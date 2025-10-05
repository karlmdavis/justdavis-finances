#!/usr/bin/env python3
"""
Amazon Transaction Matcher

Core matching engine that implements the 3-strategy system:
1. Complete Match - handles exact order/shipment matches
2. Split Payment - handles partial orders with exact item matches
3. Fuzzy Match - handles approximate matches with tolerances

All matches require penny-perfect amounts - no tolerance for differences.
"""

from datetime import date, datetime
from typing import Any

import pandas as pd

from ..core.currency import format_cents, milliunits_to_cents
from .grouper import GroupingLevel, get_order_candidates, group_orders
from .scorer import ConfidenceThresholds, MatchScorer, MatchType
from .split_matcher import SplitPaymentMatcher


class SimplifiedMatcher:
    """
    Simplified Amazon transaction matcher with 3-strategy system.
    Focuses on exact matches only for reliability.
    """

    def __init__(self, split_cache_file: str | None = None):
        """
        Initialize the matcher.

        Args:
            split_cache_file: Optional file path for persistent split payment tracking
        """
        self.split_matcher = SplitPaymentMatcher(split_cache_file)

    def is_amazon_transaction(self, payee_name: str) -> bool:
        """Check if payee name matches Amazon patterns."""
        if not payee_name:
            return False

        patterns = ["amazon", "amzn"]
        payee_lower = payee_name.lower()
        return any(pattern in payee_lower for pattern in patterns)

    def match_transaction(
        self, ynab_tx: dict[str, Any], account_data: dict[str, tuple[pd.DataFrame, pd.DataFrame]]
    ) -> dict[str, Any]:
        """
        Match a single YNAB transaction against Amazon order data.

        Args:
            ynab_tx: YNAB transaction data with id, amount, date, payee_name
            account_data: Dict of {account_name: (retail_df, digital_df)}

        Returns:
            Match result with transaction, matches, and best_match
        """
        # Convert YNAB amount to cents
        ynab_amount_cents = milliunits_to_cents(ynab_tx["amount"])
        ynab_date = datetime.strptime(ynab_tx["date"], "%Y-%m-%d").date()

        # Check if this is an Amazon transaction
        if not self.is_amazon_transaction(ynab_tx.get("payee_name", "")):
            return {
                "ynab_transaction": {
                    "id": ynab_tx["id"],
                    "amount": ynab_amount_cents,
                    "date": ynab_tx["date"],
                    "payee_name": ynab_tx.get("payee_name", ""),
                    "memo": ynab_tx.get("memo", ""),
                },
                "matches": [],
                "best_match": None,
                "message": "Not an Amazon transaction",
            }

        all_matches = []

        # Try matching against each account
        for account_name, (retail_df, _digital_df) in account_data.items():
            if retail_df.empty:
                continue

            # Strategy 1: Complete Match
            complete_matches = self._find_complete_matches(
                ynab_amount_cents, ynab_date, retail_df, account_name
            )
            all_matches.extend(complete_matches)

            # Strategy 2: Split Payment
            split_matches = self._find_split_payment_matches(
                ynab_tx, ynab_amount_cents, ynab_date, retail_df, account_name
            )
            all_matches.extend(split_matches)

        # Find best match
        best_match = self._select_best_match(all_matches)

        # Record split payment match if found
        if best_match and best_match["match_method"] == "split_payment":
            order = best_match["amazon_orders"][0]
            self.split_matcher.record_match(
                ynab_tx["id"], order["order_id"], order.get("matched_item_indices", [])
            )

        return {
            "ynab_transaction": {
                "id": ynab_tx["id"],
                "amount": ynab_amount_cents,
                "date": ynab_tx["date"],
                "payee_name": ynab_tx.get("payee_name", ""),
                "memo": ynab_tx.get("memo", ""),
            },
            "matches": all_matches,
            "best_match": best_match,
        }

    def _find_complete_matches(
        self, ynab_amount: int, ynab_date: date, orders_df: pd.DataFrame, account_name: str
    ) -> list[dict[str, Any]]:
        """Find complete order/shipment matches."""
        matches = []

        # Get candidates at all grouping levels
        candidates = get_order_candidates(orders_df, ynab_amount, ynab_date, tolerance=0)

        # Process each candidate type
        for candidate_list in candidates.values():
            for candidate in candidate_list:
                if candidate["amount_diff"] == 0:  # Exact match only
                    # Calculate confidence
                    ship_dates = candidate.get("ship_dates", [candidate.get("ship_date")])
                    ship_dates = [d for d in ship_dates if d is not None]

                    confidence = MatchScorer.calculate_confidence(
                        ynab_amount=ynab_amount,
                        amazon_total=candidate["total"],
                        ynab_date=ynab_date,
                        amazon_ship_dates=ship_dates,
                        match_type=MatchType.COMPLETE_ORDER,
                        multi_day=len(ship_dates) > 1,
                    )

                    if ConfidenceThresholds.meets_threshold(confidence, MatchType.COMPLETE_ORDER):
                        match_result = MatchScorer.create_match_result(
                            ynab_tx={"amount": ynab_amount, "date": ynab_date},
                            amazon_orders=[candidate],
                            match_method=f"complete_{candidate['grouping_level']}",
                            confidence=confidence,
                            account=account_name,
                        )
                        matches.append(match_result)

        return matches

    def _find_split_payment_matches(
        self, ynab_tx: dict, ynab_amount: int, ynab_date: date, orders_df: pd.DataFrame, account_name: str
    ) -> list[dict[str, Any]]:
        """Find split payment matches."""
        matches: list[dict[str, Any]] = []

        # Group by complete orders to find candidates for split payments
        complete_orders = group_orders(orders_df, GroupingLevel.ORDER)

        # complete_orders is always a dict when using GroupingLevel.ORDER
        if not isinstance(complete_orders, dict):
            return matches

        for order_data in complete_orders.values():
            # Try split payment matching
            split_match = self.split_matcher.match_split_payment(
                ynab_tx={"amount": ynab_amount, "date": ynab_tx["date"]},
                order_data=order_data,
                account_name=account_name,
            )

            if split_match and ConfidenceThresholds.meets_threshold(
                split_match["confidence"], MatchType.SPLIT_PAYMENT
            ):
                matches.append(split_match)

        return matches

    def _select_best_match(self, matches: list[dict[str, Any]]) -> dict[str, Any] | None:
        """Select the best match from available options."""
        if not matches:
            return None

        # Sort by confidence (highest first), then by match method preference
        def match_priority(match: dict[str, Any]) -> float:
            confidence = float(match["confidence"])
            method = match["match_method"]

            # Complete matches get priority over split payments
            if method.startswith("complete_"):
                priority = 1000
            elif method == "split_payment":
                priority = 500
            else:
                priority = 100

            return confidence + priority / 10000  # Small boost for method preference

        sorted_matches = sorted(matches, key=match_priority, reverse=True)
        return sorted_matches[0]

    def convert_match_result_for_json(self, result: dict[str, Any]) -> dict[str, Any]:
        """Convert match result with cent amounts to JSON-safe format with string amounts."""
        import copy

        json_result = copy.deepcopy(result)

        # Convert YNAB transaction amount
        if "ynab_transaction" in json_result and "amount" in json_result["ynab_transaction"]:
            amount_cents = json_result["ynab_transaction"]["amount"]
            json_result["ynab_transaction"]["amount"] = format_cents(amount_cents)

        # Convert match amounts
        if "matches" in json_result:
            for match in json_result["matches"]:
                self._convert_match_amounts(match)

        # Convert best_match amounts
        if json_result.get("best_match"):
            self._convert_match_amounts(json_result["best_match"])

        return json_result

    def _convert_match_amounts(self, match: dict[str, Any]) -> None:
        """Convert amounts in a single match to formatted strings."""
        if "total_match_amount" in match:
            match["total_match_amount"] = format_cents(match["total_match_amount"])
        if "unmatched_amount" in match:
            match["unmatched_amount"] = format_cents(match["unmatched_amount"])

        if "amazon_orders" in match:
            for order in match["amazon_orders"]:
                if "total" in order:
                    order["total"] = format_cents(order["total"])
                if "items" in order:
                    for item in order["items"]:
                        if "amount" in item:
                            item["amount"] = format_cents(item["amount"])
                        if "unit_price" in item:
                            item["unit_price"] = format_cents(item["unit_price"])
