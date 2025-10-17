#!/usr/bin/env python3
"""
Amazon Transaction Matcher

Core matching engine that implements the 3-strategy system:
1. Complete Match - handles exact order/shipment matches
2. Split Payment - handles partial orders with exact item matches
3. Fuzzy Match - handles approximate matches with tolerances

All matches require penny-perfect amounts - no tolerance for differences.
"""

from datetime import date
from typing import Any

from ..core.currency import format_cents
from ..ynab.models import YnabTransaction
from .grouper import GroupingLevel, group_orders
from .models import AmazonMatchResult, AmazonOrderItem, OrderGroup
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
        self,
        transaction: YnabTransaction,
        orders_by_account: dict[str, list[AmazonOrderItem]],
    ) -> AmazonMatchResult:
        """
        Match a single YNAB transaction against Amazon order data.

        Args:
            transaction: YNAB transaction domain model
            orders_by_account: Dict of {account_name: list[AmazonOrderItem]}

        Returns:
            AmazonMatchResult with match details
        """
        # Check if this is an Amazon transaction
        if not self.is_amazon_transaction(transaction.payee_name or ""):
            return AmazonMatchResult(
                transaction=transaction,
                matches=[],
                best_match=None,
                message="Not an Amazon transaction",
            )

        # Convert transaction to internal format for matching
        ynab_amount_cents = transaction.amount.abs().to_cents()  # Use absolute value for matching
        ynab_date = transaction.date.date

        all_matches = []

        # Try matching against each account
        for account_name, orders in orders_by_account.items():
            if not orders:
                continue

            # Strategy 1: Complete Match
            complete_matches = self._find_complete_matches(ynab_amount_cents, ynab_date, orders, account_name)
            all_matches.extend(complete_matches)

            # Strategy 2: Split Payment
            split_matches = self._find_split_payment_matches(
                transaction, ynab_amount_cents, ynab_date, orders, account_name
            )
            all_matches.extend(split_matches)

        # Find best match
        best_match = self._select_best_match(all_matches)

        # Record split payment match if found
        if best_match and best_match["match_method"] == "split_payment":
            order = best_match["amazon_orders"][0]
            self.split_matcher.record_match(
                transaction.id, order["order_id"], order.get("matched_item_indices", [])
            )

        return AmazonMatchResult(
            transaction=transaction,
            matches=all_matches,
            best_match=best_match,
        )

    def _find_complete_matches(
        self, ynab_amount: int, ynab_date: date, orders: list[AmazonOrderItem], account_name: str
    ) -> list[dict[str, Any]]:
        """Find complete order/shipment matches using domain models."""
        matches = []

        # Group orders at ORDER level only (SHIPMENT/DAILY_SHIPMENT not yet implemented)
        order_groups_result = group_orders(orders, GroupingLevel.ORDER)
        # Type narrowing: ORDER level always returns dict[str, OrderGroup]
        if not isinstance(order_groups_result, dict):
            raise TypeError(f"ORDER level must return dict, got {type(order_groups_result)}")
        order_groups: dict[str, OrderGroup] = order_groups_result

        # order_groups is dict[str, OrderGroup] for ORDER level
        for order_group in order_groups.values():
            # Check for exact amount match
            amazon_total = order_group.total.to_cents()
            amount_diff = abs(ynab_amount - amazon_total)

            if amount_diff == 0:  # Exact match only
                # Calculate confidence
                ship_dates = [d.date for d in order_group.ship_dates]

                confidence = MatchScorer.calculate_confidence(
                    ynab_amount=ynab_amount,
                    amazon_total=amazon_total,
                    ynab_date=ynab_date,
                    amazon_ship_dates=ship_dates,
                    match_type=MatchType.COMPLETE_ORDER,
                    multi_day=len(ship_dates) > 1,
                )

                if ConfidenceThresholds.meets_threshold(confidence, MatchType.COMPLETE_ORDER):
                    # Convert OrderGroup to dict format for match result
                    # TODO: Update MatchScorer to accept OrderGroup directly
                    order_dict = order_group.to_dict()

                    match_result = MatchScorer.create_match_result(
                        ynab_tx={"amount": ynab_amount, "date": ynab_date},
                        amazon_orders=[order_dict],
                        match_method=f"complete_{order_group.grouping_level}",
                        confidence=confidence,
                        account=account_name,
                    )
                    matches.append(match_result)

        return matches

    def _find_split_payment_matches(
        self,
        transaction: YnabTransaction,
        ynab_amount: int,
        ynab_date: date,
        orders: list[AmazonOrderItem],
        account_name: str,
    ) -> list[dict[str, Any]]:
        """Find split payment matches using domain models."""
        matches: list[dict[str, Any]] = []

        # Group by complete orders to find candidates for split payments
        order_groups_result = group_orders(orders, GroupingLevel.ORDER)
        # Type narrowing: ORDER level always returns dict[str, OrderGroup]
        if not isinstance(order_groups_result, dict):
            raise TypeError(f"ORDER level must return dict, got {type(order_groups_result)}")
        order_groups: dict[str, OrderGroup] = order_groups_result

        # order_groups is dict[str, OrderGroup] for ORDER level
        for order_group in order_groups.values():
            # Convert OrderGroup to dict for split_matcher (legacy interface)
            # TODO: Update split_matcher to accept OrderGroup directly
            order_dict = order_group.to_dict()

            # Try split payment matching
            split_match = self.split_matcher.match_split_payment(
                ynab_tx={"amount": ynab_amount, "date": transaction.date.to_iso_string()},
                order_data=order_dict,
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
