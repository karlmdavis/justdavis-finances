#!/usr/bin/env python3
"""
Unified Order Grouping Module

Consolidates the three separate grouping functions into a single flexible system.
Provides multiple levels of Amazon order grouping for transaction matching.
"""

from collections import defaultdict
from enum import Enum

from ..core.money import Money
from .models import AmazonOrderItem, MatchedOrderItem, OrderGroup


class GroupingLevel(Enum):
    """Different levels of order grouping"""

    ORDER = "order"  # Group complete orders
    SHIPMENT = "shipment"  # Group by order + exact ship datetime
    DAILY_SHIPMENT = "daily_shipment"  # Group by order + ship date (ignore time)


def group_orders(
    orders: list[AmazonOrderItem], level: GroupingLevel = GroupingLevel.ORDER
) -> dict[str, OrderGroup] | list[OrderGroup]:
    """
    Universal order grouping function.

    Args:
        orders: List of AmazonOrderItem domain models
        level: Grouping level (ORDER, SHIPMENT, DAILY_SHIPMENT)

    Returns:
        For ORDER level: Dictionary of {order_id: OrderGroup}
        For SHIPMENT/DAILY_SHIPMENT: List of OrderGroup objects
    """
    if not orders:
        return {} if level == GroupingLevel.ORDER else []

    if level == GroupingLevel.ORDER:
        return _group_by_order_id(orders)
    elif level == GroupingLevel.SHIPMENT:
        return _group_by_shipment(orders)
    elif level == GroupingLevel.DAILY_SHIPMENT:
        return _group_by_daily_shipment(orders)
    else:
        raise ValueError(f"Unknown grouping level: {level}")


def _group_by_order_id(orders: list[AmazonOrderItem]) -> dict[str, OrderGroup]:
    """Group orders by Order ID and calculate totals using domain models."""
    groups: dict[str, list[AmazonOrderItem]] = defaultdict(list)

    # Group items by order_id
    for item in orders:
        groups[item.order_id].append(item)

    # Create OrderGroup objects for each order
    result: dict[str, OrderGroup] = {}
    for order_id, items in groups.items():
        # Convert to MatchedOrderItem objects
        matched_items: list[MatchedOrderItem] = [MatchedOrderItem.from_order_item(item) for item in items]

        # Calculate total
        total = Money.from_cents(0)
        for matched_item in matched_items:
            total = total + matched_item.amount

        # Collect unique ship dates (excluding None)
        ship_dates_set = {item.ship_date for item in items if item.ship_date}
        ship_dates = sorted(ship_dates_set, key=lambda d: d.to_iso_string())

        # All items should have same order date
        order_date = items[0].order_date

        result[order_id] = OrderGroup(
            order_id=order_id,
            items=matched_items,
            total=total,
            order_date=order_date,
            ship_dates=ship_dates,
            grouping_level="order",
        )

    return result


def _group_by_shipment(orders: list[AmazonOrderItem]) -> list[OrderGroup]:
    """Group orders by Order ID + exact Ship Date combination."""
    # TODO(#15): Implement shipment-level grouping with domain models
    # See https://github.com/karlmdavis/justdavis-finances/issues/15
    raise NotImplementedError("Shipment-level grouping not yet implemented with domain models")


def _group_by_daily_shipment(orders: list[AmazonOrderItem]) -> list[OrderGroup]:
    """Group orders by Order ID + Ship Date (date only, ignoring time)."""
    # TODO(#15): Implement daily shipment-level grouping with domain models
    # See https://github.com/karlmdavis/justdavis-finances/issues/15
    raise NotImplementedError("Daily shipment-level grouping not yet implemented with domain models")
