#!/usr/bin/env python3
"""
Unit tests for Analysis DataStore implementations.
"""

import tempfile
from datetime import datetime
from pathlib import Path

import pytest

from finances.analysis.datastore import CashFlowResultsStore


class TestCashFlowResultsStore:
    """Test CashFlowResultsStore behavior."""

    def setup_method(self):
        """Set up test fixtures."""
        self.temp_dir = Path(tempfile.mkdtemp())
        self.charts_dir = self.temp_dir / "cash_flow" / "charts"
        self.store = CashFlowResultsStore(self.charts_dir)

    def teardown_method(self):
        """Clean up test fixtures."""
        import shutil

        shutil.rmtree(self.temp_dir)

    def test_exists_returns_false_when_no_directory(self):
        """Test exists() returns False when directory doesn't exist."""
        assert not self.store.exists()

    def test_exists_returns_false_when_no_chart_files(self):
        """Test exists() returns False when directory exists but has no chart files."""
        self.charts_dir.mkdir(parents=True, exist_ok=True)
        assert not self.store.exists()

    def test_exists_returns_true_when_chart_files_present(self):
        """Test exists() returns True when chart files are present."""
        self.charts_dir.mkdir(parents=True, exist_ok=True)
        chart_file = self.charts_dir / "2024-10-01_cash_flow_dashboard.png"
        # Create a minimal PNG file (PNG header)
        chart_file.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)

        assert self.store.exists()

    def test_load_returns_chart_file_paths(self):
        """Test load() returns list of chart file paths."""
        self.charts_dir.mkdir(parents=True, exist_ok=True)
        chart_file1 = self.charts_dir / "dashboard_2024-10.png"
        chart_file2 = self.charts_dir / "dashboard_2024-11.png"
        chart_file1.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)
        chart_file2.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)

        result = self.store.load()
        assert len(result) == 2
        assert all(p.suffix == ".png" for p in result)

    def test_load_raises_when_no_directory(self):
        """Test load() raises FileNotFoundError when directory doesn't exist."""
        with pytest.raises(FileNotFoundError):
            self.store.load()

    def test_load_raises_when_no_files(self):
        """Test load() raises FileNotFoundError when no chart files exist."""
        self.charts_dir.mkdir(parents=True, exist_ok=True)
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
        self.charts_dir.mkdir(parents=True, exist_ok=True)
        chart_file = self.charts_dir / "dashboard.png"
        chart_file.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)

        result = self.store.last_modified()
        assert result is not None
        assert isinstance(result, datetime)

    def test_age_days_returns_none_when_no_files(self):
        """Test age_days() returns None when no files exist."""
        assert self.store.age_days() is None

    def test_age_days_returns_integer(self):
        """Test age_days() returns integer when files exist."""
        self.charts_dir.mkdir(parents=True, exist_ok=True)
        chart_file = self.charts_dir / "dashboard.png"
        chart_file.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)

        result = self.store.age_days()
        assert result is not None
        assert isinstance(result, int)
        assert result >= 0

    def test_item_count_returns_none_when_no_files(self):
        """Test item_count() returns None when no files exist."""
        assert self.store.item_count() is None

    def test_item_count_returns_chart_file_count(self):
        """Test item_count() returns count of chart files."""
        self.charts_dir.mkdir(parents=True, exist_ok=True)
        chart_file1 = self.charts_dir / "dashboard_1.png"
        chart_file2 = self.charts_dir / "dashboard_2.png"
        chart_file1.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)
        chart_file2.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)

        result = self.store.item_count()
        assert result == 2

    def test_size_bytes_returns_none_when_no_files(self):
        """Test size_bytes() returns None when no files exist."""
        assert self.store.size_bytes() is None

    def test_size_bytes_returns_total_size(self):
        """Test size_bytes() returns total size of all chart files."""
        self.charts_dir.mkdir(parents=True, exist_ok=True)
        chart_file = self.charts_dir / "dashboard.png"
        chart_data = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100
        chart_file.write_bytes(chart_data)

        result = self.store.size_bytes()
        assert result is not None
        assert result == len(chart_data)

    def test_size_bytes_sums_multiple_files(self):
        """Test size_bytes() sums sizes of multiple chart files."""
        self.charts_dir.mkdir(parents=True, exist_ok=True)
        chart_file1 = self.charts_dir / "dashboard_1.png"
        chart_file2 = self.charts_dir / "dashboard_2.png"
        data1 = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100
        data2 = b"\x89PNG\r\n\x1a\n" + b"\x00" * 200
        chart_file1.write_bytes(data1)
        chart_file2.write_bytes(data2)

        result = self.store.size_bytes()
        assert result == len(data1) + len(data2)

    def test_summary_text_when_no_files(self):
        """Test summary_text() returns appropriate message when no files."""
        assert self.store.summary_text() == "No cash flow charts found"

    def test_summary_text_when_files_present(self):
        """Test summary_text() returns count message when files present."""
        self.charts_dir.mkdir(parents=True, exist_ok=True)
        chart_file = self.charts_dir / "dashboard.png"
        chart_file.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)

        assert self.store.summary_text() == "Cash flow charts: 1 files"

    def test_summary_text_pluralization(self):
        """Test summary_text() handles plural correctly."""
        self.charts_dir.mkdir(parents=True, exist_ok=True)
        chart_file1 = self.charts_dir / "dashboard_1.png"
        chart_file2 = self.charts_dir / "dashboard_2.png"
        chart_file1.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)
        chart_file2.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)

        assert self.store.summary_text() == "Cash flow charts: 2 files"

    def test_to_node_data_summary(self):
        """Test to_node_data_summary() returns NodeDataSummary."""
        self.charts_dir.mkdir(parents=True, exist_ok=True)
        chart_file = self.charts_dir / "dashboard.png"
        chart_file.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)

        summary = self.store.to_node_data_summary()
        assert summary.exists
        assert summary.last_updated is not None
        assert summary.age_days is not None
        assert summary.item_count == 1
        assert summary.size_bytes is not None
        assert "Cash flow charts" in summary.summary_text

    def test_to_node_data_summary_when_no_data(self):
        """Test to_node_data_summary() when no data exists."""
        summary = self.store.to_node_data_summary()
        assert not summary.exists
        assert summary.last_updated is None
        assert summary.age_days is None
        assert summary.item_count is None
        assert summary.size_bytes is None
        assert "No cash flow charts found" in summary.summary_text
