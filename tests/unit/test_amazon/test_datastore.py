#!/usr/bin/env python3
"""
Unit tests for Amazon DataStore implementations.
"""

import tempfile
from datetime import datetime
from pathlib import Path

import pytest

from finances.amazon.datastore import AmazonMatchResultsStore, AmazonRawDataStore
from finances.core.json_utils import write_json


class TestAmazonRawDataStore:
    """Test AmazonRawDataStore behavior."""

    def setup_method(self):
        """Set up test fixtures."""
        self.temp_dir = Path(tempfile.mkdtemp())
        self.raw_dir = self.temp_dir / "amazon" / "raw"
        self.store = AmazonRawDataStore(self.raw_dir)

    def teardown_method(self):
        """Clean up test fixtures."""
        import shutil

        shutil.rmtree(self.temp_dir)

    def test_exists_returns_false_when_no_directory(self):
        """Test exists() returns False when directory doesn't exist."""
        assert not self.store.exists()

    def test_exists_returns_false_when_no_csv_files(self):
        """Test exists() returns False when directory exists but has no CSV files."""
        self.raw_dir.mkdir(parents=True, exist_ok=True)
        assert not self.store.exists()

    def test_exists_returns_true_when_csv_files_present(self):
        """Test exists() returns True when CSV files are present."""
        account_dir = self.raw_dir / "2024-10-01_account1_amazon_data"
        account_dir.mkdir(parents=True, exist_ok=True)
        csv_file = account_dir / "Retail.OrderHistory.1.csv"
        csv_file.write_text("order_id,total\n123,12.34\n")

        assert self.store.exists()

    def test_load_returns_csv_file_paths(self):
        """Test load() returns list of CSV file paths."""
        account_dir = self.raw_dir / "2024-10-01_account1_amazon_data"
        account_dir.mkdir(parents=True, exist_ok=True)
        csv_file = account_dir / "Retail.OrderHistory.1.csv"
        csv_file.write_text("order_id,total\n123,12.34\n")

        result = self.store.load()
        assert len(result) == 1
        assert result[0] == csv_file

    def test_load_raises_when_no_files(self):
        """Test load() raises FileNotFoundError when no files exist."""
        with pytest.raises(FileNotFoundError):
            self.store.load()

    def test_save_raises_not_implemented(self):
        """Test save() raises NotImplementedError."""
        with pytest.raises(NotImplementedError):
            self.store.save([])

    def test_last_modified_returns_none_when_no_files(self):
        """Test last_modified() returns None when no files exist."""
        assert self.store.last_modified() is None

    def test_last_modified_returns_most_recent_timestamp(self):
        """Test last_modified() returns timestamp of most recent file."""
        account_dir = self.raw_dir / "2024-10-01_account1_amazon_data"
        account_dir.mkdir(parents=True, exist_ok=True)
        csv_file = account_dir / "Retail.OrderHistory.1.csv"
        csv_file.write_text("order_id,total\n123,12.34\n")

        result = self.store.last_modified()
        assert result is not None
        assert isinstance(result, datetime)

    def test_age_days_returns_none_when_no_files(self):
        """Test age_days() returns None when no files exist."""
        assert self.store.age_days() is None

    def test_age_days_returns_integer(self):
        """Test age_days() returns integer when files exist."""
        account_dir = self.raw_dir / "2024-10-01_account1_amazon_data"
        account_dir.mkdir(parents=True, exist_ok=True)
        csv_file = account_dir / "Retail.OrderHistory.1.csv"
        csv_file.write_text("order_id,total\n123,12.34\n")

        result = self.store.age_days()
        assert result is not None
        assert isinstance(result, int)
        assert result >= 0

    def test_item_count_returns_none_when_no_files(self):
        """Test item_count() returns None when no files exist."""
        assert self.store.item_count() is None

    def test_item_count_returns_csv_file_count(self):
        """Test item_count() returns count of CSV files."""
        account_dir = self.raw_dir / "2024-10-01_account1_amazon_data"
        account_dir.mkdir(parents=True, exist_ok=True)
        csv_file1 = account_dir / "Retail.OrderHistory.1.csv"
        csv_file1.write_text("order_id,total\n123,12.34\n")
        csv_file2 = account_dir / "Retail.OrderHistory.2.csv"
        csv_file2.write_text("order_id,total\n456,45.67\n")

        result = self.store.item_count()
        assert result == 2

    def test_size_bytes_returns_none_when_no_files(self):
        """Test size_bytes() returns None when no files exist."""
        assert self.store.size_bytes() is None

    def test_size_bytes_returns_total_size(self):
        """Test size_bytes() returns total size of all CSV files."""
        account_dir = self.raw_dir / "2024-10-01_account1_amazon_data"
        account_dir.mkdir(parents=True, exist_ok=True)
        csv_file = account_dir / "Retail.OrderHistory.1.csv"
        csv_file.write_text("order_id,total\n123,12.34\n")

        result = self.store.size_bytes()
        assert result is not None
        assert result > 0

    def test_summary_text_when_no_files(self):
        """Test summary_text() returns appropriate message when no files."""
        assert self.store.summary_text() == "No Amazon raw data found"

    def test_summary_text_when_files_present(self):
        """Test summary_text() returns count message when files present."""
        account_dir = self.raw_dir / "2024-10-01_account1_amazon_data"
        account_dir.mkdir(parents=True, exist_ok=True)
        csv_file = account_dir / "Retail.OrderHistory.1.csv"
        csv_file.write_text("order_id,total\n123,12.34\n")

        assert self.store.summary_text() == "Amazon data: 1 account(s)"

    def test_to_node_data_summary(self):
        """Test to_node_data_summary() returns NodeDataSummary."""
        account_dir = self.raw_dir / "2024-10-01_account1_amazon_data"
        account_dir.mkdir(parents=True, exist_ok=True)
        csv_file = account_dir / "Retail.OrderHistory.1.csv"
        csv_file.write_text("order_id,total\n123,12.34\n")

        summary = self.store.to_node_data_summary()
        assert summary.exists
        assert summary.last_updated is not None
        assert summary.age_days is not None
        assert summary.item_count == 1
        assert summary.size_bytes is not None
        assert "Amazon data" in summary.summary_text


class TestAmazonMatchResultsStore:
    """Test AmazonMatchResultsStore behavior."""

    def setup_method(self):
        """Set up test fixtures."""
        self.temp_dir = Path(tempfile.mkdtemp())
        self.matches_dir = self.temp_dir / "amazon" / "transaction_matches"
        self.store = AmazonMatchResultsStore(self.matches_dir)

    def teardown_method(self):
        """Clean up test fixtures."""
        import shutil

        shutil.rmtree(self.temp_dir)

    def test_exists_returns_false_when_no_directory(self):
        """Test exists() returns False when directory doesn't exist."""
        assert not self.store.exists()

    def test_exists_returns_true_when_json_files_present(self):
        """Test exists() returns True when JSON files are present."""
        self.matches_dir.mkdir(parents=True, exist_ok=True)
        match_file = self.matches_dir / "2024-10-01_12-00-00_amazon_matching_results.json"
        write_json(match_file, {"matches": []})

        assert self.store.exists()

    def test_load_returns_most_recent_match_results(self):
        """Test load() returns most recent matching results."""
        self.matches_dir.mkdir(parents=True, exist_ok=True)
        match_data = {"matches": [{"transaction_id": "123", "confidence": 0.95}]}
        match_file = self.matches_dir / "2024-10-01_12-00-00_amazon_matching_results.json"
        write_json(match_file, match_data)

        result = self.store.load()
        assert result["matches"][0]["transaction_id"] == "123"

    def test_load_raises_when_no_files(self):
        """Test load() raises FileNotFoundError when no files exist."""
        with pytest.raises(FileNotFoundError):
            self.store.load()

    def test_save_creates_timestamped_file(self):
        """Test save() creates file with timestamp."""
        match_data = {"matches": [{"transaction_id": "123"}]}
        self.store.save(match_data)

        assert self.matches_dir.exists()
        json_files = list(self.matches_dir.glob("*.json"))
        assert len(json_files) == 1
        assert "amazon_matching_results" in json_files[0].name

    def test_item_count_returns_match_count(self):
        """Test item_count() returns count of matches."""
        self.matches_dir.mkdir(parents=True, exist_ok=True)
        match_data = {
            "matches": [
                {"transaction_id": "123"},
                {"transaction_id": "456"},
            ]
        }
        match_file = self.matches_dir / "2024-10-01_12-00-00_amazon_matching_results.json"
        write_json(match_file, match_data)

        result = self.store.item_count()
        assert result == 2

    def test_item_count_returns_zero_for_invalid_structure(self):
        """Test item_count() returns 0 for invalid JSON structure."""
        self.matches_dir.mkdir(parents=True, exist_ok=True)
        match_file = self.matches_dir / "2024-10-01_12-00-00_amazon_matching_results.json"
        write_json(match_file, "not a dict")

        result = self.store.item_count()
        assert result == 0

    def test_summary_text_when_no_files(self):
        """Test summary_text() returns appropriate message when no files."""
        assert self.store.summary_text() == "No Amazon matches found"

    def test_summary_text_when_files_present(self):
        """Test summary_text() returns count message when files present."""
        self.matches_dir.mkdir(parents=True, exist_ok=True)
        match_data = {"matches": [{"transaction_id": "123"}]}
        match_file = self.matches_dir / "2024-10-01_12-00-00_amazon_matching_results.json"
        write_json(match_file, match_data)

        assert self.store.summary_text() == "Amazon matches: 1 transactions"
