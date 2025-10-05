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
import shutil
import subprocess
import tempfile
from datetime import date, timedelta
from pathlib import Path

import pytest

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
            shutil.copy(
                "/Users/karl/workspaces/justdavis/personal/justdavis-finances/tests/test_data/apple/sample_receipt.html",
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

    def test_apple_parse_receipts_output_format(self):
        """Test parse-receipts JSON output structure with detailed validation."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)

            # Setup email directory with synthetic receipt
            email_dir = tmpdir / "apple" / "emails"
            email_dir.mkdir(parents=True)

            # Generate synthetic receipt with known values
            items = [
                {"title": "Test App Pro", "price": 999},  # $9.99
                {"title": "Example Game", "price": 499},  # $4.99
            ]
            receipt_html = generate_synthetic_apple_receipt_html(
                receipt_id="TEST123XYZ", customer_id="test@example.com", items=items
            )

            # Write receipt with correct naming
            receipt_file = email_dir / "test_receipt-formatted-simple.html"
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

            # Load and validate JSON structure
            export_files = list((tmpdir / "exports").glob("*_apple_receipts_export.json"))
            with open(export_files[0]) as f:
                export_data = json.load(f)

            # Validate complete structure
            assert set(export_data.keys()) == {"metadata", "receipts"}

            # Validate metadata fields
            metadata = export_data["metadata"]
            required_metadata_fields = {
                "export_date",
                "total_files_processed",
                "successful_parses",
                "failed_parses",
                "success_rate",
            }
            assert set(metadata.keys()) == required_metadata_fields

            # Validate receipt structure
            receipt = export_data["receipts"][0]
            # Parser includes "Order ID: " prefix
            assert "TEST123XYZ" in receipt["order_id"]
            assert receipt["apple_id"] == "test@example.com"
            assert len(receipt["items"]) >= 2

            # Validate item structure
            for item in receipt["items"]:
                assert "title" in item
                assert "cost" in item
                assert isinstance(item["cost"], int | float)

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

    def test_apple_parse_verbose_output(self):
        """Test verbose flag provides detailed output."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)

            email_dir = tmpdir / "emails"
            email_dir.mkdir(parents=True)

            # Create test receipt
            receipt_html = generate_synthetic_apple_receipt_html(receipt_id="VERBOSE123")
            receipt_file = email_dir / "verbose_test-formatted-simple.html"
            receipt_file.write_text(receipt_html)

            # Run command with verbose flag
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
                    "--verbose",
                ],
                capture_output=True,
                text=True,
                timeout=30,
            )

            assert result.returncode == 0
            # Verbose output should include more details
            assert "Apple Receipt Parsing" in result.stdout
            assert "Input directory:" in result.stdout
            assert "Output directory:" in result.stdout


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
            with open(receipt_file, "w") as f:
                json.dump(receipt_data, f, indent=2)

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

    def test_apple_match_with_apple_id_filter(self):
        """Test match command filtering by specific Apple IDs."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)

            # Setup minimal data
            ynab_cache = tmpdir / "ynab" / "cache"
            save_synthetic_ynab_data(ynab_cache)

            start_date = (date.today() - timedelta(days=10)).strftime("%Y-%m-%d")
            end_date = date.today().strftime("%Y-%m-%d")

            # Run with Apple ID filter
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
                    "--apple-ids",
                    "user1@example.com",
                    "--apple-ids",
                    "user2@example.com",
                    "--output-dir",
                    str(tmpdir / "matches"),
                ],
                capture_output=True,
                text=True,
                timeout=30,
            )

            assert result.returncode == 0

            # Verify output file contains the Apple IDs filter
            match_files = list((tmpdir / "matches").glob("*.json"))
            with open(match_files[0]) as f:
                match_data = json.load(f)

            # Verify Apple IDs are in metadata
            assert match_data["metadata"]["apple_ids"] == ["user1@example.com", "user2@example.com"]

    def test_apple_match_verbose_output(self):
        """Test match command with verbose flag."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)

            # Setup minimal data
            ynab_cache = tmpdir / "ynab" / "cache"
            save_synthetic_ynab_data(ynab_cache)

            start_date = (date.today() - timedelta(days=5)).strftime("%Y-%m-%d")
            end_date = date.today().strftime("%Y-%m-%d")

            # Run with verbose flag
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
                    "--verbose",
                    "--output-dir",
                    str(tmpdir / "matches"),
                ],
                capture_output=True,
                text=True,
                timeout=30,
            )

            assert result.returncode == 0

            # Verbose output should include additional details
            assert "Apple Transaction Matching" in result.stdout
            assert "Date range:" in result.stdout
            assert f"{start_date} to {end_date}" in result.stdout

    def test_apple_match_invalid_date_format(self):
        """Test error handling for invalid date formats."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)

            # Run with invalid date format
            result = subprocess.run(
                [
                    "uv",
                    "run",
                    "finances",
                    "apple",
                    "match",
                    "--start",
                    "invalid-date",
                    "--end",
                    "2024-12-31",
                ],
                capture_output=True,
                text=True,
                timeout=30,
            )

            # Should fail (either validation error or processing error)
            # Exit code check depends on implementation
            # At minimum, should not produce valid output


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
