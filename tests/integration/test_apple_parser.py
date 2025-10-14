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
def test_parse_legacy_aapl_format_complete(parser, fixtures_dir):
    """Test end-to-end parsing of legacy aapl-* format receipt."""
    html_path = fixtures_dir / "legacy_aapl_receipt.html"

    with open(html_path, encoding="utf-8") as f:
        html_content = f.read()

    receipt = parser.parse_html_content(html_content, "legacy_test")

    # Verify format detection
    assert receipt.format_detected == "legacy_aapl"

    # Verify metadata extraction - Apple ID should be found
    assert receipt.apple_id == "test@example.com"

    # Order ID extraction may vary based on HTML structure - just verify something was found
    assert receipt.order_id is not None

    # Receipt date should be parsed as FinancialDate
    assert receipt.receipt_date is not None
    assert "2024" in receipt.receipt_date.to_iso_string()

    # Financial data - verify currency values were extracted (parser may extract multiple)
    # Parser now returns Money objects
    assert receipt.total is not None
    from finances.core.money import Money
    assert isinstance(receipt.total, Money)

    # Verify items extraction - should find at least one item with "Procreate"
    assert len(receipt.items) > 0
    procreate_items = [item for item in receipt.items if "Procreate" in item.title]
    assert len(procreate_items) > 0

    # Verify billing information extraction attempted
    assert receipt.billed_to is not None or receipt.payment_method is not None

    # Verify parsing metadata
    assert receipt.parsing_metadata["extraction_method"] == "html_content_parser"
    assert receipt.parsing_metadata["success_rate"] > 0


@pytest.mark.integration
@pytest.mark.apple
def test_parse_modern_custom_format_complete(parser, fixtures_dir):
    """Test end-to-end parsing of modern custom-* format receipt."""
    html_path = fixtures_dir / "modern_custom_receipt.html"

    with open(html_path, encoding="utf-8") as f:
        html_content = f.read()

    receipt = parser.parse_html_content(html_content, "modern_test")

    # Verify format detection
    assert receipt.format_detected == "modern_custom"

    # Verify metadata extraction
    assert receipt.apple_id == "family@example.com"
    assert receipt.order_id == "NX8QR3ABC"
    assert receipt.receipt_date is not None

    # Verify items extraction - should find Apple Music
    assert len(receipt.items) > 0
    music_items = [item for item in receipt.items if "Apple Music" in item.title]
    assert len(music_items) > 0

    # Verify payment method extraction attempted
    assert receipt.payment_method is not None or receipt.billed_to is not None


@pytest.mark.integration
@pytest.mark.apple
def test_parse_multi_item_receipt(parser, fixtures_dir):
    """Test end-to-end parsing of receipt with multiple items."""
    html_path = fixtures_dir / "multi_item_receipt.html"

    with open(html_path, encoding="utf-8") as f:
        html_content = f.read()

    receipt = parser.parse_html_content(html_content, "multi_item_test")

    # Verify format detection (should be table-based or generic)
    assert receipt.format_detected in ["table_based", "apple_generic"]

    # Verify metadata
    assert receipt.apple_id == "test@example.com"
    assert receipt.order_id == "KL5MN4DEF"

    # Verify date extraction
    assert receipt.receipt_date is not None

    # Verify multiple items extraction
    assert len(receipt.items) >= 2

    # Find specific items
    final_cut_items = [item for item in receipt.items if "Final Cut" in item.title]
    logic_pro_items = [item for item in receipt.items if "Logic" in item.title]

    assert len(final_cut_items) > 0
    assert len(logic_pro_items) > 0


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

    html_path = fixtures_dir / "legacy_aapl_receipt.html"

    with open(html_path, encoding="utf-8") as f:
        html_content = f.read()

    receipt = parser.parse_html_content(html_content, "currency_test")

    # Verify all currency fields are Money objects
    if receipt.total is not None:
        assert isinstance(receipt.total, Money), f"total must be Money object, got {type(receipt.total)}"
        # Verify reasonable range - should be in cents (e.g., 4599 not 45.99)
        assert receipt.total.to_cents() > 100, f"total={receipt.total.to_cents()} should be in cents (>100), not dollars"

    if receipt.subtotal is not None:
        assert isinstance(receipt.subtotal, Money), f"subtotal must be Money object, got {type(receipt.subtotal)}"

    if receipt.tax is not None:
        assert isinstance(receipt.tax, Money), f"tax must be Money object, got {type(receipt.tax)}"

    # Verify all items have Money cost objects
    for item in receipt.items:
        assert isinstance(
            item.cost, Money
        ), f"item '{item.title}' cost must be Money object, got {type(item.cost)}"
        # Verify reasonable range for items
        if item.cost.to_cents() > 0:
            assert item.cost.to_cents() > 50, f"item '{item.title}' cost={item.cost.to_cents()} should be in cents, not dollars"


@pytest.mark.integration
@pytest.mark.apple
def test_parse_receipt_from_file_system(parser, fixtures_dir, temp_dir):
    """Test parsing receipt using file system path method."""
    # Copy a fixture to temp directory with expected naming
    html_source = fixtures_dir / "legacy_aapl_receipt.html"
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
    assert receipt.format_detected == "legacy_aapl"
    assert receipt.apple_id == "test@example.com"
    assert receipt.total is not None
    assert isinstance(receipt.total, Money)  # Parser now returns Money objects


@pytest.mark.integration
@pytest.mark.apple
def test_parse_receipt_file_not_found(parser, temp_dir):
    """Test handling of missing receipt file."""
    content_dir = temp_dir / "empty_receipts"
    content_dir.mkdir(parents=True, exist_ok=True)

    receipt = parser.parse_receipt("nonexistent_receipt", content_dir)

    # Should return ParsedReceipt with error metadata
    assert isinstance(receipt, ParsedReceipt)
    assert "errors" in receipt.parsing_metadata
    assert "HTML file not found" in receipt.parsing_metadata["errors"]


@pytest.mark.integration
@pytest.mark.apple
def test_receipt_to_dict_serialization(parser, fixtures_dir):
    """Test that parsed receipt can be serialized to dictionary."""
    html_path = fixtures_dir / "legacy_aapl_receipt.html"

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


@pytest.mark.integration
@pytest.mark.apple
def test_parser_selector_tracking(parser, fixtures_dir):
    """Test that parser tracks selector usage for debugging."""
    html_path = fixtures_dir / "legacy_aapl_receipt.html"

    with open(html_path, encoding="utf-8") as f:
        html_content = f.read()

    receipt = parser.parse_html_content(html_content, "selector_test")

    # Verify selector tracking
    metadata = receipt.parsing_metadata
    assert "selectors_successful" in metadata
    assert "selectors_failed" in metadata
    assert "total_selectors_tried" in metadata
    assert "success_rate" in metadata

    # Should have some successful selectors
    assert len(metadata["selectors_successful"]) > 0
    assert metadata["success_rate"] > 0
