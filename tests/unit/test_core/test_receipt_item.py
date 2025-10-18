#!/usr/bin/env python3
"""Tests for ReceiptItem domain model."""


from finances.core import Money, ReceiptItem


class TestReceiptItem:
    """Test ReceiptItem dataclass functionality."""

    def test_receipt_item_creation(self):
        """Test creating a ReceiptItem with minimal fields."""
        item = ReceiptItem(
            name="Test Product",
            cost=Money.from_cents(1999),
        )

        assert item.name == "Test Product"
        assert item.cost.to_cents() == 1999
        assert item.quantity == 1  # Default value
        assert item.category is None
        assert item.sku is None

    def test_receipt_item_with_all_fields(self):
        """Test creating a ReceiptItem with all optional fields."""
        item = ReceiptItem(
            name="Premium Widget",
            cost=Money.from_cents(4999),
            quantity=3,
            category="Electronics",
            sku="WDG-123",
            unit_price=Money.from_cents(1666),
            metadata={"color": "blue", "size": "large"},
        )

        assert item.name == "Premium Widget"
        assert item.cost.to_cents() == 4999
        assert item.quantity == 3
        assert item.category == "Electronics"
        assert item.sku == "WDG-123"
        assert item.unit_price.to_cents() == 1666
        assert item.metadata == {"color": "blue", "size": "large"}

    def test_receipt_item_to_dict(self):
        """Test converting ReceiptItem to dictionary."""
        item = ReceiptItem(
            name="Test Item",
            cost=Money.from_cents(2500),
            quantity=2,
            category="Books",
            sku="BOOK-456",
            unit_price=Money.from_cents(1250),
            metadata={"author": "Test Author"},
        )

        item_dict = item.to_dict()

        assert item_dict["name"] == "Test Item"
        assert item_dict["cost"] == 2500  # Converted to cents
        assert item_dict["quantity"] == 2
        assert item_dict["category"] == "Books"
        assert item_dict["sku"] == "BOOK-456"
        assert item_dict["unit_price"] == 1250  # Converted to cents
        assert item_dict["metadata"] == {"author": "Test Author"}

    def test_receipt_item_from_dict(self):
        """Test creating ReceiptItem from dictionary."""
        data = {
            "name": "Imported Item",
            "cost": 3999,  # cents
            "quantity": 5,
            "category": "Groceries",
            "sku": "GROC-789",
            "unit_price": 799,  # cents
            "metadata": {"organic": True},
        }

        item = ReceiptItem.from_dict(data)

        assert item.name == "Imported Item"
        assert item.cost.to_cents() == 3999
        assert item.quantity == 5
        assert item.category == "Groceries"
        assert item.sku == "GROC-789"
        assert item.unit_price.to_cents() == 799
        assert item.metadata == {"organic": True}

    def test_receipt_item_from_dict_minimal(self):
        """Test creating ReceiptItem from dictionary with minimal fields."""
        data = {
            "name": "Minimal Item",
            "cost": 999,
        }

        item = ReceiptItem.from_dict(data)

        assert item.name == "Minimal Item"
        assert item.cost.to_cents() == 999
        assert item.quantity == 1  # Default
        assert item.category is None
        assert item.sku is None
        assert item.unit_price is None
        assert item.metadata == {}

    def test_receipt_item_from_dict_with_money_objects(self):
        """Test from_dict handles Money objects (not just ints)."""
        data = {
            "name": "Money Object Item",
            "cost": Money.from_cents(1500),
            "unit_price": Money.from_cents(750),
        }

        item = ReceiptItem.from_dict(data)

        assert item.cost.to_cents() == 1500
        assert item.unit_price.to_cents() == 750

    def test_receipt_item_roundtrip(self):
        """Test ReceiptItem survives to_dict → from_dict roundtrip."""
        original = ReceiptItem(
            name="Roundtrip Item",
            cost=Money.from_cents(5000),
            quantity=10,
            category="Test Category",
            sku="TEST-999",
            unit_price=Money.from_cents(500),
            metadata={"test": "data"},
        )

        # Convert to dict and back
        item_dict = original.to_dict()
        restored = ReceiptItem.from_dict(item_dict)

        # Should be equivalent
        assert restored.name == original.name
        assert restored.cost.to_cents() == original.cost.to_cents()
        assert restored.quantity == original.quantity
        assert restored.category == original.category
        assert restored.sku == original.sku
        assert restored.unit_price.to_cents() == original.unit_price.to_cents()
        assert restored.metadata == original.metadata
