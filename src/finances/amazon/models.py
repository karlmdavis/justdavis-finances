#!/usr/bin/env python3
"""
Amazon Domain Models

Type-safe models representing Amazon Order History CSV data.
These models match the format of Amazon's Order History Reports CSV export.
"""

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from ..core.dates import FinancialDate
from ..core.money import Money

if TYPE_CHECKING:
    from ..ynab.models import YnabTransaction


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


@dataclass
class MatchedOrderItem:
    """
    Match-layer domain model for items used in split generation.

    Simplified from AmazonOrderItem - contains only fields needed for matching
    and split generation (no CSV-specific fields like order/ship dates).
    """

    name: str
    amount: Money
    quantity: int
    asin: str | None = None
    unit_price: Money | None = None

    @classmethod
    def from_order_item(cls, item: AmazonOrderItem) -> "MatchedOrderItem":
        """Create from full AmazonOrderItem (used by grouper)."""
        return cls(
            name=item.product_name,
            amount=item.total_owed,
            quantity=item.quantity,
            asin=item.asin,
            unit_price=item.unit_price,
        )

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "MatchedOrderItem":
        """Create from dict (used for JSON deserialization only)."""
        return cls(
            name=data.get("name", ""),
            amount=Money.from_cents(data.get("amount", 0)),
            quantity=data.get("quantity", 1),
            asin=data.get("asin"),
            unit_price=Money.from_cents(data["unit_price"]) if data.get("unit_price") is not None else None,
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dict for JSON serialization."""
        return {
            "name": self.name,
            "amount": self.amount.to_cents(),
            "quantity": self.quantity,
            "asin": self.asin,
            "unit_price": self.unit_price.to_cents() if self.unit_price is not None else None,
        }


@dataclass
class OrderGroup:
    """
    Group of items representing a matched order/shipment.

    Result of grouping AmazonOrderItems by order_id or shipment.
    Contains MatchedOrderItem instances (not full AmazonOrderItems).
    """

    order_id: str
    items: list[MatchedOrderItem]
    total: Money
    order_date: FinancialDate
    ship_dates: list[FinancialDate]
    grouping_level: str  # "order" or "shipment"

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "OrderGroup":
        """Create from dict (used for JSON deserialization only)."""
        items = [MatchedOrderItem.from_dict(item_dict) for item_dict in data.get("items", [])]
        ship_dates = [FinancialDate.from_string(d) for d in data.get("ship_dates", [])]

        return cls(
            order_id=data.get("order_id", ""),
            items=items,
            total=Money.from_cents(data.get("total", 0)),
            order_date=FinancialDate.from_string(data.get("order_date", "")),
            ship_dates=ship_dates,
            grouping_level=data.get("grouping_level", "order"),
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dict for JSON serialization."""
        return {
            "order_id": self.order_id,
            "items": [item.to_dict() for item in self.items],
            "total": self.total.to_cents(),
            "order_date": self.order_date.to_iso_string(),
            "ship_dates": [d.to_iso_string() for d in self.ship_dates],
            "grouping_level": self.grouping_level,
        }


@dataclass
class AmazonMatch:
    """
    Single Amazon match candidate for a YNAB transaction.

    Represents one possible match between a YNAB transaction and
    Amazon order(s), with confidence scoring and match method.

    Note: amazon_orders contains OrderGroup-like dicts (not raw AmazonOrderItem objects).
    Each dict has: order_id, items (list of MatchedOrderItem dicts), total, ship_dates, order_date
    """

    amazon_orders: list[dict[str, Any]]  # List of OrderGroup-like dicts
    match_method: str  # "complete_order", "complete_shipment", "split_payment", etc.
    confidence: float  # 0.0 to 1.0
    account: str  # Amazon account name (e.g., "karl", "erica")
    total_match_amount: Money  # Total amount matched

    # Optional fields
    unmatched_amount: Money = field(default_factory=lambda: Money.from_cents(0))  # For split payments
    matched_item_indices: list[int] = field(default_factory=list)  # For split payments
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Validate match data."""
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError(f"Confidence must be between 0.0 and 1.0, got {self.confidence}")
        if not self.amazon_orders:
            raise ValueError("AmazonMatch must have at least one order")

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AmazonMatch":
        """
        Create AmazonMatch from dict (for JSON deserialization).

        Args:
            data: Dictionary with match data

        Returns:
            AmazonMatch instance
        """
        return cls(
            amazon_orders=data["amazon_orders"],
            match_method=data["match_method"],
            confidence=float(data["confidence"]),
            account=data["account"],
            total_match_amount=Money.from_cents(data["total_match_amount"]),
            unmatched_amount=Money.from_cents(data.get("unmatched_amount", 0)),
            matched_item_indices=data.get("matched_item_indices", []),
            metadata=data.get("metadata", {}),
        )

    def to_dict(self) -> dict[str, Any]:
        """
        Convert to dict for JSON serialization.

        Returns:
            Dictionary with all match fields in JSON-compatible format
        """
        return {
            "account": self.account,
            "amazon_orders": self.amazon_orders,
            "match_method": self.match_method,
            "confidence": self.confidence,
            "total_match_amount": self.total_match_amount.to_cents(),
            "unmatched_amount": self.unmatched_amount.to_cents(),
            "matched_item_indices": self.matched_item_indices,
            "metadata": self.metadata,
        }


@dataclass
class AmazonMatchResult:
    """
    Result of matching a YNAB transaction against Amazon orders.

    Contains the YNAB transaction, all match candidates, the best match,
    and optional messaging about the match process.
    """

    transaction: "YnabTransaction"  # Forward reference to avoid circular import
    matches: list[AmazonMatch]  # All match candidates
    best_match: AmazonMatch | None  # Best match selected

    # Optional fields
    message: str | None = None  # e.g., "Not an Amazon transaction"
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def has_matches(self) -> bool:
        """Check if any matches were found."""
        return len(self.matches) > 0

    @property
    def match_count(self) -> int:
        """Get number of match candidates."""
        return len(self.matches)
