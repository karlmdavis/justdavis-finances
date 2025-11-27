#!/usr/bin/env python3
"""
Integration tests for Apple Receipt Parser.

End-to-end tests using real HTML fixtures to validate complete parsing workflows.
"""

from pathlib import Path

import pytest

from finances.apple.parser import AppleReceiptParser, ParsedReceipt


@pytest.fixture
def parser():
    """Create a parser instance for testing."""
    return AppleReceiptParser()


@pytest.fixture
def fixtures_dir():
    """Get the Apple fixtures directory."""
    return Path(__file__).parent.parent / "fixtures" / "apple"


@pytest.mark.integration
@pytest.mark.apple
def test_parse_malformed_receipt_gracefully(parser, fixtures_dir):
    """Test graceful handling of malformed HTML receipt."""
    html_path = fixtures_dir / "malformed_receipt.html"

    with open(html_path, encoding="utf-8") as f:
        html_content = f.read()

    receipt = parser.parse_html_content(html_content, "malformed_test")

    # Should not crash and return a ParsedReceipt object
    assert isinstance(receipt, ParsedReceipt)

    # Format should be detected (even if unknown)
    assert receipt.format_detected is not None

    # Most fields will be None due to missing data
    # This validates graceful degradation
    assert receipt.base_name == "malformed_test"


@pytest.mark.integration
@pytest.mark.apple
def test_currency_values_are_money_objects(parser, fixtures_dir):
    """
    Verify parser returns currency as Money objects, not raw integers or floats.

    Updated from original test to validate type-safe Money objects.
    """
    from finances.core.money import Money

    html_path = fixtures_dir / "table_format_receipt.html"

    with open(html_path, encoding="utf-8") as f:
        html_content = f.read()

    receipt = parser.parse_html_content(html_content, "currency_test")

    # Verify all currency fields are Money objects
    if receipt.total is not None:
        assert isinstance(receipt.total, Money), f"total must be Money object, got {type(receipt.total)}"
        # Verify reasonable range - should be in cents (e.g., 4599 not 45.99)
        assert (
            receipt.total.to_cents() > 100
        ), f"total={receipt.total.to_cents()} should be in cents (>100), not dollars"

    if receipt.subtotal is not None:
        assert isinstance(
            receipt.subtotal, Money
        ), f"subtotal must be Money object, got {type(receipt.subtotal)}"

    if receipt.tax is not None:
        assert isinstance(receipt.tax, Money), f"tax must be Money object, got {type(receipt.tax)}"

    # Verify all items have Money cost objects
    for item in receipt.items:
        assert isinstance(
            item.cost, Money
        ), f"item '{item.title}' cost must be Money object, got {type(item.cost)}"
        # Verify reasonable range for items
        if item.cost.to_cents() > 0:
            assert (
                item.cost.to_cents() > 50
            ), f"item '{item.title}' cost={item.cost.to_cents()} should be in cents, not dollars"


@pytest.mark.integration
@pytest.mark.apple
def test_parse_receipt_from_file_system(parser, fixtures_dir, temp_dir):
    """Test parsing receipt using file system path method."""
    # Copy a fixture to temp directory with expected naming
    html_source = fixtures_dir / "table_format_receipt.html"
    test_base_name = "test_receipt_001"

    content_dir = temp_dir / "receipts"
    content_dir.mkdir(parents=True, exist_ok=True)

    html_dest = content_dir / f"{test_base_name}-formatted-simple.html"

    with open(html_source, encoding="utf-8") as f:
        html_content = f.read()

    with open(html_dest, "w", encoding="utf-8") as f:
        f.write(html_content)

    # Parse using file system method
    receipt = parser.parse_receipt(test_base_name, content_dir)

    # Verify successful parsing
    from finances.core.money import Money

    assert receipt.base_name == test_base_name
    assert receipt.format_detected == "table_format"
    assert receipt.apple_id == "test@example.com"
    assert receipt.total is not None
    assert isinstance(receipt.total, Money)  # Parser now returns Money objects


@pytest.mark.integration
@pytest.mark.apple
def test_parse_receipt_file_not_found(parser, temp_dir):
    """Test handling of missing receipt file."""
    content_dir = temp_dir / "empty_receipts"
    content_dir.mkdir(parents=True, exist_ok=True)

    # Should raise FileNotFoundError for missing files
    with pytest.raises(FileNotFoundError, match="HTML file not found"):
        parser.parse_receipt("nonexistent_receipt", content_dir)


@pytest.mark.integration
@pytest.mark.apple
def test_receipt_to_dict_serialization(parser, fixtures_dir):
    """Test that parsed receipt can be serialized to dictionary."""
    html_path = fixtures_dir / "table_format_receipt.html"

    with open(html_path, encoding="utf-8") as f:
        html_content = f.read()

    receipt = parser.parse_html_content(html_content, "serialization_test")

    # Convert to dict
    receipt_dict = receipt.to_dict()

    # Verify structure
    assert isinstance(receipt_dict, dict)
    assert "format_detected" in receipt_dict
    assert "apple_id" in receipt_dict
    assert "total" in receipt_dict
    assert "items" in receipt_dict
    assert "parsing_metadata" in receipt_dict

    # Verify items are also dictionaries
    assert isinstance(receipt_dict["items"], list)
    if receipt_dict["items"]:
        assert isinstance(receipt_dict["items"][0], dict)
        assert "title" in receipt_dict["items"][0]
        assert "cost" in receipt_dict["items"][0]


@pytest.mark.integration
@pytest.mark.apple
def test_add_item_to_receipt(parser):
    """Test adding items to receipt programmatically."""
    from finances.core.money import Money

    receipt = ParsedReceipt(base_name="test_receipt")

    # Add items (now using Money objects)
    receipt.add_item("Test App 1", Money.from_cents(999), quantity=1)
    receipt.add_item("Test App 2", Money.from_cents(499), quantity=2, subscription=True)

    # Verify items added
    assert len(receipt.items) == 2
    assert receipt.items[0].title == "Test App 1"
    assert receipt.items[0].cost.to_cents() == 999
    assert receipt.items[0].quantity == 1
    assert receipt.items[0].subscription is False

    assert receipt.items[1].title == "Test App 2"
    assert receipt.items[1].cost.to_cents() == 499
    assert receipt.items[1].quantity == 2
    assert receipt.items[1].subscription is True
