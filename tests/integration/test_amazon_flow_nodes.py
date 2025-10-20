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

    # test_execute_no_zip_files removed - covered by parameterized test_flownode_interface.py


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

    # Removed tests that are covered by parameterized test_flownode_interface.py:
    # - test_execute_no_amazon_data (missing input data handling)
    # - test_execute_no_ynab_cache (missing dependency handling)
