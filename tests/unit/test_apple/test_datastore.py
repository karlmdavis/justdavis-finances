#!/usr/bin/env python3
"""
Unit tests for Apple DataStore implementations.
"""

import tempfile
from datetime import datetime
from pathlib import Path

import pytest

from finances.apple.datastore import (
    AppleEmailStore,
    AppleMatchResultsStore,
    AppleReceiptStore,
)
from finances.core.json_utils import write_json


class TestAppleEmailStore:
    """Test AppleEmailStore behavior."""

    def setup_method(self):
        """Set up test fixtures."""
        self.temp_dir = Path(tempfile.mkdtemp())
        self.emails_dir = self.temp_dir / "apple" / "emails"
        self.store = AppleEmailStore(self.emails_dir)

    def teardown_method(self):
        """Clean up test fixtures."""
        import shutil

        shutil.rmtree(self.temp_dir)

    def test_load_returns_email_file_paths(self):
        """Test load() returns list of email file paths."""
        self.emails_dir.mkdir(parents=True, exist_ok=True)
        email_file1 = self.emails_dir / "receipt_123.eml"
        email_file1.write_text("Subject: Receipt 1\n\nTest")
        email_file2 = self.emails_dir / "receipt_456.eml"
        email_file2.write_text("Subject: Receipt 2\n\nTest")

        result = self.store.load()
        assert len(result) == 2
        assert all(p.suffix == ".eml" for p in result)

    def test_save_raises_not_implemented(self):
        """Test save() raises NotImplementedError."""
        with pytest.raises(NotImplementedError):
            self.store.save([])

    def test_to_node_data_summary(self):
        """Test to_node_data_summary() returns NodeDataSummary."""
        self.emails_dir.mkdir(parents=True, exist_ok=True)
        email_file = self.emails_dir / "receipt_123.eml"
        email_file.write_text("Test")

        summary = self.store.to_node_data_summary()
        assert summary.exists
        assert summary.last_updated is not None
        assert summary.item_count == 1
        assert "Apple emails" in summary.summary_text


class TestAppleReceiptStore:
    """Test AppleReceiptStore behavior."""

    def setup_method(self):
        """Set up test fixtures."""
        self.temp_dir = Path(tempfile.mkdtemp())
        self.exports_dir = self.temp_dir / "apple" / "exports"
        self.store = AppleReceiptStore(self.exports_dir)

    def teardown_method(self):
        """Clean up test fixtures."""
        import shutil

        shutil.rmtree(self.temp_dir)

    def test_load_returns_list_of_receipts(self):
        """Test load() returns list of receipt dictionaries."""
        self.exports_dir.mkdir(parents=True, exist_ok=True)
        receipt1 = {"order_id": "M12345", "total": "12.34"}
        receipt2 = {"order_id": "M67890", "total": "45.67"}
        write_json(self.exports_dir / "M12345.json", receipt1)
        write_json(self.exports_dir / "M67890.json", receipt2)

        result = self.store.load()
        assert len(result) == 2
        assert all(isinstance(r, dict) for r in result)

    def test_save_creates_files_with_order_ids(self):
        """Test save() creates files named after order IDs."""
        receipts = [
            {"order_id": "M12345", "total": "12.34"},
            {"order_id": "M67890", "total": "45.67"},
        ]
        self.store.save(receipts)

        assert (self.exports_dir / "M12345.json").exists()
        assert (self.exports_dir / "M67890.json").exists()

    def test_save_handles_receipts_without_order_id(self):
        """Test save() handles receipts without order_id field."""
        receipts = [{"id": "receipt123", "total": "12.34"}]
        self.store.save(receipts)

        json_files = list(self.exports_dir.glob("*.json"))
        assert len(json_files) == 1


class TestAppleMatchResultsStore:
    """Test AppleMatchResultsStore behavior."""

    def setup_method(self):
        """Set up test fixtures."""
        self.temp_dir = Path(tempfile.mkdtemp())
        self.matches_dir = self.temp_dir / "apple" / "transaction_matches"
        self.store = AppleMatchResultsStore(self.matches_dir)

    def teardown_method(self):
        """Clean up test fixtures."""
        import shutil

        shutil.rmtree(self.temp_dir)

    def test_load_returns_most_recent_match_results(self):
        """Test load() returns most recent matching results."""
        self.matches_dir.mkdir(parents=True, exist_ok=True)
        match_data = {"matches": [{"transaction_id": "t1", "confidence": 0.95}]}
        match_file = self.matches_dir / "2024-10-01_12-00-00_apple_matching_results.json"
        write_json(match_file, match_data)

        result = self.store.load()
        assert result["matches"][0]["transaction_id"] == "t1"

    def test_save_creates_timestamped_file(self):
        """Test save() creates file with timestamp."""
        match_data = {"matches": [{"transaction_id": "t1"}]}
        self.store.save(match_data)

        assert self.matches_dir.exists()
        json_files = list(self.matches_dir.glob("*.json"))
        assert len(json_files) == 1
        assert "apple_matching_results" in json_files[0].name

    def test_item_count_returns_match_count(self):
        """Test item_count() returns count of matches."""
        self.matches_dir.mkdir(parents=True, exist_ok=True)
        match_data = {
            "matches": [
                {"transaction_id": "t1"},
                {"transaction_id": "t2"},
            ]
        }
        match_file = self.matches_dir / "2024-10-01_12-00-00_apple_matching_results.json"
        write_json(match_file, match_data)

        result = self.store.item_count()
        assert result == 2

    def test_item_count_returns_none_for_invalid_structure(self):
        """Test item_count() returns None for invalid JSON structure."""
        self.matches_dir.mkdir(parents=True, exist_ok=True)
        match_file = self.matches_dir / "2024-10-01_12-00-00_apple_matching_results.json"
        write_json(match_file, "not a dict")

        result = self.store.item_count()
        assert result is None
