"""Tests for Amazon flow node OutputInfo implementations."""

import json
import tempfile
from pathlib import Path

from finances.amazon.flow import AmazonMatchingFlowNode, AmazonUnzipFlowNode


def test_amazon_unzip_output_info_is_data_ready_returns_true_with_csv_files():
    """Verify is_data_ready returns True when CSV files exist."""
    with tempfile.TemporaryDirectory() as tmpdir:
        data_dir = Path(tmpdir)
        # Create proper Amazon account directory structure
        account_dir = data_dir / "amazon" / "raw" / "2024-01-01_test_amazon_data"
        csv_dir = account_dir / "Retail.OrderHistory.1"
        csv_dir.mkdir(parents=True)

        # Create CSV file in nested structure
        (csv_dir / "Retail.OrderHistory.1.csv").write_text(
            '"Order ID","Order Date"\n"123","2024-01-01T12:00:00Z"'
        )

        node = AmazonUnzipFlowNode(data_dir)
        info = node.get_output_info()

        assert info.is_data_ready() is True


def test_amazon_unzip_output_info_get_output_files_counts_csv_rows():
    """Verify get_output_files returns CSV files with row counts."""
    with tempfile.TemporaryDirectory() as tmpdir:
        data_dir = Path(tmpdir)
        # Create proper Amazon account directory structure
        account_dir = data_dir / "amazon" / "raw" / "2024-01-01_test_amazon_data"
        csv_dir = account_dir / "Retail.OrderHistory.1"
        csv_dir.mkdir(parents=True)

        # Create CSV with 3 data rows in nested structure
        csv_content = (
            '"Order ID","Order Date"\n'
            '"123","2024-01-01T12:00:00Z"\n'
            '"456","2024-01-02T12:00:00Z"\n'
            '"789","2024-01-03T12:00:00Z"'
        )
        (csv_dir / "Retail.OrderHistory.1.csv").write_text(csv_content)

        node = AmazonUnzipFlowNode(data_dir)
        info = node.get_output_info()
        files = info.get_output_files()

        assert len(files) == 1
        assert files[0].path.suffix == ".csv"
        assert files[0].record_count == 3  # Data rows (excludes header)


def test_amazon_matching_output_info_is_data_ready_returns_true_with_json_files():
    """Verify is_data_ready returns True when JSON match files exist."""
    with tempfile.TemporaryDirectory() as tmpdir:
        data_dir = Path(tmpdir)
        matches_dir = data_dir / "amazon" / "transaction_matches"
        matches_dir.mkdir(parents=True)

        # Create match result JSON
        (matches_dir / "2024-10-19_results.json").write_text('{"matches": []}')

        node = AmazonMatchingFlowNode(data_dir)
        info = node.get_output_info()

        assert info.is_data_ready() is True


def test_amazon_matching_output_info_get_output_files_returns_json_with_match_counts():
    """Verify get_output_files returns .json files with match counts."""
    with tempfile.TemporaryDirectory() as tmpdir:
        data_dir = Path(tmpdir)
        matches_dir = data_dir / "amazon" / "transaction_matches"
        matches_dir.mkdir(parents=True)

        # Create match result JSON
        match_data = {"matches": [{"id": "1"}, {"id": "2"}]}
        (matches_dir / "2024-10-19_results.json").write_text(json.dumps(match_data))

        node = AmazonMatchingFlowNode(data_dir)
        info = node.get_output_info()
        files = info.get_output_files()

        assert len(files) == 1
        assert files[0].record_count == 2
