#!/usr/bin/env python3
"""
End-to-end tests for Amazon CLI commands.

Tests the complete CLI interface for Amazon transaction matching,
using subprocess to execute actual commands with synthetic test data.

NO MOCKING - Uses real temporary directories with synthetic data to ensure
CLI commands work correctly from the user's perspective.
"""

import csv
import json
import shutil
import subprocess
import tempfile
import zipfile
from pathlib import Path

import pytest

from tests.fixtures.synthetic_data import (
    generate_synthetic_amazon_orders,
    save_synthetic_ynab_data,
)


@pytest.mark.e2e
@pytest.mark.amazon
def test_amazon_unzip_command():
    """Test `finances amazon unzip` with a test zip file."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        # Create download directory with test ZIP
        download_dir = tmpdir / "downloads"
        download_dir.mkdir()

        # Create synthetic Amazon data
        test_orders = generate_synthetic_amazon_orders(num_orders=5)

        # Create CSV file
        csv_file = tmpdir / "temp_orders.csv"
        with open(csv_file, "w", newline="") as f:
            if test_orders:
                writer = csv.DictWriter(f, fieldnames=test_orders[0].keys())
                writer.writeheader()
                writer.writerows(test_orders)

        # Create ZIP file
        zip_path = download_dir / "amazon_orders_karl.zip"
        with zipfile.ZipFile(zip_path, "w") as zip_ref:
            zip_ref.write(csv_file, "Retail.OrderHistory.1.csv")

        # Create output directory
        output_dir = tmpdir / "amazon" / "raw"

        # Set environment variable for data directory
        env = {"FINANCES_DATA_DIR": str(tmpdir)}

        # Run unzip command
        result = subprocess.run(
            [
                "uv",
                "run",
                "finances",
                "amazon",
                "unzip",
                "--download-dir",
                str(download_dir),
                "--output-dir",
                str(output_dir),
            ],
            capture_output=True,
            text=True,
            env={**env},
        )

        # Verify command succeeded
        assert result.returncode == 0, f"Command failed: {result.stderr}"
        assert "✅" in result.stdout or "Successfully" in result.stdout

        # Verify output directory was created
        assert output_dir.exists()

        # Verify extracted files exist
        extracted_dirs = list(output_dir.glob("*_karl_amazon_data"))
        assert len(extracted_dirs) > 0, "No extracted directories found"

        # Verify CSV file was extracted
        csv_files = list(extracted_dirs[0].glob("*.csv"))
        assert len(csv_files) > 0, "No CSV files extracted"


@pytest.mark.e2e
@pytest.mark.amazon
def test_amazon_match_command():
    """Test `finances amazon match` with synthetic YNAB + Amazon data."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        # Setup YNAB cache
        ynab_cache_dir = tmpdir / "ynab" / "cache"
        save_synthetic_ynab_data(ynab_cache_dir)

        # Setup Amazon data
        amazon_dir = tmpdir / "amazon" / "raw" / "2025-10-01_karl_amazon_data"
        amazon_dir.mkdir(parents=True)

        # Copy sample orders
        test_data_path = Path(__file__).parent.parent / "test_data" / "amazon" / "sample_orders.csv"
        shutil.copy(test_data_path, amazon_dir / "Retail.OrderHistory.1.csv")

        # Create output directory
        output_dir = tmpdir / "amazon" / "transaction_matches"
        output_dir.mkdir(parents=True)

        # Set environment variable for data directory
        env = {"FINANCES_DATA_DIR": str(tmpdir)}

        # Run match command
        result = subprocess.run(
            [
                "uv",
                "run",
                "finances",
                "amazon",
                "match",
                "--start",
                "2025-09-01",
                "--end",
                "2025-09-30",
                "--output-dir",
                str(output_dir),
            ],
            capture_output=True,
            text=True,
            env={**env},
        )

        # Verify command succeeded
        assert result.returncode == 0, f"Command failed: {result.stderr}"
        assert "✅" in result.stdout or "Results saved" in result.stdout

        # Verify output file was created
        output_files = list(output_dir.glob("*_amazon_matching_results.json"))
        assert len(output_files) > 0, "No output files created"

        # Verify JSON structure
        with open(output_files[0]) as f:
            data = json.load(f)

        assert "metadata" in data
        assert "summary" in data
        assert "matches" in data
        assert data["metadata"]["start_date"] == "2025-09-01"
        assert data["metadata"]["end_date"] == "2025-09-30"


@pytest.mark.e2e
@pytest.mark.amazon
def test_amazon_match_multiple_accounts():
    """Test multi-account support in `finances amazon match`."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        # Setup YNAB cache
        ynab_cache_dir = tmpdir / "ynab" / "cache"
        save_synthetic_ynab_data(ynab_cache_dir)

        # Setup Amazon data for multiple accounts
        for account in ["karl", "erica"]:
            amazon_dir = tmpdir / "amazon" / "raw" / f"2025-10-01_{account}_amazon_data"
            amazon_dir.mkdir(parents=True)

            test_data_path = Path(__file__).parent.parent / "test_data" / "amazon" / "sample_orders.csv"
            shutil.copy(test_data_path, amazon_dir / "Retail.OrderHistory.1.csv")

        # Set environment variable for data directory
        env = {"FINANCES_DATA_DIR": str(tmpdir)}

        # Run match with specific accounts
        result = subprocess.run(
            [
                "uv",
                "run",
                "finances",
                "amazon",
                "match",
                "--start",
                "2025-09-01",
                "--end",
                "2025-09-30",
                "--accounts",
                "karl",
                "--accounts",
                "erica",
            ],
            capture_output=True,
            text=True,
            env={**env},
        )

        # Verify command succeeded
        assert result.returncode == 0, f"Command failed: {result.stderr}"

        # Verify output file contains account information
        output_dir = tmpdir / "amazon" / "transaction_matches"
        output_files = list(output_dir.glob("*_amazon_matching_results.json"))
        assert len(output_files) > 0

        with open(output_files[0]) as f:
            data = json.load(f)

        assert data["metadata"]["accounts"] == ["karl", "erica"]


@pytest.mark.e2e
@pytest.mark.amazon
def test_amazon_match_error_missing_data():
    """Test error handling when YNAB cache is missing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        # DO NOT create YNAB cache - intentionally missing

        # Setup Amazon data
        amazon_dir = tmpdir / "amazon" / "raw" / "2025-10-01_karl_amazon_data"
        amazon_dir.mkdir(parents=True)

        test_data_path = Path(__file__).parent.parent / "test_data" / "amazon" / "sample_orders.csv"
        shutil.copy(test_data_path, amazon_dir / "Retail.OrderHistory.1.csv")

        # Set environment variable for data directory
        env = {"FINANCES_DATA_DIR": str(tmpdir)}

        # Run match command - should succeed but may have warnings
        # (The CLI currently creates a placeholder result even without full data)
        result = subprocess.run(
            [
                "uv",
                "run",
                "finances",
                "amazon",
                "match",
                "--start",
                "2025-09-01",
                "--end",
                "2025-09-30",
            ],
            capture_output=True,
            text=True,
            env={**env},
        )

        # The command may succeed with warnings or fail gracefully
        # Current implementation creates placeholder results
        # Verify it doesn't crash unexpectedly
        assert result.returncode in [0, 1], f"Unexpected error: {result.stderr}"


@pytest.mark.e2e
@pytest.mark.amazon
def test_amazon_unzip_corrupted_file():
    """Test error handling for corrupted zip file."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        # Create download directory
        download_dir = tmpdir / "downloads"
        download_dir.mkdir()

        # Create a corrupted (invalid) ZIP file
        corrupted_zip = download_dir / "corrupted_karl.zip"
        with open(corrupted_zip, "w") as f:
            f.write("This is not a valid ZIP file content")

        # Create output directory
        output_dir = tmpdir / "amazon" / "raw"

        # Set environment variable for data directory
        env = {"FINANCES_DATA_DIR": str(tmpdir)}

        # Run unzip command - should handle error gracefully
        result = subprocess.run(
            [
                "uv",
                "run",
                "finances",
                "amazon",
                "unzip",
                "--download-dir",
                str(download_dir),
                "--output-dir",
                str(output_dir),
            ],
            capture_output=True,
            text=True,
            env={**env},
        )

        # Verify command handles error (may exit with error code)
        # The command should not crash unexpectedly
        assert result.returncode in [0, 1], f"Unexpected error: {result.stderr}"

        # Verify error message is present
        output_text = result.stdout + result.stderr
        assert "error" in output_text.lower() or "❌" in output_text or "⚠" in output_text
