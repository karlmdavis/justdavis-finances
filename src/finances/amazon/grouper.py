#!/usr/bin/env python3
"""
Unified Order Grouping Module

Consolidates the three separate grouping functions into a single flexible system.
Provides multiple levels of Amazon order grouping for transaction matching.

Type Checking Notes:
--------------------
This module contains strategic type: ignore comments for pandas GroupBy operations.
These are necessary due to known limitations in pandas-stubs where:
- GroupBy.__iter__ returns overly broad Union types containing all possible pandas scalar types
- Dictionary access on group_summary returns Union types despite our known dict structure
- These are not actual type errors but rather limitations in pandas type stubs

All type: ignore comments are marked with specific error codes and explanations.
"""

from datetime import date
from enum import Enum
from typing import Any

import pandas as pd

from ..core.currency import safe_currency_to_cents


class GroupingLevel(Enum):
    """Different levels of order grouping"""

    ORDER = "order"  # Group complete orders
    SHIPMENT = "shipment"  # Group by order + exact ship datetime
    DAILY_SHIPMENT = "daily_shipment"  # Group by order + ship date (ignore time)


def group_orders(
    orders_df: pd.DataFrame, level: GroupingLevel = GroupingLevel.ORDER
) -> dict[str, dict[str, Any]] | list[dict[str, Any]]:
    """
    Universal order grouping function.

    Args:
        orders_df: DataFrame with order data
        level: Grouping level (ORDER, SHIPMENT, DAILY_SHIPMENT)

    Returns:
        For ORDER level: Dictionary of {order_id: order_data}
        For SHIPMENT/DAILY_SHIPMENT: List of shipment groups
    """
    if orders_df.empty:
        return {} if level == GroupingLevel.ORDER else []

    if level == GroupingLevel.ORDER:
        return _group_by_order_id(orders_df)
    elif level == GroupingLevel.SHIPMENT:
        return _group_by_shipment(orders_df)
    elif level == GroupingLevel.DAILY_SHIPMENT:
        return _group_by_daily_shipment(orders_df)
    else:
        raise ValueError(f"Unknown grouping level: {level}")


def _group_by_order_id(orders_df: pd.DataFrame) -> dict[str, dict[str, Any]]:
    """Group orders by Order ID and calculate totals."""
    grouped: dict[str, dict[str, Any]] = {}

    for order_id, group in orders_df.groupby("Order ID"):
        order_summary: dict[str, Any] = {
            "order_id": order_id,
            "items": [],
            "total": 0,
            "order_date": None,
            "ship_dates": [],
        }

        for _, row in group.iterrows():
            # Use Total Owed directly instead of calculating from unit price
            item_amount = safe_currency_to_cents(row.get("Total Owed", 0))

            # Still extract unit price for metadata (but convert properly)
            unit_price = safe_currency_to_cents(row.get("Unit Price", 0))
            quantity = int(row.get("Quantity", 1))

            item = {
                "name": row.get("Product Name", ""),
                "amount": item_amount,
                "ship_date": row.get("Ship Date"),
                "unit_price": unit_price,
                "quantity": quantity,
                "asin": row.get("ASIN", ""),
            }
            items_list: list[Any] = order_summary["items"]
            items_list.append(item)
            total_val: int = order_summary["total"]
            order_summary["total"] = total_val + item_amount

            # Track unique ship dates
            ship_date = row.get("Ship Date")
            ship_dates_list: list[Any] = order_summary["ship_dates"]
            if ship_date and ship_date not in ship_dates_list:
                ship_dates_list.append(ship_date)

        # Set order date (should be same for all items in order)
        order_summary["order_date"] = group.iloc[0].get("Order Date")
        ship_dates_list = order_summary["ship_dates"]
        order_summary["ship_dates"] = sorted(ship_dates_list)

        grouped[order_id] = order_summary

    return grouped


def _group_by_shipment(orders_df: pd.DataFrame) -> list[dict[str, Any]]:
    """Group orders by Order ID + exact Ship Date combination."""
    shipment_groups: list[dict[str, Any]] = []

    # Group by Order ID first, then by exact Ship Date within each order
    # pandas-stubs limitation: groupby iterator returns overly broad Union type
    for order_id, order_group in orders_df.groupby("Order ID"):
        for ship_date, shipment_group in order_group.groupby("Ship Date"):
            group_summary: dict[str, Any] = {
                "order_id": order_id,
                "ship_date": ship_date,
                "items": [],
                "total": 0,
                "order_date": shipment_group.iloc[0].get("Order Date"),
            }

            for _, row in shipment_group.iterrows():
                # Use Total Owed directly instead of calculating from unit price
                item_amount = safe_currency_to_cents(row.get("Total Owed", 0))

                # Still extract unit price for metadata (but convert properly)
                unit_price = safe_currency_to_cents(row.get("Unit Price", 0))
                quantity = int(row.get("Quantity", 1))

                item = {
                    "name": row.get("Product Name", ""),
                    "amount": item_amount,
                    "unit_price": unit_price,
                    "quantity": quantity,
                    "asin": row.get("ASIN", ""),
                }
                # pandas-stubs: dict access returns Union type despite our known structure
                group_summary["items"].append(item)
                group_summary["total"] += item_amount

            shipment_groups.append(group_summary)

    return shipment_groups


def _group_by_daily_shipment(orders_df: pd.DataFrame) -> list[dict[str, Any]]:
    """Group orders by Order ID + Ship Date (date only, ignoring time)."""
    # Add a date-only column for grouping
    orders_df = orders_df.copy()
    orders_df["Ship Date Only"] = orders_df["Ship Date"].dt.date

    shipment_groups: list[dict[str, Any]] = []

    # Group by Order ID first, then by Ship Date (date only) within each order
    # pandas-stubs limitation: groupby iterator returns overly broad Union type
    for order_id, order_group in orders_df.groupby("Order ID"):
        for ship_date_only, daily_group in order_group.groupby("Ship Date Only"):
            group_summary: dict[str, Any] = {
                "order_id": order_id,
                "ship_date": ship_date_only,  # Date only
                "items": [],
                "total": 0,
                "order_date": daily_group.iloc[0].get("Order Date"),
                "ship_times": [],  # Track different ship times within the day
            }

            for _, row in daily_group.iterrows():
                # Use Total Owed directly instead of calculating from unit price
                item_amount = safe_currency_to_cents(row.get("Total Owed", 0))

                # Still extract unit price for metadata (but convert properly)
                unit_price = safe_currency_to_cents(row.get("Unit Price", 0))
                quantity = int(row.get("Quantity", 1))

                item = {
                    "name": row.get("Product Name", ""),
                    "amount": item_amount,
                    "unit_price": unit_price,
                    "quantity": quantity,
                    "asin": row.get("ASIN", ""),
                }
                # pandas-stubs: dict access returns Union type despite our known structure
                group_summary["items"].append(item)
                group_summary["total"] += item_amount

                # Track different ship times within the day
                ship_time = row.get("Ship Date")
                if ship_time and ship_time not in group_summary["ship_times"]:
                    group_summary["ship_times"].append(ship_time)

            group_summary["ship_times"] = sorted(group_summary["ship_times"])
            shipment_groups.append(group_summary)

    return shipment_groups


def get_order_candidates(
    orders_df: pd.DataFrame, ynab_amount: int, ynab_date: date, tolerance: int = 100
) -> dict[str, list[dict[str, Any]]]:
    """
    Get order candidates at all grouping levels that could match the transaction.

    Args:
        orders_df: DataFrame with order data
        ynab_amount: Transaction amount in cents
        ynab_date: Transaction date
        tolerance: Amount tolerance in cents (default $1.00)

    Returns:
        Dictionary with candidates from each grouping level
    """
    candidates: dict[str, list[dict[str, Any]]] = {
        "complete_orders": [],
        "shipments": [],
        "daily_shipments": [],
    }

    # Try each grouping level
    for level in GroupingLevel:
        groups = group_orders(orders_df, level)

        if level == GroupingLevel.ORDER:
            # groups is a dict - pandas-stubs: Union type from group_orders return
            for order_data in groups.values():  # type: ignore[union-attr]
                amount_diff = abs(ynab_amount - order_data["total"])
                if amount_diff <= tolerance:
                    candidates["complete_orders"].append(
                        {**order_data, "amount_diff": amount_diff, "grouping_level": "order"}
                    )
        else:
            # groups is a list - pandas-stubs: Union type from group_orders return
            for group in groups:
                # pandas-stubs: group dict values return Union type despite our known structure
                amount_diff = abs(ynab_amount - group["total"])  # type: ignore[operator, index]
                if amount_diff <= tolerance:
                    level_name = "shipments" if level == GroupingLevel.SHIPMENT else "daily_shipments"
                    candidates[level_name].append(
                        {**group, "amount_diff": amount_diff, "grouping_level": level.value}  # type: ignore[dict-item]
                    )

    return candidates
