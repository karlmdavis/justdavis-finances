#!/usr/bin/env python3
"""
Integration tests for Apple data loaders.

Tests Apple receipt loading with real file operations, error handling,
and edge cases like malformed JSON and missing files.
"""

import tempfile
from pathlib import Path

import pytest

from finances.apple.loader import load_apple_receipts, filter_receipts_by_date_range, receipts_to_dataframe
from finances.core import FinancialDate, Money
from finances.core.json_utils import write_json


@pytest.fixture
def temp_dir():
    """Create temporary directory for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def sample_exports_dir(temp_dir):
    """Create sample exports directory with test receipts."""
    exports_dir = temp_dir / "apple" / "exports"
    exports_dir.mkdir(parents=True)
    return exports_dir


@pytest.mark.integration
@pytest.mark.apple
class TestAppleReceiptLoader:
    """Test Apple receipt loading with real file operations."""

    def test_load_receipts_from_valid_directory(self, sample_exports_dir):
        """Test loading receipts from directory with valid JSON."""
        # Create valid receipt
        write_json(sample_exports_dir / "receipt1.json", {
            "order_id": "ML123ABC",
            "receipt_date": "2024-10-15",
            "apple_id": "test@example.com",
            "total": 999,
            "subtotal": 899,
            "tax": 100,
            "items": [],
            "format_detected": "modern_custom"
        })

        receipts = load_apple_receipts(str(sample_exports_dir))

        assert len(receipts) == 1
        assert receipts[0].order_id == "ML123ABC"

    def test_load_receipts_from_nonexistent_directory(self, temp_dir):
        """Test loading receipts when exports directory doesn't exist raises error."""
        nonexistent_path = temp_dir / "nonexistent"

        with pytest.raises(FileNotFoundError, match="No Apple receipt JSON files found"):
            load_apple_receipts(str(nonexistent_path))

    def test_load_receipts_with_multiple_files(self, sample_exports_dir):
        """Test loading multiple receipts from directory."""
        # Create multiple receipts
        write_json(sample_exports_dir / "receipt1.json", {
            "order_id": "ML111AAA",
            "receipt_date": "2024-10-10",
            "apple_id": "test@example.com",
            "total": 1999,
            "subtotal": 1799,
            "tax": 200,
            "items": [],
            "format_detected": "modern_custom"
        })

        write_json(sample_exports_dir / "receipt2.json", {
            "order_id": "ML222BBB",
            "receipt_date": "2024-10-11",
            "apple_id": "test@example.com",
            "total": 999,
            "subtotal": 899,
            "tax": 100,
            "items": [],
            "format_detected": "modern_custom"
        })

        receipts = load_apple_receipts(str(sample_exports_dir))

        assert len(receipts) == 2
        order_ids = {r.order_id for r in receipts}
        assert order_ids == {"ML111AAA", "ML222BBB"}

    def test_receipts_to_dataframe_conversion(self, sample_exports_dir):
        """Test converting receipts to DataFrame."""
        write_json(sample_exports_dir / "receipt.json", {
            "order_id": "ML999ZZZ",
            "receipt_date": "2024-10-18",
            "apple_id": "test@example.com",
            "total": 3299,
            "subtotal": 2999,
            "tax": 300,
            "items": [],
            "format_detected": "modern_custom"
        })

        receipts = load_apple_receipts(str(sample_exports_dir))
        df = receipts_to_dataframe(receipts)

        assert len(df) == 1
        assert df.iloc[0]["order_id"] == "ML999ZZZ"
        assert "receipt_date" in df.columns
        assert "total" in df.columns

    def test_filter_receipts_by_date_range(self, sample_exports_dir):
        """Test filtering receipts by date range using DataFrame."""
        # Create receipts with different dates
        write_json(sample_exports_dir / "receipt_jan.json", {
            "order_id": "R_JAN",
            "receipt_date": "2024-01-15",
            "apple_id": "test@example.com",
            "total": 999,
            "subtotal": 899,
            "tax": 100,
            "items": [],
            "format_detected": "modern_custom"
        })

        write_json(sample_exports_dir / "receipt_mar.json", {
            "order_id": "R_MAR",
            "receipt_date": "2024-03-10",
            "apple_id": "test@example.com",
            "total": 2999,
            "subtotal": 2699,
            "tax": 300,
            "items": [],
            "format_detected": "modern_custom"
        })

        receipts = load_apple_receipts(str(sample_exports_dir))
        df = receipts_to_dataframe(receipts)

        # Filter to only January
        filtered_df = filter_receipts_by_date_range(df, "2024-01-01", "2024-01-31")

        assert len(filtered_df) == 1
        assert filtered_df.iloc[0]["order_id"] == "R_JAN"
