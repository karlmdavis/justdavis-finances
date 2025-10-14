#!/usr/bin/env python3
"""
Amazon Domain Models

Type-safe models representing Amazon Order History CSV data.
These models match the format of Amazon's Order History Reports CSV export.
"""

from dataclasses import dataclass
from typing import Any

from ..core.dates import FinancialDate
from ..core.money import Money


@dataclass
class AmazonOrderItem:
    """
    Single line item from Amazon Order History CSV.

    Represents one row from the Retail.OrderHistory CSV export.
    Each row is a single item within an order (orders can have multiple items).
    """

    # Core identifiers
    order_id: str
    asin: str  # Amazon Standard Identification Number

    # Product information
    product_name: str
    quantity: int

    # Financial data
    unit_price: Money  # Price per unit
    total_owed: Money  # Total amount for this line item (includes tax, shipping allocation)

    # Dates
    order_date: FinancialDate
    ship_date: FinancialDate | None

    # Optional fields (may not be present in all CSV formats)
    category: str | None = None
    seller: str | None = None
    condition: str | None = None

    @classmethod
    def from_csv_row(cls, row: dict[str, Any]) -> "AmazonOrderItem":
        """
        Create AmazonOrderItem from CSV row dict.

        Args:
            row: Dictionary representing one CSV row (pandas row.to_dict() or similar)

        Returns:
            AmazonOrderItem instance

        Note:
            - Handles both string and datetime types for dates
            - Uses safe_currency_to_cents for monetary values
            - Gracefully handles missing optional fields
        """
        from ..core.currency import safe_currency_to_cents

        # Parse order date (required)
        order_date_val = row.get("Order Date")
        if isinstance(order_date_val, str):
            order_date = FinancialDate.from_string(order_date_val)
        elif order_date_val is not None:
            # Assume it's already a datetime/date object
            order_date = FinancialDate(date=order_date_val)
        else:
            raise ValueError("Order Date is required but was None")

        # Parse ship date (optional)
        ship_date_val = row.get("Ship Date")
        if ship_date_val is None or (isinstance(ship_date_val, str) and not ship_date_val):
            ship_date = None
        elif isinstance(ship_date_val, str):
            ship_date = FinancialDate.from_string(ship_date_val)
        else:
            ship_date = FinancialDate(date=ship_date_val)

        # Parse monetary values
        unit_price_cents = safe_currency_to_cents(row.get("Unit Price", 0))
        total_owed_cents = safe_currency_to_cents(row.get("Total Owed", 0))

        return cls(
            order_id=str(row.get("Order ID", "")),
            asin=str(row.get("ASIN", "")),
            product_name=str(row.get("Product Name", "")),
            quantity=int(row.get("Quantity", 1)),
            unit_price=Money.from_cents(unit_price_cents),
            total_owed=Money.from_cents(total_owed_cents),
            order_date=order_date,
            ship_date=ship_date,
            category=row.get("Category"),
            seller=row.get("Seller"),
            condition=row.get("Condition"),
        )

    @property
    def total_price(self) -> Money:
        """
        Get total price for this line item.

        This is the amount Amazon actually charged (includes tax and shipping allocation).
        """
        return self.total_owed

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization or DataFrame creation."""
        return {
            "Order ID": self.order_id,
            "ASIN": self.asin,
            "Product Name": self.product_name,
            "Quantity": self.quantity,
            "Unit Price": self.unit_price.to_cents(),
            "Total Owed": self.total_owed.to_cents(),
            "Order Date": self.order_date.to_iso_string(),
            "Ship Date": self.ship_date.to_iso_string() if self.ship_date else None,
            "Category": self.category,
            "Seller": self.seller,
            "Condition": self.condition,
        }


@dataclass
class AmazonOrderSummary:
    """
    Summary of a complete Amazon order (potentially multiple items).

    This represents an aggregated view of all items in a single order,
    used for transaction matching.
    """

    order_id: str
    order_date: FinancialDate
    items: list[AmazonOrderItem]
    total_amount: Money
    ship_dates: list[FinancialDate]

    @classmethod
    def from_items(cls, order_id: str, items: list[AmazonOrderItem]) -> "AmazonOrderSummary":
        """
        Create order summary from a list of items.

        Args:
            order_id: Amazon order ID
            items: List of items in this order

        Returns:
            AmazonOrderSummary with aggregated data
        """
        if not items:
            raise ValueError("Cannot create order summary from empty items list")

        # All items should have same order date
        order_date = items[0].order_date

        # Calculate total from all items
        total_amount = Money.from_cents(0)
        for item in items:
            total_amount = total_amount + item.total_owed

        # Collect unique ship dates (excluding None)
        ship_dates_set: set[FinancialDate] = set()
        for item in items:
            if item.ship_date:
                ship_dates_set.add(item.ship_date)

        ship_dates = sorted(ship_dates_set, key=lambda d: d.to_iso_string())

        return cls(
            order_id=order_id,
            order_date=order_date,
            items=items,
            total_amount=total_amount,
            ship_dates=ship_dates,
        )

    @property
    def item_count(self) -> int:
        """Get total number of items in this order."""
        return len(self.items)

    @property
    def item_names(self) -> list[str]:
        """Get list of all product names in this order."""
        return [item.product_name for item in self.items]
