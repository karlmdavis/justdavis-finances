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

        # Verify extraction results (nested directory structure)
        extracted_dirs = list(raw_dir.glob("*_karl_amazon_data"))
        assert len(extracted_dirs) == 1
        csv_path = extracted_dirs[0] / "Retail.OrderHistory.1" / "Retail.OrderHistory.1.csv"
        assert csv_path.exists()

    # test_execute_no_zip_files removed - covered by parameterized test_flownode_interface.py


@pytest.mark.integration
@pytest.mark.amazon
class TestAmazonMatchingFlowNode:
    """Integration tests for AmazonMatchingFlowNode orchestration."""

    def test_execute_with_data(self, temp_dir, flow_context):
        """Test AmazonMatchingFlowNode.execute() with Amazon and YNAB data."""
        node = AmazonMatchingFlowNode(temp_dir)

        # Set up Amazon raw data with nested directory structure (current format)
        raw_dir = temp_dir / "amazon" / "raw" / "2025-01-01_karl_amazon_data"
        csv_dir = raw_dir / "Retail.OrderHistory.1"
        csv_dir.mkdir(parents=True)
        csv_file = csv_dir / "Retail.OrderHistory.1.csv"
        csv_file.write_text(
            '"Website","Order ID","Order Date","Purchase Order Number","Currency",'
            '"Unit Price","Unit Price Tax","Shipping Charge","Total Discounts","Total Owed",'
            '"Shipment Item Subtotal","Shipment Item Subtotal Tax","ASIN","Product Condition",'
            '"Quantity","Payment Instrument Type","Order Status","Shipment Status","Ship Date",'
            '"Shipping Option","Shipping Address","Billing Address","Carrier Name & Tracking Number",'
            '"Product Name","Gift Message","Gift Sender Name","Gift Recipient Contact Details",'
            '"Item Serial Number"\n'
            '"Amazon.com","111-2223334-5556667","2024-08-15T12:00:00Z","Not Applicable","USD",'
            '"49.99","0.00","0","0","29.99","29.99","0.00","B07XJ8C8F7","New","1",'
            '"Visa - 1234","Closed","Shipped","2024-08-15T14:00:00Z","standard",'
            '"Karl Davis 123 Main St Seattle WA 98101 United States",'
            '"Karl Davis 123 Main St Seattle WA 98101 United States",'
            '"USPS(9400111899223344556677)","Echo Dot (4th Gen)","Not Available",'
            '"Not Available","Not Available","Not Available"\n'
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
