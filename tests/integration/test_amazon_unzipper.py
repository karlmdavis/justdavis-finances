#!/usr/bin/env python3
"""
Integration tests for Amazon unzipper module.

Tests complete end-to-end extraction workflows using real ZIP fixtures.
"""

import csv
import json
from pathlib import Path

import pytest

from finances.amazon.unzipper import AmazonUnzipper, extract_amazon_zip_files


@pytest.mark.integration
@pytest.mark.amazon
class TestAmazonUnzipperIntegration:
    """Integration tests for Amazon ZIP extraction workflows."""

    @pytest.fixture
    def fixtures_dir(self):
        """Path to Amazon test fixtures directory."""
        return Path(__file__).parent.parent / "fixtures" / "amazon"

    @pytest.fixture
    def karl_zip(self, fixtures_dir):
        """Path to Karl's Amazon orders ZIP fixture."""
        return fixtures_dir / "amazon_orders_karl.zip"

    @pytest.fixture
    def erica_zip(self, fixtures_dir):
        """Path to Erica's Amazon orders ZIP fixture."""
        return fixtures_dir / "amazon_orders_erica.zip"

    @pytest.fixture
    def corrupted_zip(self, fixtures_dir):
        """Path to corrupted ZIP fixture."""
        return fixtures_dir / "corrupted_amazon.zip"

    @pytest.fixture
    def unzipper(self, temp_dir):
        """Create AmazonUnzipper instance with temporary raw data directory."""
        raw_data_dir = temp_dir / "amazon" / "raw"
        return AmazonUnzipper(raw_data_dir)

    def test_extract_single_zip_complete(self, unzipper, karl_zip, temp_dir):
        """Test complete ZIP extraction with comprehensive validation."""
        # Execute extraction
        result = unzipper.extract_zip_file(karl_zip)

        # Verify extraction success
        assert result["success"] is True
        assert result["account_name"] == "karl"
        assert result["files_extracted"] == 2  # CSV + JSON

        # Verify output directory structure
        output_dir = Path(result["output_directory"])
        assert output_dir.exists()
        assert output_dir.is_dir()
        assert output_dir.parent == unzipper.raw_data_dir

        # Verify directory naming convention (YYYY-MM-DD_accountname_amazon_data)
        assert "_karl_amazon_data" in output_dir.name
        assert output_dir.name.startswith("2025-")  # Current year

        # Verify CSV files were extracted
        assert len(result["csv_files"]) == 1
        assert result["csv_files"][0] == "Retail.OrderHistory.1.csv"

        # Verify JSON files were extracted
        assert len(result["json_files"]) == 1
        assert result["json_files"][0] == "metadata.json"

        # Verify actual file extraction
        csv_path = output_dir / "Retail.OrderHistory.1.csv"
        assert csv_path.exists()
        assert csv_path.is_file()

        json_path = output_dir / "metadata.json"
        assert json_path.exists()
        assert json_path.is_file()

        # Verify CSV data integrity
        with open(csv_path, encoding="utf-8") as f:
            reader = csv.DictReader(f)
            orders = list(reader)
            assert len(orders) == 2
            assert orders[0]["Order ID"] == "111-2223334-5556667"
            assert orders[0]["Title"] == "Echo Dot (4th Gen) Smart speaker with Alexa - Charcoal"
            assert orders[1]["Order ID"] == "112-3334445-6667778"

        # Verify JSON data integrity
        with open(json_path) as f:
            metadata = json.load(f)
            assert metadata["report_type"] == "order_history"
            assert metadata["record_count"] == 2

        # Verify metadata preservation in result
        assert "zip_file" in result
        assert "output_directory" in result
        assert "timestamp" in result
        assert "files_extracted" in result

        # Verify timestamp format (ISO 8601)
        from datetime import datetime

        timestamp = datetime.fromisoformat(result["timestamp"])
        assert timestamp is not None

        # Verify zip_file path is preserved
        assert karl_zip.name in result["zip_file"]

        # Verify CSV column structure and data formats
        with open(csv_path, encoding="utf-8") as f:
            reader = csv.DictReader(f)
            orders = list(reader)

            # Verify expected columns exist
            expected_columns = [
                "Order ID",
                "Order Date",
                "Title",
                "ASIN/ISBN",
                "Item Subtotal",
                "Item Subtotal Tax",
                "Item Total",
                "Buyer Name",
                "Ordering Customer Email",
            ]

            for column in expected_columns:
                assert column in orders[0]

            # Verify data types and formats
            assert orders[0]["Order ID"].startswith("111-")
            assert "$" in orders[0]["Item Subtotal"]  # Currency format preserved

            # Verify multi-item order data
            assert orders[1]["Quantity"] == "2"  # Second order has 2 items

    def test_extract_with_account_name_detection(self, unzipper, erica_zip):
        """Test automatic account name detection from filename."""
        result = unzipper.extract_zip_file(erica_zip)

        # Verify account name was correctly detected
        assert result["success"] is True
        assert result["account_name"] == "erica"
        assert "_erica_amazon_data" in result["output_directory"]

        # Verify extracted content
        assert len(result["csv_files"]) == 1
        output_dir = Path(result["output_directory"])
        csv_path = output_dir / "Retail.OrderHistory.1.csv"

        with open(csv_path, encoding="utf-8") as f:
            reader = csv.DictReader(f)
            orders = list(reader)
            assert len(orders) == 1
            assert orders[0]["Order ID"] == "113-4445556-7778889"
            assert orders[0]["Buyer Name"] == "Erica Davis"

    def test_extract_with_explicit_account_name(self, unzipper, karl_zip):
        """Test extraction with explicitly provided account name."""
        result = unzipper.extract_zip_file(karl_zip, account_name="custom_account")

        assert result["success"] is True
        assert result["account_name"] == "custom_account"
        assert "_custom_account_amazon_data" in result["output_directory"]

    def test_extract_handles_duplicate_directory_names(self, unzipper, karl_zip):
        """Test that duplicate extractions create unique directories."""
        # First extraction
        result1 = unzipper.extract_zip_file(karl_zip)
        output_dir1 = Path(result1["output_directory"])
        assert output_dir1.exists()

        # Second extraction - should create new directory with sequence number
        result2 = unzipper.extract_zip_file(karl_zip)
        output_dir2 = Path(result2["output_directory"])
        assert output_dir2.exists()

        # Verify directories are different
        assert output_dir1 != output_dir2
        assert "_001" in output_dir2.name  # Should have sequence number

        # Verify both directories contain extracted files
        assert (output_dir1 / "Retail.OrderHistory.1.csv").exists()
        assert (output_dir2 / "Retail.OrderHistory.1.csv").exists()

    def test_extract_corrupted_zip_file(self, unzipper, corrupted_zip):
        """Test error handling for corrupted ZIP files."""
        with pytest.raises(ValueError) as exc_info:
            unzipper.extract_zip_file(corrupted_zip)

        error_msg = str(exc_info.value)
        assert "Invalid ZIP file" in error_msg
        assert "corrupted_amazon.zip" in error_msg

    def test_extract_nonexistent_zip_file(self, unzipper, temp_dir):
        """Test error handling for non-existent ZIP files."""
        nonexistent_zip = temp_dir / "nonexistent.zip"

        with pytest.raises(FileNotFoundError) as exc_info:
            unzipper.extract_zip_file(nonexistent_zip)

        assert "ZIP file not found" in str(exc_info.value)

    def test_scan_for_zip_files(self, unzipper, fixtures_dir):
        """Test ZIP file scanning functionality."""
        zip_files = unzipper.scan_for_zip_files(fixtures_dir)

        # Should find all valid ZIP files (karl, erica, corrupted)
        assert len(zip_files) == 3
        assert all(f.suffix == ".zip" for f in zip_files)

        # Verify sorted order
        zip_names = [f.name for f in zip_files]
        assert zip_names == sorted(zip_names)

    def test_scan_nonexistent_directory(self, unzipper, temp_dir):
        """Test scanning non-existent directory returns empty list."""
        nonexistent_dir = temp_dir / "nonexistent_directory"

        zip_files = unzipper.scan_for_zip_files(nonexistent_dir)
        assert zip_files == []

    def test_batch_extract_multiple_accounts(self, unzipper, fixtures_dir):
        """Test batch extraction of multiple account ZIP files."""
        # Create temporary download directory with valid ZIPs
        download_dir = unzipper.raw_data_dir.parent / "downloads"
        download_dir.mkdir(parents=True)

        # Copy valid ZIP files to download directory
        import shutil

        karl_zip = fixtures_dir / "amazon_orders_karl.zip"
        erica_zip = fixtures_dir / "amazon_orders_erica.zip"
        shutil.copy(karl_zip, download_dir / "amazon_orders_karl.zip")
        shutil.copy(erica_zip, download_dir / "amazon_orders_erica.zip")

        # Execute batch extraction
        result = unzipper.batch_extract(download_dir)

        # Verify batch success
        assert result["success"] is True
        assert result["files_processed"] == 2
        assert result["files_failed"] == 0
        assert len(result["extractions"]) == 2
        assert len(result["errors"]) == 0

        # Verify both accounts were extracted
        accounts = {extract["account_name"] for extract in result["extractions"]}
        assert accounts == {"karl", "erica"}

        # Verify all output directories exist
        for extraction in result["extractions"]:
            output_dir = Path(extraction["output_directory"])
            assert output_dir.exists()
            assert (output_dir / "Retail.OrderHistory.1.csv").exists()

    def test_batch_extract_empty_directory(self, unzipper, temp_dir):
        """Test batch extraction with no ZIP files."""
        empty_dir = temp_dir / "empty"
        empty_dir.mkdir()

        result = unzipper.batch_extract(empty_dir)

        assert result["success"] is True
        assert result["files_processed"] == 0
        assert result["message"] == "No ZIP files found to extract"
        assert result["extractions"] == []

    def test_batch_extract_with_errors(self, unzipper, fixtures_dir):
        """Test batch extraction handles errors gracefully."""
        # Create download directory with mix of valid and corrupted files
        download_dir = unzipper.raw_data_dir.parent / "downloads"
        download_dir.mkdir(parents=True)

        import shutil

        karl_zip = fixtures_dir / "amazon_orders_karl.zip"
        corrupted_zip = fixtures_dir / "corrupted_amazon.zip"
        shutil.copy(karl_zip, download_dir / "amazon_orders_karl.zip")
        shutil.copy(corrupted_zip, download_dir / "corrupted_amazon.zip")

        result = unzipper.batch_extract(download_dir)

        # Verify partial success
        assert result["success"] is False  # Has errors
        assert result["files_processed"] == 1  # One succeeded
        assert result["files_failed"] == 1  # One failed
        assert len(result["extractions"]) == 1
        assert len(result["errors"]) == 1

        # Verify error information
        error = result["errors"][0]
        assert "corrupted_amazon.zip" in error["zip_file"]
        assert "error" in error
        assert "timestamp" in error

    def test_convenience_function(self, temp_dir, fixtures_dir):
        """Test convenience function for extracting Amazon ZIP files."""
        import shutil

        download_dir = temp_dir / "downloads"
        download_dir.mkdir()
        raw_data_dir = temp_dir / "amazon" / "raw"

        # Copy test ZIP file
        karl_zip = fixtures_dir / "amazon_orders_karl.zip"
        shutil.copy(karl_zip, download_dir / "amazon_orders_karl.zip")

        # Use convenience function
        result = extract_amazon_zip_files(download_dir, raw_data_dir)

        # Verify successful extraction
        assert result["success"] is True
        assert result["files_processed"] == 1
        assert len(result["extractions"]) == 1

        # Verify raw data directory was created
        assert raw_data_dir.exists()

        # Verify extraction output
        extraction = result["extractions"][0]
        output_dir = Path(extraction["output_directory"])
        assert output_dir.exists()
        assert (output_dir / "Retail.OrderHistory.1.csv").exists()
