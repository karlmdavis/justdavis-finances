#!/usr/bin/env python3
"""
Unit tests for Amazon grouper with domain models.

Tests grouper refactored to use list[AmazonOrderItem] input
and OrderGroup output (no DataFrames).
"""


from finances.amazon.grouper import GroupingLevel, group_orders
from finances.amazon.models import AmazonOrderItem, OrderGroup
from finances.core import FinancialDate, Money


class TestGroupOrdersByOrderId:
    """Tests for group_orders with ORDER level (domain models)."""

    def test_group_single_item_order(self):
        """Test grouping single-item order."""
        # Arrange
        items = [
            AmazonOrderItem(
                order_id="123-456",
                asin="B01",
                product_name="Product A",
                quantity=1,
                unit_price=Money.from_cents(1999),
                total_owed=Money.from_cents(1999),
                order_date=FinancialDate.from_string("2024-01-15"),
                ship_date=FinancialDate.from_string("2024-01-16"),
            )
        ]

        # Act
        result = group_orders(items, level=GroupingLevel.ORDER)

        # Assert
        assert isinstance(result, dict)
        assert "123-456" in result

        order_group = result["123-456"]
        assert isinstance(order_group, OrderGroup)
        assert order_group.order_id == "123-456"
        assert len(order_group.items) == 1
        assert order_group.items[0].name == "Product A"
        assert order_group.items[0].amount == Money.from_cents(1999)
        assert order_group.total == Money.from_cents(1999)
        assert order_group.order_date == FinancialDate.from_string("2024-01-15")
        assert len(order_group.ship_dates) == 1
        assert order_group.grouping_level == "order"

    def test_group_multi_item_order(self):
        """Test grouping multi-item order with same ship date."""
        # Arrange
        items = [
            AmazonOrderItem(
                order_id="123-456",
                asin="B01",
                product_name="Product A",
                quantity=1,
                unit_price=Money.from_cents(1999),
                total_owed=Money.from_cents(1999),
                order_date=FinancialDate.from_string("2024-01-15"),
                ship_date=FinancialDate.from_string("2024-01-16"),
            ),
            AmazonOrderItem(
                order_id="123-456",
                asin="B02",
                product_name="Product B",
                quantity=2,
                unit_price=Money.from_cents(500),
                total_owed=Money.from_cents(1000),
                order_date=FinancialDate.from_string("2024-01-15"),
                ship_date=FinancialDate.from_string("2024-01-16"),
            ),
        ]

        # Act
        result = group_orders(items, level=GroupingLevel.ORDER)

        # Assert
        order_group = result["123-456"]
        assert len(order_group.items) == 2
        assert order_group.total == Money.from_cents(2999)
        assert order_group.items[0].name == "Product A"
        assert order_group.items[1].name == "Product B"

    def test_group_multiple_orders(self):
        """Test grouping items from different orders."""
        # Arrange
        items = [
            AmazonOrderItem(
                order_id="123-456",
                asin="B01",
                product_name="Product A",
                quantity=1,
                unit_price=Money.from_cents(1000),
                total_owed=Money.from_cents(1000),
                order_date=FinancialDate.from_string("2024-01-15"),
                ship_date=FinancialDate.from_string("2024-01-16"),
            ),
            AmazonOrderItem(
                order_id="789-012",
                asin="B02",
                product_name="Product B",
                quantity=1,
                unit_price=Money.from_cents(2000),
                total_owed=Money.from_cents(2000),
                order_date=FinancialDate.from_string("2024-01-17"),
                ship_date=FinancialDate.from_string("2024-01-18"),
            ),
        ]

        # Act
        result = group_orders(items, level=GroupingLevel.ORDER)

        # Assert
        assert len(result) == 2
        assert "123-456" in result
        assert "789-012" in result
        assert result["123-456"].total == Money.from_cents(1000)
        assert result["789-012"].total == Money.from_cents(2000)

    def test_group_order_with_multiple_ship_dates(self):
        """Test order with items shipping on different dates."""
        # Arrange
        items = [
            AmazonOrderItem(
                order_id="123-456",
                asin="B01",
                product_name="Product A",
                quantity=1,
                unit_price=Money.from_cents(1000),
                total_owed=Money.from_cents(1000),
                order_date=FinancialDate.from_string("2024-01-15"),
                ship_date=FinancialDate.from_string("2024-01-16"),
            ),
            AmazonOrderItem(
                order_id="123-456",
                asin="B02",
                product_name="Product B",
                quantity=1,
                unit_price=Money.from_cents(500),
                total_owed=Money.from_cents(500),
                order_date=FinancialDate.from_string("2024-01-15"),
                ship_date=FinancialDate.from_string("2024-01-18"),
            ),
        ]

        # Act
        result = group_orders(items, level=GroupingLevel.ORDER)

        # Assert
        order_group = result["123-456"]
        assert len(order_group.ship_dates) == 2
        assert FinancialDate.from_string("2024-01-16") in order_group.ship_dates
        assert FinancialDate.from_string("2024-01-18") in order_group.ship_dates
        # Should be sorted
        assert order_group.ship_dates[0] < order_group.ship_dates[1]

    def test_group_empty_list(self):
        """Test grouping empty list."""
        # Act
        result = group_orders([], level=GroupingLevel.ORDER)

        # Assert
        assert result == {}
