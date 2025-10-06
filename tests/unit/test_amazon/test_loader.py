#!/usr/bin/env python3
"""
Unit tests for Amazon loader module.

Tests data loading utilities for Amazon order history.
"""

import tempfile
from pathlib import Path

import pandas as pd
import pytest

from finances.amazon.loader import find_latest_amazon_export, load_amazon_data


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
            # Create minimal valid CSV
            csv_content = "Order Date,Ship Date,Order ID,Title,Price,Quantity\n"
            csv_content += "2024-01-01,2024-01-02,123-456,Test Item,$10.00,1\n"
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

    def test_load_amazon_data_simple_account_name(self):
        """Test loading data with simple account name."""
        self._create_amazon_dir("2024-01-01_karl_amazon_data")

        account_data = load_amazon_data(self.raw_dir)

        assert "karl" in account_data
        retail_df, _ = account_data["karl"]
        assert isinstance(retail_df, pd.DataFrame)
        assert len(retail_df) == 1  # One row from our test CSV

    def test_load_amazon_data_account_name_with_underscore(self):
        """Test loading data when account name contains underscores."""
        # Create directory with underscored account name
        self._create_amazon_dir("2024-01-01_karl_test_amazon_data")
        self._create_amazon_dir("2024-01-15_erica_main_amazon_data")

        account_data = load_amazon_data(self.raw_dir)

        # Should correctly extract "karl_test" and "erica_main" as account names
        assert "karl_test" in account_data
        assert "erica_main" in account_data

        # Verify data loaded correctly
        retail_df, _ = account_data["karl_test"]
        assert len(retail_df) == 1

    def test_load_amazon_data_filters_by_account(self):
        """Test filtering to specific accounts."""
        self._create_amazon_dir("2024-01-01_karl_amazon_data")
        self._create_amazon_dir("2024-01-01_erica_amazon_data")

        # Load only karl's data
        account_data = load_amazon_data(self.raw_dir, accounts=("karl",))

        assert "karl" in account_data
        assert "erica" not in account_data

    def test_load_amazon_data_no_directories_raises_error(self):
        """Test that loading from empty directory raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError, match="No Amazon data directories found"):
            load_amazon_data(self.raw_dir)

    def test_find_latest_export_no_directories_returns_none(self):
        """Test that finding export in empty directory returns None."""
        result = find_latest_amazon_export(self.raw_dir)
        assert result is None
