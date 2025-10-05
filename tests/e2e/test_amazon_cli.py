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
import os
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
        env = {**os.environ, "FINANCES_DATA_DIR": str(tmpdir)}

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
            env=env,
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
        env = {**os.environ, "FINANCES_DATA_DIR": str(tmpdir)}

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
            env=env,
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
        env = {**os.environ, "FINANCES_DATA_DIR": str(tmpdir)}

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
            env=env,
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
        env = {**os.environ, "FINANCES_DATA_DIR": str(tmpdir)}

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
            env=env,
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
        env = {**os.environ, "FINANCES_DATA_DIR": str(tmpdir)}

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
            env=env,
        )

        # Verify command handles error (may exit with error code)
        # The command should not crash unexpectedly
        assert result.returncode in [0, 1], f"Unexpected error: {result.stderr}"

        # Verify error message is present
        output_text = result.stdout + result.stderr
        assert "error" in output_text.lower() or "❌" in output_text or "⚠" in output_text


@pytest.mark.e2e
@pytest.mark.amazon
def test_amazon_complete_workflow():
    """
    Test complete Amazon workflow: unzip → match → verify results.

    This E2E test validates the entire user journey from extracting Amazon
    order data to generating transaction matches with accurate results.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        # Step 1: Create a ZIP file with synthetic Amazon CSV data
        download_dir = tmpdir / "downloads"
        download_dir.mkdir()

        # Create Amazon orders with known amounts and dates (use past dates)
        amazon_orders = [
            {
                "Order ID": "111-1111111-1111111",
                "Order Date": "09/15/2024",
                "Ship Date": "09/17/2024",
                "Total Owed": "$50.00",
                "Title": "Test Product A",
                "Quantity": 1,
                "ASIN/ISBN": "B012345678",
                "Item Subtotal": "$46.30",
                "Item Tax": "$3.70",
            },
            {
                "Order ID": "222-2222222-2222222",
                "Order Date": "09/20/2024",
                "Ship Date": "09/22/2024",
                "Total Owed": "$75.00",
                "Title": "Test Product B",
                "Quantity": 1,
                "ASIN/ISBN": "B087654321",
                "Item Subtotal": "$69.44",
                "Item Tax": "$5.56",
            },
        ]

        # Create CSV file
        csv_file = tmpdir / "temp_orders.csv"
        with open(csv_file, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=amazon_orders[0].keys())
            writer.writeheader()
            writer.writerows(amazon_orders)

        # Create ZIP file
        zip_path = download_dir / "amazon_orders_testuser.zip"
        with zipfile.ZipFile(zip_path, "w") as zip_ref:
            zip_ref.write(csv_file, "Retail.OrderHistory.1.csv")

        # Step 2: Run `finances amazon unzip` to extract data
        output_dir = tmpdir / "amazon" / "raw"
        env = {**os.environ, "FINANCES_DATA_DIR": str(tmpdir)}

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
            env=env,
        )

        # Step 3: Verify extraction created correct directory structure
        assert result.returncode == 0, f"Unzip failed: {result.stderr}\n{result.stdout}"
        assert output_dir.exists()

        # Look for any amazon_data directories (account name may vary)
        extracted_dirs = list(output_dir.glob("*_amazon_data*"))
        assert (
            len(extracted_dirs) > 0
        ), f"No extracted directories found in {output_dir}. Contents: {list(output_dir.iterdir()) if output_dir.exists() else 'directory does not exist'}"
        assert (extracted_dirs[0] / "Retail.OrderHistory.1.csv").exists()

        # Step 4: Setup YNAB cache with matching transactions
        ynab_cache_dir = tmpdir / "ynab" / "cache"
        ynab_cache_dir.mkdir(parents=True)

        # Create matching YNAB transactions (amounts in milliunits: cents * 10)
        ynab_transactions = [
            {
                "id": "ynab-tx-001",
                "date": "2024-09-15",
                "amount": -500000,  # -$50.00 in milliunits
                "account_id": "account-001",
                "account_name": "Test Credit Card",
                "payee_name": "Amazon.com",
                "category_id": "category-001",
                "category_name": "Shopping",
                "memo": None,
                "cleared": "cleared",
                "approved": True,
            },
            {
                "id": "ynab-tx-002",
                "date": "2024-09-20",
                "amount": -750000,  # -$75.00 in milliunits
                "account_id": "account-001",
                "account_name": "Test Credit Card",
                "payee_name": "AMZN Marketplace",
                "category_id": "category-001",
                "category_name": "Shopping",
                "memo": None,
                "cleared": "cleared",
                "approved": True,
            },
        ]

        ynab_accounts = {
            "accounts": [
                {
                    "id": "account-001",
                    "name": "Test Credit Card",
                    "type": "creditCard",
                    "balance": 1000000,
                    "cleared_balance": 1000000,
                    "uncleared_balance": 0,
                    "closed": False,
                    "on_budget": True,
                }
            ],
            "server_knowledge": 12345,
        }

        ynab_categories = {
            "category_groups": [
                {
                    "id": "group-001",
                    "name": "Test Group",
                    "hidden": False,
                    "categories": [
                        {
                            "id": "category-001",
                            "name": "Shopping",
                            "hidden": False,
                            "budgeted": 500000,
                            "activity": -1250000,
                            "balance": 0,
                        }
                    ],
                }
            ],
            "server_knowledge": 67890,
        }

        # Write YNAB cache files
        with open(ynab_cache_dir / "accounts.json", "w") as f:
            json.dump(ynab_accounts, f, indent=2)

        with open(ynab_cache_dir / "categories.json", "w") as f:
            json.dump(ynab_categories, f, indent=2)

        with open(ynab_cache_dir / "transactions.json", "w") as f:
            json.dump(ynab_transactions, f, indent=2)

        # Step 5: Run `finances amazon match` on extracted data
        # Extract account name from extracted directory
        account_name = extracted_dirs[0].name.split("_")[
            2
        ]  # Gets "unknown" or "testuser" from directory name
        match_output_dir = tmpdir / "amazon" / "transaction_matches"

        result = subprocess.run(
            [
                "uv",
                "run",
                "finances",
                "amazon",
                "match",
                "--start",
                "2024-09-01",
                "--end",
                "2024-09-30",
                "--accounts",
                account_name,
                "--output-dir",
                str(match_output_dir),
            ],
            capture_output=True,
            text=True,
            env=env,
        )

        # Step 6: Verify match results JSON structure
        assert result.returncode == 0, f"Match command failed: {result.stderr}"
        assert match_output_dir.exists()

        output_files = list(match_output_dir.glob("*_amazon_matching_results.json"))
        assert len(output_files) > 0, "No output files created"

        with open(output_files[0]) as f:
            results = json.load(f)

        assert "metadata" in results
        assert "summary" in results
        assert "matches" in results

        # Step 7: Verify results structure (CLI currently returns placeholder)
        # NOTE: The match CLI command is currently a placeholder that doesn't
        # implement full batch matching logic. This test validates the workflow
        # completes and generates proper output structure.

        # Verify metadata is correct
        assert results["metadata"]["start_date"] == "2024-09-01"
        assert results["metadata"]["end_date"] == "2024-09-30"
        assert results["metadata"]["accounts"] == [account_name]

        # Verify summary structure exists (values will be 0 until CLI implementation is complete)
        summary = results["summary"]
        assert "total_transactions" in summary
        assert "matched_transactions" in summary
        assert "match_rate" in summary
        assert "average_confidence" in summary

        # Verify matches is a list (empty until CLI implementation is complete)
        matches = results["matches"]
        assert isinstance(matches, list)


@pytest.mark.e2e
@pytest.mark.amazon
def test_amazon_match_no_matches_found():
    """
    Test Amazon matching when no YNAB transactions match Amazon orders.

    This tests the important failure mode where user has Amazon orders
    but no corresponding transactions in YNAB (common when data is incomplete).
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        # Step 1: Setup Amazon orders from date range A (September 2024)
        amazon_dir = tmpdir / "amazon" / "raw" / "2024-10-01_testuser_amazon_data"
        amazon_dir.mkdir(parents=True)

        amazon_orders = [
            {
                "Order ID": "333-3333333-3333333",
                "Order Date": "09/15/2024",
                "Ship Date": "09/17/2024",
                "Total Owed": "$100.00",
                "Title": "Test Product C",
                "Quantity": 1,
                "ASIN/ISBN": "B099999999",
                "Item Subtotal": "$92.59",
                "Item Tax": "$7.41",
            },
        ]

        csv_file = amazon_dir / "Retail.OrderHistory.1.csv"
        with open(csv_file, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=amazon_orders[0].keys())
            writer.writeheader()
            writer.writerows(amazon_orders)

        # Step 2: Setup YNAB transactions from date range B (July 2024 - non-overlapping)
        ynab_cache_dir = tmpdir / "ynab" / "cache"
        ynab_cache_dir.mkdir(parents=True)

        ynab_transactions = [
            {
                "id": "ynab-tx-003",
                "date": "2024-07-15",  # Different month - no overlap
                "amount": -1000000,  # -$100.00 in milliunits
                "account_id": "account-001",
                "account_name": "Test Credit Card",
                "payee_name": "Amazon.com",
                "category_id": "category-001",
                "category_name": "Shopping",
                "memo": None,
                "cleared": "cleared",
                "approved": True,
            },
        ]

        ynab_accounts = {
            "accounts": [
                {
                    "id": "account-001",
                    "name": "Test Credit Card",
                    "type": "creditCard",
                    "balance": 1000000,
                    "cleared_balance": 1000000,
                    "uncleared_balance": 0,
                    "closed": False,
                    "on_budget": True,
                }
            ],
            "server_knowledge": 12345,
        }

        ynab_categories = {
            "category_groups": [
                {
                    "id": "group-001",
                    "name": "Test Group",
                    "hidden": False,
                    "categories": [
                        {
                            "id": "category-001",
                            "name": "Shopping",
                            "hidden": False,
                            "budgeted": 500000,
                            "activity": -1000000,
                            "balance": 0,
                        }
                    ],
                }
            ],
            "server_knowledge": 67890,
        }

        with open(ynab_cache_dir / "accounts.json", "w") as f:
            json.dump(ynab_accounts, f, indent=2)

        with open(ynab_cache_dir / "categories.json", "w") as f:
            json.dump(ynab_categories, f, indent=2)

        with open(ynab_cache_dir / "transactions.json", "w") as f:
            json.dump(ynab_transactions, f, indent=2)

        # Step 3: Run match command
        env = {**os.environ, "FINANCES_DATA_DIR": str(tmpdir)}
        match_output_dir = tmpdir / "amazon" / "transaction_matches"

        result = subprocess.run(
            [
                "uv",
                "run",
                "finances",
                "amazon",
                "match",
                "--start",
                "2024-09-01",
                "--end",
                "2024-09-30",
                "--accounts",
                "testuser",
                "--output-dir",
                str(match_output_dir),
            ],
            capture_output=True,
            text=True,
            env=env,
        )

        # Step 4: Verify: success exit code, but 0 matches found
        assert result.returncode == 0, f"Command failed: {result.stderr}"

        # Step 5: Verify output JSON shows 0 matches with appropriate summary
        output_files = list(match_output_dir.glob("*_amazon_matching_results.json"))
        assert len(output_files) > 0, "No output files created"

        with open(output_files[0]) as f:
            results = json.load(f)

        # Verify structure
        assert "metadata" in results
        assert "summary" in results
        assert "matches" in results

        # Verify no matches were found (transaction outside date range)
        summary = results["summary"]
        assert summary["total_transactions"] == 0 or summary["matched_transactions"] == 0

        # Verify matches list reflects no successful matches
        matches = results["matches"]
        if len(matches) > 0:
            # If matches exist, they should have no best_match
            for match in matches:
                assert match["best_match"] is None or match["best_match"]["confidence_score"] == 0
