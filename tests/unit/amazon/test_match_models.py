#!/usr/bin/env python3
"""
Unit tests for Amazon match-layer domain models.

Tests MatchedOrderItem and OrderGroup models used in matching pipeline.
"""


from finances.amazon.models import AmazonOrderItem, MatchedOrderItem, OrderGroup
from finances.core import FinancialDate, Money


class TestMatchedOrderItem:
    """Tests for MatchedOrderItem domain model."""

    def test_from_order_item_minimal_fields(self):
        """Test creating MatchedOrderItem from AmazonOrderItem with minimal fields."""
        # Arrange
        order_item = AmazonOrderItem(
            order_id="123-456",
            asin="B0123456",
            product_name="Test Product",
            quantity=1,
            unit_price=Money.from_cents(1999),
            total_owed=Money.from_cents(1999),
            order_date=FinancialDate.from_string("2024-01-15"),
            ship_date=FinancialDate.from_string("2024-01-16"),
        )

        # Act
        matched = MatchedOrderItem.from_order_item(order_item)

        # Assert
        assert matched.name == "Test Product"
        assert matched.amount == Money.from_cents(1999)
        assert matched.quantity == 1
        assert matched.asin == "B0123456"
        assert matched.unit_price == Money.from_cents(1999)

    def test_from_order_item_with_none_asin(self):
        """Test creating MatchedOrderItem when ASIN is None."""
        # Arrange
        order_item = AmazonOrderItem(
            order_id="123-456",
            asin=None,
            product_name="Test Product",
            quantity=2,
            unit_price=Money.from_cents(500),
            total_owed=Money.from_cents(1000),
            order_date=FinancialDate.from_string("2024-01-15"),
            ship_date=None,
        )

        # Act
        matched = MatchedOrderItem.from_order_item(order_item)

        # Assert
        assert matched.asin is None
        assert matched.quantity == 2

    def test_from_dict_complete(self):
        """Test creating MatchedOrderItem from dict (JSON deserialization)."""
        # Arrange
        data = {
            "name": "Product Name",
            "amount": 2499,  # cents
            "quantity": 1,
            "asin": "B0987654",
            "unit_price": 2499,
        }

        # Act
        matched = MatchedOrderItem.from_dict(data)

        # Assert
        assert matched.name == "Product Name"
        assert matched.amount == Money.from_cents(2499)
        assert matched.quantity == 1
        assert matched.asin == "B0987654"
        assert matched.unit_price == Money.from_cents(2499)

    def test_from_dict_minimal(self):
        """Test creating MatchedOrderItem from dict with minimal fields."""
        # Arrange
        data = {
            "name": "Product Name",
            "amount": 1500,
            "quantity": 3,
        }

        # Act
        matched = MatchedOrderItem.from_dict(data)

        # Assert
        assert matched.name == "Product Name"
        assert matched.amount == Money.from_cents(1500)
        assert matched.quantity == 3
        assert matched.asin is None
        assert matched.unit_price is None

    def test_to_dict(self):
        """Test serializing MatchedOrderItem to dict."""
        # Arrange
        matched = MatchedOrderItem(
            name="Product",
            amount=Money.from_cents(999),
            quantity=2,
            asin="B0111111",
            unit_price=Money.from_cents(999),
        )

        # Act
        result = matched.to_dict()

        # Assert
        assert result == {
            "name": "Product",
            "amount": 999,
            "quantity": 2,
            "asin": "B0111111",
            "unit_price": 999,
        }

    def test_to_dict_with_none_values(self):
        """Test serializing MatchedOrderItem with None values."""
        # Arrange
        matched = MatchedOrderItem(
            name="Product",
            amount=Money.from_cents(500),
            quantity=1,
            asin=None,
            unit_price=None,
        )

        # Act
        result = matched.to_dict()

        # Assert
        assert result == {
            "name": "Product",
            "amount": 500,
            "quantity": 1,
            "asin": None,
            "unit_price": None,
        }


class TestOrderGroup:
    """Tests for OrderGroup domain model."""

    def test_create_order_group(self):
        """Test creating an OrderGroup."""
        # Arrange
        items = [
            MatchedOrderItem(
                name="Item 1",
                amount=Money.from_cents(1000),
                quantity=1,
                asin="B01",
                unit_price=Money.from_cents(1000),
            ),
            MatchedOrderItem(
                name="Item 2",
                amount=Money.from_cents(500),
                quantity=2,
                asin="B02",
                unit_price=Money.from_cents(250),
            ),
        ]

        # Act
        group = OrderGroup(
            order_id="123-456",
            items=items,
            total=Money.from_cents(1500),
            order_date=FinancialDate.from_string("2024-01-15"),
            ship_dates=[FinancialDate.from_string("2024-01-16")],
            grouping_level="order",
        )

        # Assert
        assert group.order_id == "123-456"
        assert len(group.items) == 2
        assert group.total == Money.from_cents(1500)
        assert group.order_date == FinancialDate.from_string("2024-01-15")
        assert len(group.ship_dates) == 1
        assert group.grouping_level == "order"

    def test_order_group_to_dict(self):
        """Test serializing OrderGroup to dict."""
        # Arrange
        items = [
            MatchedOrderItem(
                name="Item",
                amount=Money.from_cents(999),
                quantity=1,
                asin="B01",
                unit_price=Money.from_cents(999),
            )
        ]
        group = OrderGroup(
            order_id="123-456",
            items=items,
            total=Money.from_cents(999),
            order_date=FinancialDate.from_string("2024-01-15"),
            ship_dates=[FinancialDate.from_string("2024-01-16")],
            grouping_level="order",
        )

        # Act
        result = group.to_dict()

        # Assert
        assert result["order_id"] == "123-456"
        assert len(result["items"]) == 1
        assert result["items"][0]["name"] == "Item"
        assert result["total"] == 999
        assert result["order_date"] == "2024-01-15"
        assert result["ship_dates"] == ["2024-01-16"]
        assert result["grouping_level"] == "order"

    def test_order_group_from_dict(self):
        """Test deserializing OrderGroup from dict."""
        # Arrange
        data = {
            "order_id": "789-012",
            "items": [
                {
                    "name": "Product A",
                    "amount": 1200,
                    "quantity": 1,
                    "asin": "B0A",
                    "unit_price": 1200,
                }
            ],
            "total": 1200,
            "order_date": "2024-02-01",
            "ship_dates": ["2024-02-02", "2024-02-03"],
            "grouping_level": "shipment",
        }

        # Act
        group = OrderGroup.from_dict(data)

        # Assert
        assert group.order_id == "789-012"
        assert len(group.items) == 1
        assert group.items[0].name == "Product A"
        assert group.total == Money.from_cents(1200)
        assert group.order_date == FinancialDate.from_string("2024-02-01")
        assert len(group.ship_dates) == 2
        assert group.grouping_level == "shipment"
