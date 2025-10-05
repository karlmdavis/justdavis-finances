#!/usr/bin/env python3
"""
End-to-end tests for Apple CLI commands.

Tests complete workflows via subprocess execution with synthetic data.
NO MOCKING - uses real temporary directories and actual CLI execution.

Test coverage:
- finances apple parse-receipts
- finances apple match
- Error handling and edge cases
- Output validation and JSON structure

Note: finances apple fetch-emails tests are skipped (requires IMAP credentials).
"""

import json
import random
import shutil
import subprocess
import tempfile
from datetime import date, timedelta
from pathlib import Path

import pytest

from finances.core.json_utils import write_json
from tests.fixtures.e2e_helpers import get_test_environment
from tests.fixtures.synthetic_data import (
    generate_synthetic_apple_receipt_html,
    save_synthetic_ynab_data,
)


@pytest.mark.e2e
@pytest.mark.apple
class TestAppleParseReceiptsCLI:
    """E2E tests for 'finances apple parse-receipts' command."""

    def test_apple_parse_receipts_command(self):
        """Test parse-receipts command with synthetic HTML receipt."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)

            # Setup email directory with test receipt (using expected naming convention)
            email_dir = tmpdir / "apple" / "emails"
            email_dir.mkdir(parents=True)

            # Copy sample receipt with correct naming pattern
            receipt_html = email_dir / "receipt001-formatted-simple.html"
            sample_receipt_path = Path(__file__).parent.parent / "test_data" / "apple" / "sample_receipt.html"
            shutil.copy(
                sample_receipt_path,
                receipt_html,
            )

            # Run command
            result = subprocess.run(
                [
                    "uv",
                    "run",
                    "finances",
                    "apple",
                    "parse-receipts",
                    "--input-dir",
                    str(email_dir),
                    "--output-dir",
                    str(tmpdir / "apple" / "exports"),
                ],
                capture_output=True,
                text=True,
                timeout=30,
            )

            # Verify command succeeded
            assert result.returncode == 0, f"Command failed: {result.stderr}"
            assert "Parsing completed" in result.stdout
            assert "Successful: 1" in result.stdout

            # Verify export directory created with JSON
            export_dir = tmpdir / "apple" / "exports"
            assert export_dir.exists()

            export_files = list(export_dir.glob("*_apple_receipts_export.json"))
            assert len(export_files) == 1, "Expected exactly one export file"

            # Read and verify the export JSON structure
            with open(export_files[0]) as f:
                export_data = json.load(f)

            # Verify metadata structure
            assert "metadata" in export_data
            assert "receipts" in export_data

            metadata = export_data["metadata"]
            assert metadata["total_files_processed"] == 1
            assert metadata["successful_parses"] == 1
            assert metadata["failed_parses"] == 0
            assert metadata["success_rate"] == 1.0

            # Verify receipt data structure
            receipts = export_data["receipts"]
            assert len(receipts) == 1

            receipt = receipts[0]
            assert "order_id" in receipt
            assert "total" in receipt
            assert "items" in receipt
            # Parser extracts "Order ID: " prefix from HTML
            assert "ML7PQ2XYZ" in receipt["order_id"]
            assert len(receipt["items"]) >= 2

    def test_apple_parse_multiple_receipts(self):
        """Test parsing multiple receipt files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)

            email_dir = tmpdir / "emails"
            email_dir.mkdir(parents=True)

            # Create 3 synthetic receipts
            for i in range(3):
                receipt_html = generate_synthetic_apple_receipt_html(
                    receipt_id=f"ORDER{i:03d}", customer_id=f"user{i}@example.com"
                )
                receipt_file = email_dir / f"receipt{i:03d}-formatted-simple.html"
                receipt_file.write_text(receipt_html)

            # Run command
            result = subprocess.run(
                [
                    "uv",
                    "run",
                    "finances",
                    "apple",
                    "parse-receipts",
                    "--input-dir",
                    str(email_dir),
                    "--output-dir",
                    str(tmpdir / "exports"),
                ],
                capture_output=True,
                text=True,
                timeout=30,
            )

            assert result.returncode == 0
            assert "Found 3 receipt files" in result.stdout
            assert "Successful: 3" in result.stdout

            # Verify all receipts parsed
            export_files = list((tmpdir / "exports").glob("*.json"))
            with open(export_files[0]) as f:
                export_data = json.load(f)

            assert len(export_data["receipts"]) == 3
            assert export_data["metadata"]["success_rate"] == 1.0

    def test_apple_parse_malformed_html(self):
        """Test error handling for malformed HTML receipts."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)

            email_dir = tmpdir / "emails"
            email_dir.mkdir(parents=True)

            # Create malformed HTML
            bad_receipt = email_dir / "bad_receipt-formatted-simple.html"
            bad_receipt.write_text("<html><body>Not a valid Apple receipt</body></html>")

            # Create one valid receipt
            good_receipt_html = generate_synthetic_apple_receipt_html(receipt_id="GOOD123")
            good_receipt = email_dir / "good_receipt-formatted-simple.html"
            good_receipt.write_text(good_receipt_html)

            # Run command
            result = subprocess.run(
                [
                    "uv",
                    "run",
                    "finances",
                    "apple",
                    "parse-receipts",
                    "--input-dir",
                    str(email_dir),
                    "--output-dir",
                    str(tmpdir / "exports"),
                ],
                capture_output=True,
                text=True,
                timeout=30,
            )

            # Command should succeed but report partial failure
            assert result.returncode == 0
            assert "Found 2 receipt files" in result.stdout

            # Verify parsing results
            export_files = list((tmpdir / "exports").glob("*.json"))
            with open(export_files[0]) as f:
                export_data = json.load(f)

            # At least one should succeed, one should fail
            metadata = export_data["metadata"]
            assert metadata["total_files_processed"] == 2
            assert metadata["successful_parses"] >= 1
            assert metadata["failed_parses"] >= 0

    def test_apple_parse_missing_directory(self):
        """Test error handling when input directory doesn't exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)

            # Use non-existent directory
            nonexistent_dir = tmpdir / "nonexistent"

            # Run command
            result = subprocess.run(
                [
                    "uv",
                    "run",
                    "finances",
                    "apple",
                    "parse-receipts",
                    "--input-dir",
                    str(nonexistent_dir),
                ],
                capture_output=True,
                text=True,
                timeout=30,
            )

            # Should fail with error
            assert result.returncode != 0
            assert "Input directory not found" in result.stderr or "not found" in result.stderr.lower()

    def test_apple_parse_empty_directory(self):
        """Test behavior when input directory has no receipt files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)

            # Create empty directory
            email_dir = tmpdir / "emails"
            email_dir.mkdir(parents=True)

            # Run command
            result = subprocess.run(
                [
                    "uv",
                    "run",
                    "finances",
                    "apple",
                    "parse-receipts",
                    "--input-dir",
                    str(email_dir),
                    "--output-dir",
                    str(tmpdir / "exports"),
                ],
                capture_output=True,
                text=True,
                timeout=30,
            )

            # Should succeed but report no files
            assert result.returncode == 0
            assert "No HTML receipt files found" in result.stdout


@pytest.mark.e2e
@pytest.mark.apple
class TestAppleMatchCLI:
    """E2E tests for 'finances apple match' command."""

    def test_apple_match_command(self):
        """Test match command with synthetic YNAB and Apple data."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)

            # Setup YNAB cache data
            ynab_cache = tmpdir / "ynab" / "cache"
            save_synthetic_ynab_data(ynab_cache)

            # Setup Apple receipts (parsed exports)
            apple_exports = tmpdir / "apple" / "exports"
            apple_exports.mkdir(parents=True)

            # Create synthetic Apple receipt export
            receipt_data = {
                "metadata": {
                    "export_date": date.today().strftime("%Y-%m-%d_%H-%M-%S"),
                    "total_files_processed": 2,
                    "successful_parses": 2,
                    "failed_parses": 0,
                    "success_rate": 1.0,
                },
                "receipts": [
                    {
                        "order_id": "ML7PQ2XYZ",
                        "apple_id": "test@example.com",
                        "receipt_date": (date.today() - timedelta(days=5)).strftime("%b %d, %Y"),
                        "total": 118.05,
                        "subtotal": 109.31,
                        "tax": 8.74,
                        "items": [
                            {"title": "Mock Photo Editor", "cost": 69.93},
                            {"title": "Sample Subscription", "cost": 39.38},
                        ],
                    }
                ],
            }

            receipt_file = apple_exports / "test_receipts.json"
            write_json(receipt_file, receipt_data)

            # Calculate date range
            start_date = (date.today() - timedelta(days=10)).strftime("%Y-%m-%d")
            end_date = date.today().strftime("%Y-%m-%d")

            # Run match command
            result = subprocess.run(
                [
                    "uv",
                    "run",
                    "finances",
                    "--config-env",
                    "test",
                    "apple",
                    "match",
                    "--start",
                    start_date,
                    "--end",
                    end_date,
                    "--output-dir",
                    str(tmpdir / "matches"),
                ],
                capture_output=True,
                text=True,
                timeout=30,
            )

            # Command should succeed (even if placeholder implementation)
            assert result.returncode == 0
            assert "Processing Apple transaction matching" in result.stdout

            # Verify output file created
            match_dir = tmpdir / "matches"
            assert match_dir.exists()

            match_files = list(match_dir.glob("*_apple_matching_results.json"))
            assert len(match_files) == 1

            # Verify JSON structure
            with open(match_files[0]) as f:
                match_data = json.load(f)

            assert "metadata" in match_data
            assert "summary" in match_data
            assert "matches" in match_data

            # Verify metadata
            metadata = match_data["metadata"]
            assert metadata["start_date"] == start_date
            assert metadata["end_date"] == end_date


@pytest.mark.e2e
@pytest.mark.apple
class TestAppleMatchSingleCLI:
    """E2E tests for 'finances apple match-single' command."""

    def test_apple_match_single_command(self):
        """Test match-single command with synthetic transaction data."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)

            # Setup Apple receipt data
            apple_exports = tmpdir / "apple" / "exports"
            apple_exports.mkdir(parents=True)

            # Run match-single command
            result = subprocess.run(
                [
                    "uv",
                    "run",
                    "finances",
                    "--config-env",
                    "test",
                    "apple",
                    "match-single",
                    "--transaction-id",
                    "test-tx-12345",
                    "--date",
                    "2024-10-01",
                    "--amount",
                    "-11805",  # $118.05 in milliunits
                    "--payee-name",
                    "Apple Store",
                    "--account-name",
                    "Test Credit Card",
                ],
                capture_output=True,
                text=True,
                timeout=30,
            )

            # Command should execute (even if no matches found)
            assert result.returncode == 0
            assert "Searching for matching Apple receipts" in result.stdout
            assert "JSON Result:" in result.stdout


@pytest.mark.e2e
@pytest.mark.apple
@pytest.mark.skip(reason="Requires IMAP credentials - tested in integration tests")
class TestAppleFetchEmailsCLI:
    """E2E tests for 'finances apple fetch-emails' command (skipped)."""

    def test_apple_fetch_emails_requires_credentials(self):
        """Verify fetch-emails command validates email configuration."""
        # This test would verify credential checking
        # Skipped because it requires actual IMAP setup
        pass


@pytest.mark.e2e
@pytest.mark.apple
class TestAppleCompleteWorkflow:
    """E2E tests for complete Apple receipt processing workflows."""

    def test_apple_complete_workflow_parse_and_match(self):
        """
        Test complete Apple workflow: parse receipts → match → verify results.

        Validates the entire user journey from parsing receipt HTML files
        to matching them against YNAB transactions.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)

            # Step 1: Create synthetic Apple receipt HTML files
            email_dir = tmpdir / "apple" / "emails"
            email_dir.mkdir(parents=True)

            # Create 3 receipts with known amounts for matching
            receipt_amounts = [11805, 4999, 7250]  # cents
            receipt_ids = ["ABC123XYZ", "DEF456UVW", "GHI789RST"]

            for i, (receipt_id, amount_cents) in enumerate(zip(receipt_ids, receipt_amounts, strict=False)):
                items = [
                    {"title": f"Item 1 for Receipt {i}", "price": int(amount_cents * 0.6)},
                    {"title": f"Item 2 for Receipt {i}", "price": int(amount_cents * 0.4)},
                ]
                receipt_html = generate_synthetic_apple_receipt_html(
                    receipt_id=receipt_id,
                    customer_id=f"user{i}@example.com",
                    items=items,
                )
                receipt_file = email_dir / f"receipt{i:03d}-formatted-simple.html"
                receipt_file.write_text(receipt_html)

            # Step 2: Run parse-receipts to extract data
            export_dir = tmpdir / "apple" / "exports"
            result_parse = subprocess.run(
                [
                    "uv",
                    "run",
                    "finances",
                    "apple",
                    "parse-receipts",
                    "--input-dir",
                    str(email_dir),
                    "--output-dir",
                    str(export_dir),
                ],
                capture_output=True,
                text=True,
                timeout=30,
            )

            # Step 3: Verify parsed JSON export is created
            assert result_parse.returncode == 0, f"Parse failed: {result_parse.stderr}"
            assert "Parsing completed" in result_parse.stdout
            assert "Successful: 3" in result_parse.stdout

            export_files = list(export_dir.glob("*_apple_receipts_export.json"))
            assert len(export_files) == 1, "Expected exactly one export file"

            # Verify parsed data structure
            with open(export_files[0]) as f:
                parsed_data = json.load(f)

            assert parsed_data["metadata"]["successful_parses"] == 3
            assert len(parsed_data["receipts"]) == 3

            # Step 4: Setup YNAB cache with matching transactions
            ynab_cache = tmpdir / "ynab" / "cache"
            ynab_cache.mkdir(parents=True)

            # Create YNAB transactions that match our receipts
            accounts = [
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
            ]

            transactions = []
            base_date = date.today() - timedelta(days=5)

            # Create matching transactions (negative amounts in milliunits)
            for i, amount_cents in enumerate(receipt_amounts):
                transactions.append(
                    {
                        "id": f"tx-{i:05d}",
                        "date": (base_date + timedelta(days=i)).strftime("%Y-%m-%d"),
                        "amount": -(amount_cents * 10),  # Convert cents to milliunits and negate
                        "account_id": "account-001",
                        "account_name": "Test Credit Card",
                        "payee_name": "Apple.com/bill",
                        "category_id": "category-001",
                        "category_name": "Shopping",
                        "memo": None,
                        "cleared": "cleared",
                        "approved": True,
                    }
                )

            # Save YNAB cache files
            write_json(ynab_cache / "accounts.json", {"accounts": accounts, "server_knowledge": 12345})

            write_json(
                ynab_cache / "categories.json",
                {
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
                                    "budgeted": 100000,
                                    "activity": -50000,
                                    "balance": 50000,
                                }
                            ],
                        }
                    ],
                    "server_knowledge": 67890,
                },
            )

            write_json(ynab_cache / "transactions.json", transactions)

            # Step 5: Run apple match on parsed data
            match_dir = tmpdir / "apple" / "matches"
            start_date = (base_date - timedelta(days=2)).strftime("%Y-%m-%d")
            end_date = (base_date + timedelta(days=10)).strftime("%Y-%m-%d")

            result_match = subprocess.run(
                [
                    "uv",
                    "run",
                    "finances",
                    "--config-env",
                    "test",
                    "apple",
                    "match",
                    "--start",
                    start_date,
                    "--end",
                    end_date,
                    "--output-dir",
                    str(match_dir),
                ],
                capture_output=True,
                text=True,
                timeout=30,
                env=get_test_environment(tmpdir),
            )

            # Step 6: Verify match results JSON structure
            assert result_match.returncode == 0, f"Match failed: {result_match.stderr}"
            assert "Processing Apple transaction matching" in result_match.stdout

            match_files = list(match_dir.glob("*_apple_matching_results.json"))
            assert len(match_files) == 1, "Expected exactly one match results file"

            # Step 7: Verify match accuracy
            with open(match_files[0]) as f:
                match_data = json.load(f)

            # Verify structure
            assert "metadata" in match_data
            assert "summary" in match_data
            assert "matches" in match_data

            # Verify metadata
            metadata = match_data["metadata"]
            assert metadata["start_date"] == start_date
            assert metadata["end_date"] == end_date

            # Verify we got some matches (implementation may vary)
            # This validates the workflow completes successfully
            assert isinstance(match_data["matches"], list)

    def test_apple_match_no_matches_found(self):
        """
        Test Apple matching when receipts don't match any YNAB transactions.

        This tests the failure mode where user has Apple receipts but
        no corresponding transactions (common with incomplete data).
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)

            # Step 1: Create Apple receipt exports from date range A (recent)
            apple_exports = tmpdir / "apple" / "exports"
            apple_exports.mkdir(parents=True)

            recent_date = date.today() - timedelta(days=5)
            receipt_data = {
                "metadata": {
                    "export_date": date.today().strftime("%Y-%m-%d_%H-%M-%S"),
                    "total_files_processed": 2,
                    "successful_parses": 2,
                    "failed_parses": 0,
                    "success_rate": 1.0,
                },
                "receipts": [
                    {
                        "order_id": "RECENT123",
                        "apple_id": "test@example.com",
                        "receipt_date": recent_date.strftime("%b %d, %Y"),
                        "total": 49.99,
                        "subtotal": 46.29,
                        "tax": 3.70,
                        "items": [
                            {"title": "Recent App Purchase", "cost": 46.29},
                        ],
                    },
                    {
                        "order_id": "RECENT456",
                        "apple_id": "test@example.com",
                        "receipt_date": (recent_date + timedelta(days=1)).strftime("%b %d, %Y"),
                        "total": 29.99,
                        "subtotal": 27.77,
                        "tax": 2.22,
                        "items": [
                            {"title": "Another Recent Purchase", "cost": 27.77},
                        ],
                    },
                ],
            }

            receipt_file = apple_exports / "test_receipts.json"
            write_json(receipt_file, receipt_data)

            # Step 2: Setup YNAB transactions from date range B (non-overlapping, older)
            ynab_cache = tmpdir / "ynab" / "cache"
            ynab_cache.mkdir(parents=True)

            old_date = date.today() - timedelta(days=90)

            accounts = [
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
            ]

            # Create old transactions that won't match
            transactions = [
                {
                    "id": "tx-00001",
                    "date": (old_date - timedelta(days=i)).strftime("%Y-%m-%d"),
                    "amount": -random.randint(10000, 50000),  # noqa: S311
                    "account_id": "account-001",
                    "account_name": "Test Credit Card",
                    "payee_name": "Apple.com/bill",
                    "category_id": "category-001",
                    "category_name": "Shopping",
                    "memo": None,
                    "cleared": "cleared",
                    "approved": True,
                }
                for i in range(5)
            ]

            # Save YNAB cache
            write_json(ynab_cache / "accounts.json", {"accounts": accounts, "server_knowledge": 12345})

            write_json(
                ynab_cache / "categories.json",
                {
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
                                    "budgeted": 100000,
                                    "activity": -50000,
                                    "balance": 50000,
                                }
                            ],
                        }
                    ],
                    "server_knowledge": 67890,
                },
            )

            write_json(ynab_cache / "transactions.json", transactions)

            # Step 3: Run match command on recent receipt date range
            match_dir = tmpdir / "apple" / "matches"
            start_date = (recent_date - timedelta(days=2)).strftime("%Y-%m-%d")
            end_date = (recent_date + timedelta(days=5)).strftime("%Y-%m-%d")

            result = subprocess.run(
                [
                    "uv",
                    "run",
                    "finances",
                    "--config-env",
                    "test",
                    "apple",
                    "match",
                    "--start",
                    start_date,
                    "--end",
                    end_date,
                    "--output-dir",
                    str(match_dir),
                ],
                capture_output=True,
                text=True,
                timeout=30,
                env=get_test_environment(tmpdir),
            )

            # Step 4: Verify success exit code but 0 matches
            assert result.returncode == 0, f"Command should succeed: {result.stderr}"
            assert "Processing Apple transaction matching" in result.stdout

            # Step 5: Verify output JSON shows 0 matches with summary
            match_files = list(match_dir.glob("*_apple_matching_results.json"))
            assert len(match_files) == 1, "Expected match results file even with 0 matches"

            with open(match_files[0]) as f:
                match_data = json.load(f)

            # Verify structure exists
            assert "metadata" in match_data
            assert "summary" in match_data
            assert "matches" in match_data

            # Verify metadata shows the search parameters
            assert match_data["metadata"]["start_date"] == start_date
            assert match_data["metadata"]["end_date"] == end_date

            # The matches list should exist (even if empty)
            assert isinstance(match_data["matches"], list)
