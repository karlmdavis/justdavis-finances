#!/usr/bin/env python3
"""
Integration tests for Amazon FlowNode implementations.

Tests FlowNode orchestration logic with real filesystem operations.
"""

import shutil
from datetime import datetime
from pathlib import Path

import pytest

from finances.amazon.flow import AmazonMatchingFlowNode, AmazonUnzipFlowNode
from finances.core.flow import FlowContext
from finances.core.json_utils import write_json


@pytest.fixture
def fixtures_dir():
    """Path to Amazon test fixtures."""
    return Path(__file__).parent.parent / "fixtures" / "amazon"


@pytest.fixture
def karl_zip(fixtures_dir):
    """Path to Karl's Amazon ZIP fixture."""
    return fixtures_dir / "amazon_orders_karl.zip"


@pytest.fixture
def erica_zip(fixtures_dir):
    """Path to Erica's Amazon ZIP fixture."""
    return fixtures_dir / "amazon_orders_erica.zip"


@pytest.fixture
def flow_context():
    """Create basic FlowContext for testing."""
    return FlowContext(start_time=datetime.now())


@pytest.mark.integration
@pytest.mark.amazon
class TestAmazonUnzipFlowNode:
    """Integration tests for AmazonUnzipFlowNode orchestration."""

    def test_execute_with_zip_files(self, temp_dir, karl_zip, flow_context):
        """Test AmazonUnzipFlowNode.execute() with ZIP files in amazon/raw."""
        node = AmazonUnzipFlowNode(temp_dir)

        # Set up amazon/raw directory with ZIP file
        raw_dir = temp_dir / "amazon" / "raw"
        raw_dir.mkdir(parents=True, exist_ok=True)
        zip_copy = raw_dir / "amazon_orders_karl_test.zip"
        shutil.copy(karl_zip, zip_copy)

        # Execute node
        result = node.execute(flow_context)

        # Verify success
        assert result.success is True
        assert result.items_processed == 1
        assert result.new_items == 1

        # Verify extraction results
        extracted_dirs = list(raw_dir.glob("*_karl_amazon_data"))
        assert len(extracted_dirs) == 1
        assert (extracted_dirs[0] / "Retail.OrderHistory.1.csv").exists()

    def test_execute_no_zip_files(self, temp_dir, flow_context):
        """Test AmazonUnzipFlowNode.execute() with no ZIP files."""
        node = AmazonUnzipFlowNode(temp_dir)

        # Execute without amazon/raw directory
        result = node.execute(flow_context)

        # Should fail gracefully when directory doesn't exist
        assert result.success is False
        assert "Amazon raw directory not found" in result.error_message

    def test_check_changes_with_new_zips(self, temp_dir, karl_zip, flow_context):
        """Test check_changes() when new ZIPs are available."""
        node = AmazonUnzipFlowNode(temp_dir)

        # Copy ZIP to amazon/raw
        raw_dir = temp_dir / "amazon" / "raw"
        raw_dir.mkdir(parents=True, exist_ok=True)
        zip_copy = raw_dir / "amazon_orders_karl_test.zip"
        shutil.copy(karl_zip, zip_copy)

        # Check changes
        has_changes, reasons = node.check_changes(flow_context)

        # Should detect new ZIP
        assert has_changes is True
        assert any("ZIP file" in r for r in reasons)


@pytest.mark.integration
@pytest.mark.amazon
class TestAmazonMatchingFlowNode:
    """Integration tests for AmazonMatchingFlowNode orchestration."""

    def test_execute_with_data(self, temp_dir, flow_context):
        """Test AmazonMatchingFlowNode.execute() with Amazon and YNAB data."""
        node = AmazonMatchingFlowNode(temp_dir)

        # Set up Amazon raw data
        raw_dir = temp_dir / "amazon" / "raw" / "2025-01-01_karl_amazon_data"
        raw_dir.mkdir(parents=True)
        csv_file = raw_dir / "Retail.OrderHistory.1.csv"
        csv_file.write_text(
            "Order ID,Order Date,Purchase Order Number,Ship Date,Title,Category,ASIN/ISBN,"
            "UNSPSC Code,Website,Release Date,Condition,Seller,Seller Credentials,"
            "List Price Per Unit,Purchase Price Per Unit,Quantity,Payment Instrument Type,"
            "Purchase Order State,Shipping Address Name,Shipping Address Street 1,"
            "Shipping Address Street 2,Shipping Address City,Shipping Address State,"
            "Shipping Address Zip,Order Status,Carrier Name & Tracking Number,Item Subtotal,"
            "Item Subtotal Tax,Item Total,Tax Exemption Applied,Tax Exemption Type,"
            "Exemption Opt-Out,Buyer Name,Currency,Group Name\n"
            "111-2223334-5556667,08/15/2024,D01-1234567-1234567,08/15/2024,Echo Dot (4th Gen),"
            "Electronics,B07XJ8C8F7,,,Amazon.com,,,,$49.99,$29.99,1,Visa - 1234,Shipped,"
            "Karl Davis,123 Main St,,Seattle,WA,98101,Shipped,USPS(9400111899223344556677),"
            "$29.99,$0.00,$29.99,,,,Karl Davis,USD,\n"
        )

        # Set up YNAB cache
        ynab_cache_dir = temp_dir / "ynab" / "cache"
        ynab_cache_dir.mkdir(parents=True)
        transactions_file = ynab_cache_dir / "transactions.json"
        write_json(
            transactions_file,
            [
                {
                    "id": "tx123",
                    "date": "2024-08-15",
                    "amount": -29990,  # -$29.99 in milliunits
                    "payee_name": "Amazon.com",
                    "account_name": "Visa - 1234",
                }
            ],
        )

        # Execute matching
        result = node.execute(flow_context)

        # Verify success
        assert result.success is True
        assert result.items_processed >= 1
        assert len(result.outputs) == 1

        # Verify output file created
        matches_dir = temp_dir / "amazon" / "transaction_matches"
        assert matches_dir.exists()
        match_files = list(matches_dir.glob("*.json"))
        assert len(match_files) == 1

    def test_execute_no_amazon_data(self, temp_dir, flow_context):
        """Test execute() when no Amazon data available."""
        node = AmazonMatchingFlowNode(temp_dir)

        # Set up YNAB cache only (no Amazon data)
        ynab_cache_dir = temp_dir / "ynab" / "cache"
        ynab_cache_dir.mkdir(parents=True)
        transactions_file = ynab_cache_dir / "transactions.json"
        write_json(transactions_file, [{"id": "tx123", "payee_name": "Amazon.com"}])

        # Execute should fail gracefully
        result = node.execute(flow_context)

        assert result.success is False
        assert "Amazon" in result.error_message or result.items_processed == 0

    def test_execute_no_ynab_cache(self, temp_dir, flow_context):
        """Test execute() when no YNAB cache available."""
        node = AmazonMatchingFlowNode(temp_dir)

        # Set up Amazon data only (no YNAB cache)
        raw_dir = temp_dir / "amazon" / "raw" / "2025-01-01_karl_amazon_data"
        raw_dir.mkdir(parents=True)
        csv_file = raw_dir / "Retail.OrderHistory.1.csv"
        csv_file.write_text("Order ID\n111-222\n")

        # Execute should fail
        result = node.execute(flow_context)

        assert result.success is False

    def test_check_changes_no_ynab_cache(self, temp_dir, flow_context):
        """Test check_changes() when YNAB cache missing."""
        node = AmazonMatchingFlowNode(temp_dir)

        # Create Amazon data only (node looks for Retail.OrderHistory.*.csv)
        raw_dir = temp_dir / "amazon" / "raw" / "2025-01-01_karl_amazon_data"
        raw_dir.mkdir(parents=True)
        (raw_dir / "Retail.OrderHistory.1.csv").write_text("Order ID\n111\n")

        has_changes, reasons = node.check_changes(flow_context)

        assert has_changes is False
        assert any("No YNAB cache available" in r for r in reasons)

    def test_check_changes_no_previous_matches(self, temp_dir, flow_context):
        """Test check_changes() when no previous matches exist."""
        node = AmazonMatchingFlowNode(temp_dir)

        # Create Amazon data (node looks for Retail.OrderHistory.*.csv)
        raw_dir = temp_dir / "amazon" / "raw" / "2025-01-01_karl_amazon_data"
        raw_dir.mkdir(parents=True)
        (raw_dir / "Retail.OrderHistory.1.csv").write_text("Order ID\n111\n")

        # Create YNAB cache
        ynab_cache_dir = temp_dir / "ynab" / "cache"
        ynab_cache_dir.mkdir(parents=True)
        (ynab_cache_dir / "transactions.json").write_text("[]")

        has_changes, reasons = node.check_changes(flow_context)

        assert has_changes is True
        assert any("No previous matching" in r for r in reasons)
