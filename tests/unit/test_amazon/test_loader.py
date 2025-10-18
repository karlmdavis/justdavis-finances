#!/usr/bin/env python3
"""
Unit tests for Amazon loader module.

Tests data loading utilities for Amazon order history.
"""

import tempfile
from pathlib import Path

import pytest

from finances.amazon.loader import find_latest_amazon_export, load_orders
from finances.amazon.models import AmazonOrderItem


class TestAmazonLoader:
    """Test Amazon data loader functionality."""

    def setup_method(self):
        """Set up test environment with temporary directories."""
        self.temp_dir = Path(tempfile.mkdtemp())
        self.raw_dir = self.temp_dir / "amazon" / "raw"
        self.raw_dir.mkdir(parents=True)

    def teardown_method(self):
        """Clean up test environment."""
        import shutil

        shutil.rmtree(self.temp_dir)

    def _create_amazon_dir(self, dir_name: str, create_csv: bool = True) -> Path:
        """Helper to create Amazon data directory with optional CSV file."""
        amazon_dir = self.raw_dir / dir_name
        amazon_dir.mkdir(parents=True, exist_ok=True)

        if create_csv:
            csv_file = amazon_dir / "Retail.OrderHistory.1.csv"
            # Create valid Amazon CSV with all required columns
            csv_content = "Order ID,Order Date,Ship Date,Total Owed,Product Name,Quantity,ASIN/ISBN,Item Subtotal,Item Tax\n"
            csv_content += "123-456-789,01/01/2024,01/02/2024,$10.00,Test Item,1,B01234567,$9.00,$1.00\n"
            csv_file.write_text(csv_content)

        return amazon_dir

    def test_find_latest_export_simple_account_name(self):
        """Test finding latest export with simple account name."""
        # Create two exports with simple names
        self._create_amazon_dir("2024-01-01_karl_amazon_data")
        self._create_amazon_dir("2024-01-15_karl_amazon_data")

        latest = find_latest_amazon_export(self.raw_dir)

        assert latest is not None
        assert latest.name == "2024-01-15_karl_amazon_data"

    def test_find_latest_export_account_name_with_underscore(self):
        """Test finding latest export when account name contains underscores."""
        # Create exports with account names containing underscores
        self._create_amazon_dir("2024-01-01_karl_test_amazon_data")
        self._create_amazon_dir("2024-01-15_erica_main_amazon_data")

        latest = find_latest_amazon_export(self.raw_dir)

        assert latest is not None
        assert latest.name == "2024-01-15_erica_main_amazon_data"

    def test_load_orders_simple_account_name(self):
        """Test loading orders with simple account name."""
        self._create_amazon_dir("2024-01-01_karl_amazon_data")

        orders_by_account = load_orders(self.raw_dir)

        assert "karl" in orders_by_account
        orders = orders_by_account["karl"]
        assert isinstance(orders, list)
        assert len(orders) == 1
        assert isinstance(orders[0], AmazonOrderItem)
        assert orders[0].order_id == "123-456-789"
        assert orders[0].product_name == "Test Item"

    def test_load_orders_account_name_with_underscore(self):
        """Test loading orders when account name contains underscores."""
        # Create directory with underscored account name
        self._create_amazon_dir("2024-01-01_karl_test_amazon_data")
        self._create_amazon_dir("2024-01-15_erica_main_amazon_data")

        orders_by_account = load_orders(self.raw_dir)

        # Should correctly extract "karl_test" and "erica_main" as account names
        assert "karl_test" in orders_by_account
        assert "erica_main" in orders_by_account

        # Verify data loaded correctly
        orders = orders_by_account["karl_test"]
        assert len(orders) == 1
        assert isinstance(orders[0], AmazonOrderItem)

    def test_load_orders_filters_by_account(self):
        """Test filtering to specific accounts."""
        self._create_amazon_dir("2024-01-01_karl_amazon_data")
        self._create_amazon_dir("2024-01-01_erica_amazon_data")

        # Load only karl's data
        orders_by_account = load_orders(self.raw_dir, accounts=("karl",))

        assert "karl" in orders_by_account
        assert "erica" not in orders_by_account

    def test_load_orders_no_directories_raises_error(self):
        """Test that loading from empty directory raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError, match="No Amazon data directories found"):
            load_orders(self.raw_dir)
