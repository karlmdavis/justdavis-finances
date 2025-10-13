#!/usr/bin/env python3
"""
Unit Tests for Change Detection System

Tests all change detector classes with real file system operations using
temporary directories. No mocking required - tests verify actual change
detection logic based on file system state.
"""

import tempfile
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from finances.core.change_detection import (
    AmazonMatchingChangeDetector,
    AmazonUnzipChangeDetector,
    AppleEmailChangeDetector,
    AppleMatchingChangeDetector,
    ChangeDetector,
    RetirementUpdateChangeDetector,
    YnabSyncChangeDetector,
    create_change_detectors,
    get_change_detector_function,
)
from finances.core.flow import FlowContext
from finances.core.json_utils import write_json


@pytest.fixture
def temp_data_dir():
    """Create temporary data directory for testing."""
    with tempfile.TemporaryDirectory() as temp_dir:
        yield Path(temp_dir)


@pytest.fixture
def flow_context():
    """Create a basic flow context for testing."""
    return FlowContext(start_time=datetime.now())


class TestChangeDetectorBase:
    """Tests for ChangeDetector base class."""

    def test_init_creates_cache_directory(self, temp_data_dir):
        """Test that initializing detector creates cache directory."""
        detector = ChangeDetector(temp_data_dir)

        assert detector.cache_dir.exists()
        assert detector.cache_dir == temp_data_dir / "cache" / "flow"

    def test_get_cache_file(self, temp_data_dir):
        """Test cache file path generation."""
        detector = ChangeDetector(temp_data_dir)

        cache_file = detector.get_cache_file("test_node")

        assert cache_file == temp_data_dir / "cache" / "flow" / "test_node_last_check.json"

    def test_load_last_check_state_no_file(self, temp_data_dir):
        """Test loading state when no cache file exists."""
        detector = ChangeDetector(temp_data_dir)

        state = detector.load_last_check_state("test_node")

        assert state == {}

    def test_save_and_load_last_check_state(self, temp_data_dir):
        """Test saving and loading check state."""
        detector = ChangeDetector(temp_data_dir)

        test_state = {"last_run": "2024-01-01T00:00:00", "file_count": 5}
        detector.save_last_check_state("test_node", test_state)

        loaded_state = detector.load_last_check_state("test_node")

        assert loaded_state == test_state

    def test_get_file_modification_times_empty_directory(self, temp_data_dir):
        """Test getting modification times from empty directory."""
        detector = ChangeDetector(temp_data_dir)
        test_dir = temp_data_dir / "test"
        test_dir.mkdir()

        mod_times = detector.get_file_modification_times(test_dir)

        assert mod_times == {}

    def test_get_file_modification_times_with_files(self, temp_data_dir):
        """Test getting modification times with files."""
        detector = ChangeDetector(temp_data_dir)
        test_dir = temp_data_dir / "test"
        test_dir.mkdir()

        # Create test files
        (test_dir / "file1.txt").write_text("content1")
        (test_dir / "file2.txt").write_text("content2")

        mod_times = detector.get_file_modification_times(test_dir, "*.txt")

        assert len(mod_times) == 2
        assert "file1.txt" in mod_times
        assert "file2.txt" in mod_times
        assert all(isinstance(v, float) for v in mod_times.values())

    def test_get_directory_listing_empty(self, temp_data_dir):
        """Test directory listing for empty directory."""
        detector = ChangeDetector(temp_data_dir)
        test_dir = temp_data_dir / "test"
        test_dir.mkdir()

        listing = detector.get_directory_listing(test_dir)

        assert listing == []

    def test_get_directory_listing_with_items(self, temp_data_dir):
        """Test directory listing with items."""
        detector = ChangeDetector(temp_data_dir)
        test_dir = temp_data_dir / "test"
        test_dir.mkdir()

        (test_dir / "file1.txt").write_text("content")
        (test_dir / "subdir").mkdir()

        listing = detector.get_directory_listing(test_dir)

        assert sorted(listing) == ["file1.txt", "subdir"]


class TestYnabSyncChangeDetector:
    """Tests for YNAB sync change detection."""

    def test_detects_missing_cache_files(self, temp_data_dir, flow_context):
        """Test detection when cache files are missing."""
        detector = YnabSyncChangeDetector(temp_data_dir)

        has_changes, reasons = detector.check_changes(flow_context)

        assert has_changes is True
        assert "Missing cache files" in reasons[0]

    def test_no_changes_when_fresh(self, temp_data_dir, flow_context):
        """Test no changes detected when cache is fresh."""
        # Create YNAB cache files
        ynab_cache_dir = temp_data_dir / "ynab" / "cache"
        ynab_cache_dir.mkdir(parents=True)

        write_json(ynab_cache_dir / "accounts.json", {"accounts": [], "server_knowledge": 100})
        write_json(ynab_cache_dir / "categories.json", {"category_groups": [], "server_knowledge": 50})
        write_json(ynab_cache_dir / "transactions.json", [])

        detector = YnabSyncChangeDetector(temp_data_dir)

        # First check - should detect changes (either new server_knowledge or no previous sync)
        has_changes1, reasons1 = detector.check_changes(flow_context)
        assert has_changes1 is True
        # Could be either reason depending on state
        assert len(reasons1) > 0

        # Second check immediately after - should show no changes
        has_changes2, reasons2 = detector.check_changes(flow_context)
        assert has_changes2 is False
        assert "No changes detected" in reasons2[0]

    def test_detects_server_knowledge_change_accounts(self, temp_data_dir, flow_context):
        """Test detection when accounts server_knowledge changes."""
        ynab_cache_dir = temp_data_dir / "ynab" / "cache"
        ynab_cache_dir.mkdir(parents=True)

        # Initial state
        write_json(ynab_cache_dir / "accounts.json", {"accounts": [], "server_knowledge": 100})
        write_json(ynab_cache_dir / "categories.json", {"category_groups": [], "server_knowledge": 50})
        write_json(ynab_cache_dir / "transactions.json", [])

        detector = YnabSyncChangeDetector(temp_data_dir)

        # First check to establish baseline
        detector.check_changes(flow_context)

        # Change accounts server_knowledge
        write_json(ynab_cache_dir / "accounts.json", {"accounts": [], "server_knowledge": 101})

        has_changes, reasons = detector.check_changes(flow_context)

        assert has_changes is True
        assert any("accounts server_knowledge changed" in r for r in reasons)

    def test_detects_server_knowledge_change_categories(self, temp_data_dir, flow_context):
        """Test detection when categories server_knowledge changes."""
        ynab_cache_dir = temp_data_dir / "ynab" / "cache"
        ynab_cache_dir.mkdir(parents=True)

        # Initial state
        write_json(ynab_cache_dir / "accounts.json", {"accounts": [], "server_knowledge": 100})
        write_json(ynab_cache_dir / "categories.json", {"category_groups": [], "server_knowledge": 50})
        write_json(ynab_cache_dir / "transactions.json", [])

        detector = YnabSyncChangeDetector(temp_data_dir)

        # First check to establish baseline
        detector.check_changes(flow_context)

        # Change categories server_knowledge
        write_json(ynab_cache_dir / "categories.json", {"category_groups": [], "server_knowledge": 51})

        has_changes, reasons = detector.check_changes(flow_context)

        assert has_changes is True
        assert any("categories server_knowledge changed" in r for r in reasons)

    def test_detects_time_based_refresh(self, temp_data_dir, flow_context):
        """Test detection after 24-hour refresh interval."""
        ynab_cache_dir = temp_data_dir / "ynab" / "cache"
        ynab_cache_dir.mkdir(parents=True)

        write_json(ynab_cache_dir / "accounts.json", {"accounts": [], "server_knowledge": 100})
        write_json(ynab_cache_dir / "categories.json", {"category_groups": [], "server_knowledge": 50})
        write_json(ynab_cache_dir / "transactions.json", [])

        detector = YnabSyncChangeDetector(temp_data_dir)

        # Manually set last sync time to 25 hours ago
        old_time = (datetime.now() - timedelta(hours=25)).isoformat()
        detector.save_last_check_state(
            "ynab_sync",
            {
                "last_sync_time": old_time,
                "accounts_server_knowledge": 100,
                "categories_server_knowledge": 50,
            },
        )

        has_changes, reasons = detector.check_changes(flow_context)

        assert has_changes is True
        assert any("24-hour refresh interval reached" in r for r in reasons)


class TestAmazonUnzipChangeDetector:
    """Tests for Amazon unzip change detection."""

    def test_no_zip_files(self, temp_data_dir, flow_context):
        """Test when no Amazon ZIP files are present."""
        detector = AmazonUnzipChangeDetector(temp_data_dir)

        has_changes, reasons = detector.check_changes(flow_context)

        assert has_changes is False
        assert "No new Amazon ZIP files detected" in reasons[0]

    def test_detects_new_zip_file(self, temp_data_dir, flow_context):
        """Test detection of new Amazon ZIP file in Downloads."""
        downloads_dir = Path.home() / "Downloads"
        if not downloads_dir.exists():
            pytest.skip("Downloads directory does not exist")

        detector = AmazonUnzipChangeDetector(temp_data_dir)

        # Establish baseline (no files)
        detector.check_changes(flow_context)

        # Create a test Amazon ZIP file in Downloads
        test_zip = downloads_dir / "amazon_order_history_test.zip"
        try:
            test_zip.write_bytes(b"PK\x03\x04")  # Minimal ZIP signature

            has_changes, reasons = detector.check_changes(flow_context)

            assert has_changes is True
            assert "New Amazon ZIP files detected" in reasons[0]
        finally:
            # Cleanup
            if test_zip.exists():
                test_zip.unlink()


class TestAmazonMatchingChangeDetector:
    """Tests for Amazon matching change detection."""

    def test_no_changes_empty_directories(self, temp_data_dir, flow_context):
        """Test no changes when directories are empty."""
        detector = AmazonMatchingChangeDetector(temp_data_dir)

        has_changes, reasons = detector.check_changes(flow_context)

        assert has_changes is False
        assert "No changes in Amazon data or YNAB transactions" in reasons[0]

    def test_detects_new_amazon_directory(self, temp_data_dir, flow_context):
        """Test detection of new Amazon data directory."""
        amazon_raw_dir = temp_data_dir / "amazon" / "raw"
        amazon_raw_dir.mkdir(parents=True)

        detector = AmazonMatchingChangeDetector(temp_data_dir)

        # Establish baseline
        detector.check_changes(flow_context)

        # Add new directory
        (amazon_raw_dir / "2024-01-01_account_amazon_data").mkdir()

        has_changes, reasons = detector.check_changes(flow_context)

        assert has_changes is True
        assert any("New Amazon data directories" in r for r in reasons)

    def test_detects_ynab_transactions_update(self, temp_data_dir, flow_context):
        """Test detection when YNAB transactions file is updated."""
        ynab_cache_dir = temp_data_dir / "ynab" / "cache"
        ynab_cache_dir.mkdir(parents=True)

        transactions_file = ynab_cache_dir / "transactions.json"
        write_json(transactions_file, [{"id": "tx1"}])

        detector = AmazonMatchingChangeDetector(temp_data_dir)

        # Establish baseline
        detector.check_changes(flow_context)

        # Update transactions file
        import time

        time.sleep(0.01)  # Ensure different modification time
        write_json(transactions_file, [{"id": "tx1"}, {"id": "tx2"}])

        has_changes, reasons = detector.check_changes(flow_context)

        assert has_changes is True
        assert any("YNAB transactions cache updated" in r for r in reasons)


class TestAppleEmailChangeDetector:
    """Tests for Apple email change detection."""

    def test_first_run_triggers_fetch(self, temp_data_dir, flow_context):
        """Test that first run triggers email fetch."""
        detector = AppleEmailChangeDetector(temp_data_dir)

        has_changes, reasons = detector.check_changes(flow_context)

        assert has_changes is True
        assert "No previous fetch time recorded" in reasons[0]

    def test_no_fetch_within_interval(self, temp_data_dir, flow_context):
        """Test no fetch needed within 12-hour interval."""
        detector = AppleEmailChangeDetector(temp_data_dir)

        # First check
        detector.check_changes(flow_context)

        # Second check immediately after
        has_changes, reasons = detector.check_changes(flow_context)

        assert has_changes is False
        assert "Next fetch in" in reasons[0]

    def test_detects_interval_expiration(self, temp_data_dir, flow_context):
        """Test detection after 12-hour interval expires."""
        detector = AppleEmailChangeDetector(temp_data_dir)

        # Manually set last fetch time to 13 hours ago
        old_time = (datetime.now() - timedelta(hours=13)).isoformat()
        detector.save_last_check_state("apple_email_fetch", {"last_fetch_time": old_time})

        has_changes, reasons = detector.check_changes(flow_context)

        assert has_changes is True
        assert "12-hour email fetch interval reached" in reasons[0]


class TestAppleMatchingChangeDetector:
    """Tests for Apple matching change detection."""

    def test_no_changes_empty_directories(self, temp_data_dir, flow_context):
        """Test no changes when directories are empty."""
        detector = AppleMatchingChangeDetector(temp_data_dir)

        has_changes, reasons = detector.check_changes(flow_context)

        assert has_changes is False
        assert "No changes in Apple exports or YNAB transactions" in reasons[0]

    def test_detects_new_apple_export_directory(self, temp_data_dir, flow_context):
        """Test detection of new Apple export directory."""
        apple_exports_dir = temp_data_dir / "apple" / "exports"
        apple_exports_dir.mkdir(parents=True)

        detector = AppleMatchingChangeDetector(temp_data_dir)

        # Establish baseline
        detector.check_changes(flow_context)

        # Add new directory
        (apple_exports_dir / "2024-01-01_export").mkdir()

        has_changes, reasons = detector.check_changes(flow_context)

        assert has_changes is True
        assert any("New Apple export directories" in r for r in reasons)

    def test_detects_ynab_transactions_update(self, temp_data_dir, flow_context):
        """Test detection when YNAB transactions file is updated."""
        ynab_cache_dir = temp_data_dir / "ynab" / "cache"
        ynab_cache_dir.mkdir(parents=True)

        transactions_file = ynab_cache_dir / "transactions.json"
        write_json(transactions_file, [{"id": "tx1"}])

        detector = AppleMatchingChangeDetector(temp_data_dir)

        # Establish baseline
        detector.check_changes(flow_context)

        # Update transactions file
        import time

        time.sleep(0.01)  # Ensure different modification time
        write_json(transactions_file, [{"id": "tx1"}, {"id": "tx2"}])

        has_changes, reasons = detector.check_changes(flow_context)

        assert has_changes is True
        assert any("YNAB transactions cache updated" in r for r in reasons)


class TestRetirementUpdateChangeDetector:
    """Tests for retirement update change detection."""

    def test_first_run_triggers_update(self, temp_data_dir, flow_context):
        """Test that first run triggers retirement update."""
        detector = RetirementUpdateChangeDetector(temp_data_dir)

        has_changes, reasons = detector.check_changes(flow_context)

        assert has_changes is True
        assert "No previous retirement update recorded" in reasons[0]

    def test_no_update_within_interval(self, temp_data_dir, flow_context):
        """Test no update needed within 30-day interval."""
        detector = RetirementUpdateChangeDetector(temp_data_dir)

        # Manually set last update to 15 days ago
        recent_time = (datetime.now() - timedelta(days=15)).isoformat()
        detector.save_last_check_state("retirement_update", {"last_update_time": recent_time})

        has_changes, reasons = detector.check_changes(flow_context)

        assert has_changes is False
        assert "Next update in" in reasons[0]

    def test_detects_interval_expiration(self, temp_data_dir, flow_context):
        """Test detection after 30-day interval expires."""
        detector = RetirementUpdateChangeDetector(temp_data_dir)

        # Manually set last update to 31 days ago
        old_time = (datetime.now() - timedelta(days=31)).isoformat()
        detector.save_last_check_state("retirement_update", {"last_update_time": old_time})

        has_changes, reasons = detector.check_changes(flow_context)

        assert has_changes is True
        assert "Monthly retirement update cycle reached" in reasons[0]


class TestChangeDetectorFactories:
    """Tests for change detector factory functions."""

    def test_create_change_detectors(self, temp_data_dir):
        """Test creating all change detectors."""
        detectors = create_change_detectors(temp_data_dir)

        expected_nodes = [
            "ynab_sync",
            "amazon_unzip",
            "amazon_matching",
            "apple_email_fetch",
            "apple_matching",
            "retirement_update",
        ]

        assert set(detectors.keys()) == set(expected_nodes)
        assert all(isinstance(d, ChangeDetector) for d in detectors.values())

    def test_get_change_detector_function(self, temp_data_dir, flow_context):
        """Test creating change detector function from detector instance."""
        detector = YnabSyncChangeDetector(temp_data_dir)

        func = get_change_detector_function(detector)

        # Should be callable and return tuple
        result = func(flow_context)
        assert isinstance(result, tuple)
        assert len(result) == 2
        assert isinstance(result[0], bool)
        assert isinstance(result[1], list)
