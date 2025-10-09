#!/usr/bin/env python3
"""
E2E Tests for YNAB CLI Commands

Comprehensive end-to-end tests for the YNAB CLI interface.
Tests actual CLI invocations using subprocess with synthetic test data.

SAFETY: All tests use --dry-run, mocked APIs, or synthetic data.
NEVER touches real YNAB account.
"""

import json
import subprocess
import tempfile
from pathlib import Path

import pytest

from finances.core.currency import milliunits_to_cents
from finances.core.json_utils import write_json
from tests.fixtures.synthetic_data import generate_synthetic_ynab_cache


@pytest.mark.e2e
@pytest.mark.ynab
def test_ynab_generate_splits_from_amazon():
    """
    Test generating transaction splits from Amazon match results.

    Verifies:
    - Command processes Amazon match results correctly
    - Edit file is created with proper structure
    - Splits are calculated with correct amounts
    - Confidence threshold filtering works
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)

        # Setup YNAB cache
        ynab_cache_dir = tmpdir_path / "ynab" / "cache"
        ynab_cache_dir.mkdir(parents=True, exist_ok=True)

        cache_data = generate_synthetic_ynab_cache(num_transactions=10)

        write_json(ynab_cache_dir / "accounts.json", cache_data["accounts"])
        write_json(ynab_cache_dir / "categories.json", cache_data["categories"])
        write_json(ynab_cache_dir / "transactions.json", cache_data["transactions"])

        # Create synthetic Amazon match result
        # Use a fixed transaction amount that's evenly divisible (whole cents)
        # to avoid rounding issues when splitting
        transaction = cache_data["transactions"][0].copy()
        transaction["amount"] = -45990  # -$45.99 in milliunits (evenly divisible by 10)

        transaction_amount_cents = milliunits_to_cents(transaction["amount"])  # 4599 cents

        # Create Amazon items that sum to transaction amount (in cents)
        item1_amount = 2500  # $25.00 in cents
        item2_amount = 2099  # $20.99 in cents
        # Total: $45.99

        amazon_match_result = {
            "matches": [
                {
                    "transaction_id": transaction["id"],
                    "confidence": 0.95,
                    "ynab_transaction": {
                        "id": transaction["id"],
                        "date": transaction["date"],
                        "amount": transaction["amount"],  # Already in milliunits (negative for expense)
                        "payee_name": transaction["payee_name"],
                    },
                    "amazon_orders": [
                        {
                            "order_id": "123-4567890-1234567",
                            "order_date": transaction["date"],
                            "total_owed": transaction_amount_cents,
                            "items": [
                                {
                                    "name": "Wireless Mouse",
                                    "amount": item1_amount,
                                    "quantity": 1,
                                    "unit_price": item1_amount,
                                },
                                {
                                    "name": "USB Cable",
                                    "amount": item2_amount,
                                    "quantity": 1,
                                    "unit_price": item2_amount,
                                },
                            ],
                        }
                    ],
                    "strategy": "exact_match",
                }
            ]
        }

        # Write match results to temp file
        match_file = tmpdir_path / "amazon_matches.json"
        write_json(match_file, amazon_match_result)

        # Run generate-splits command
        output_dir = tmpdir_path / "ynab" / "edits"
        result = subprocess.run(
            [
                "uv",
                "run",
                "finances",
                "ynab",
                "generate-splits",
                "--input-file",
                str(match_file),
                "--confidence-threshold",
                "0.8",
                "--output-dir",
                str(output_dir),
                "-v",
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )

        # Verify command succeeded
        assert result.returncode == 0
        assert "Generated 1 edits" in result.stdout
        assert "Auto-approved: 1" in result.stdout
        assert "Requires review: 0" in result.stdout

        # Verify edit file was created
        edit_files = list(output_dir.glob("*amazon*.json"))
        assert len(edit_files) == 1

        # Verify edit file structure
        with open(edit_files[0]) as f:
            edit_data = json.load(f)

        assert "metadata" in edit_data
        assert "summary" in edit_data
        assert "edits" in edit_data

        # Verify metadata
        assert edit_data["metadata"]["match_type"] == "amazon"
        assert edit_data["metadata"]["confidence_threshold"] == 0.8

        # Verify summary
        assert edit_data["summary"]["total_edits"] == 1
        assert edit_data["summary"]["auto_approved"] == 1
        assert edit_data["summary"]["requires_review"] == 0

        # Verify edits
        assert len(edit_data["edits"]) == 1
        edit = edit_data["edits"][0]
        assert edit["transaction_id"] == transaction["id"]
        assert edit["confidence"] == 0.95
        assert edit["auto_approved"] is True
        assert "splits" in edit
        assert len(edit["splits"]) == 2

        # Verify splits sum to transaction amount (in milliunits)
        splits_total = sum(split["amount"] for split in edit["splits"])
        expected_total = transaction["amount"]  # Already in milliunits (negative for expense)
        assert splits_total == expected_total


@pytest.mark.e2e
@pytest.mark.ynab
def test_ynab_generate_splits_from_apple():
    """
    Test generating transaction splits from Apple match results.

    Verifies:
    - Command processes Apple match results correctly
    - Apple-specific split calculation (proportional tax)
    - Edit file structure for Apple matches
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)

        # Setup YNAB cache
        ynab_cache_dir = tmpdir_path / "ynab" / "cache"
        ynab_cache_dir.mkdir(parents=True, exist_ok=True)

        cache_data = generate_synthetic_ynab_cache(num_transactions=10)

        write_json(ynab_cache_dir / "accounts.json", cache_data["accounts"])
        write_json(ynab_cache_dir / "categories.json", cache_data["categories"])
        write_json(ynab_cache_dir / "transactions.json", cache_data["transactions"])

        # Create synthetic Apple match result
        # Use a fixed transaction amount that's evenly divisible (whole cents)
        transaction = cache_data["transactions"][1].copy()
        transaction["amount"] = -11990  # -$11.99 in milliunits (evenly divisible by 10)

        # For Apple, items represent the price (in cents) before tax
        # The split calculator will convert these to milliunits
        item1_price = 600  # $6.00 in cents
        item2_price = 599  # $5.99 in cents
        # Total: $11.99

        apple_match_result = {
            "matches": [
                {
                    "transaction_id": transaction["id"],
                    "confidence": 0.88,
                    "ynab_transaction": {
                        "id": transaction["id"],
                        "date": transaction["date"],
                        "amount": transaction["amount"],  # Already in milliunits (negative for expense)
                        "payee_name": transaction["payee_name"],
                    },
                    "items": [
                        {"name": "Test App Pro", "price": item1_price},
                        {"name": "Example Game", "price": item2_price},
                    ],
                    "strategy": "exact_match",
                }
            ]
        }

        # Write match results to temp file
        match_file = tmpdir_path / "apple_matches.json"
        write_json(match_file, apple_match_result)

        # Run generate-splits command
        output_dir = tmpdir_path / "ynab" / "edits"
        result = subprocess.run(
            [
                "uv",
                "run",
                "finances",
                "ynab",
                "generate-splits",
                "--input-file",
                str(match_file),
                "--confidence-threshold",
                "0.8",
                "--output-dir",
                str(output_dir),
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )

        # Verify command succeeded
        assert result.returncode == 0
        assert "Generated 1 edits" in result.stdout

        # Verify edit file was created
        edit_files = list(output_dir.glob("*apple*.json"))
        assert len(edit_files) == 1

        # Verify edit file structure
        with open(edit_files[0]) as f:
            edit_data = json.load(f)

        assert edit_data["metadata"]["match_type"] == "apple"
        assert len(edit_data["edits"]) == 1

        edit = edit_data["edits"][0]
        assert len(edit["splits"]) == 2

        # Verify splits sum to transaction amount (in milliunits)
        splits_total = sum(split["amount"] for split in edit["splits"])
        expected_total = transaction["amount"]  # Already in milliunits (negative for expense)
        assert splits_total == expected_total


@pytest.mark.e2e
@pytest.mark.ynab
def test_ynab_generate_splits_with_confidence_threshold():
    """
    Test confidence threshold filtering in split generation.

    Verifies:
    - High-confidence matches are auto-approved
    - Low-confidence matches require review
    - Threshold filtering works correctly
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)

        # Setup YNAB cache
        ynab_cache_dir = tmpdir_path / "ynab" / "cache"
        ynab_cache_dir.mkdir(parents=True, exist_ok=True)

        cache_data = generate_synthetic_ynab_cache(num_transactions=10)

        write_json(ynab_cache_dir / "accounts.json", cache_data["accounts"])
        write_json(ynab_cache_dir / "categories.json", cache_data["categories"])
        write_json(ynab_cache_dir / "transactions.json", cache_data["transactions"])

        # Create match results with varying confidence levels
        # Use fixed amounts that are evenly divisible (whole cents)
        test_amounts = [-23990, -15990, -31990]  # -$23.99, -$15.99, -$31.99 in milliunits
        confidence_values = [0.95, 0.75, 0.85]  # high, low, medium

        matches = []
        for i in range(3):
            transaction = cache_data["transactions"][i].copy()
            transaction["amount"] = test_amounts[i]
            transaction_amount_cents = milliunits_to_cents(transaction["amount"])

            matches.append(
                {
                    "transaction_id": transaction["id"],
                    "confidence": confidence_values[i],
                    "ynab_transaction": {
                        "id": transaction["id"],
                        "date": transaction["date"],
                        "amount": transaction["amount"],  # Already in milliunits (negative for expense)
                        "payee_name": transaction["payee_name"],
                    },
                    "amazon_orders": [
                        {
                            "order_id": f"123-456789{i}-1234567",
                            "order_date": transaction["date"],
                            "total_owed": transaction_amount_cents,
                            "items": [
                                {
                                    "name": f"Test Item {i}",
                                    "amount": transaction_amount_cents,
                                    "quantity": 1,
                                    "unit_price": transaction_amount_cents,
                                }
                            ],
                        }
                    ],
                    "strategy": "exact_match",
                }
            )

        match_result = {"matches": matches}

        # Write match results to temp file
        match_file = tmpdir_path / "amazon_matches.json"
        write_json(match_file, match_result)

        # Run generate-splits with 0.8 threshold
        output_dir = tmpdir_path / "ynab" / "edits"
        result = subprocess.run(
            [
                "uv",
                "run",
                "finances",
                "ynab",
                "generate-splits",
                "--input-file",
                str(match_file),
                "--confidence-threshold",
                "0.8",
                "--output-dir",
                str(output_dir),
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )

        # Verify command succeeded
        assert result.returncode == 0
        assert "Generated 3 edits" in result.stdout
        assert "Auto-approved: 2" in result.stdout  # 0.95 and 0.85
        assert "Requires review: 1" in result.stdout  # 0.75

        # Verify edit file
        edit_files = list(output_dir.glob("*amazon*.json"))
        assert len(edit_files) == 1

        with open(edit_files[0]) as f:
            edit_data = json.load(f)

        # Verify summary statistics
        assert edit_data["summary"]["total_edits"] == 3
        assert edit_data["summary"]["auto_approved"] == 2
        assert edit_data["summary"]["requires_review"] == 1

        # Verify individual edit approval status
        edits = edit_data["edits"]
        assert edits[0]["confidence"] == 0.95
        assert edits[0]["auto_approved"] is True
        assert edits[1]["confidence"] == 0.75
        assert edits[1]["auto_approved"] is False
        assert edits[2]["confidence"] == 0.85
        assert edits[2]["auto_approved"] is True


@pytest.mark.e2e
@pytest.mark.ynab
def test_ynab_generate_splits_invalid_input():
    """
    Test error handling for invalid input file.

    Verifies:
    - Command fails gracefully with non-existent file
    - Provides helpful error message
    - Returns non-zero exit code
    """
    result = subprocess.run(
        [
            "uv",
            "run",
            "finances",
            "ynab",
            "generate-splits",
            "--input-file",
            "/nonexistent/path/to/matches.json",
        ],
        capture_output=True,
        text=True,
        timeout=30,
    )

    # Verify command failed
    assert result.returncode != 0
    assert "Input file not found" in result.stderr or "Input file not found" in result.stdout


@pytest.mark.e2e
@pytest.mark.ynab
def test_ynab_apply_edits_missing_file():
    """
    Test error handling when edit file doesn't exist.

    Verifies:
    - Command fails gracefully with missing file
    - Provides helpful error message
    - Returns non-zero exit code
    """
    result = subprocess.run(
        [
            "uv",
            "run",
            "finances",
            "ynab",
            "apply-edits",
            "--edit-file",
            "/nonexistent/path/to/edits.json",
            "--force",
        ],
        capture_output=True,
        text=True,
        timeout=30,
    )

    # Verify command failed
    assert result.returncode != 0
    assert "Edit file not found" in result.stderr or "Edit file not found" in result.stdout


@pytest.mark.e2e
@pytest.mark.ynab
def test_ynab_generate_splits_empty_matches():
    """
    Test handling of empty match results.

    Verifies:
    - Command handles empty matches gracefully
    - Creates edit file with zero edits
    - Reports correct summary statistics
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)

        # Create empty match result
        match_result = {"matches": []}

        match_file = tmpdir_path / "amazon_matches.json"
        write_json(match_file, match_result)

        # Run generate-splits
        output_dir = tmpdir_path / "ynab" / "edits"
        result = subprocess.run(
            [
                "uv",
                "run",
                "finances",
                "ynab",
                "generate-splits",
                "--input-file",
                str(match_file),
                "--output-dir",
                str(output_dir),
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )

        # Verify command succeeded
        assert result.returncode == 0
        assert "Generated 0 edits" in result.stdout

        # Verify edit file was created
        edit_files = list(output_dir.glob("*.json"))
        assert len(edit_files) == 1

        # Verify empty edits
        with open(edit_files[0]) as f:
            edit_data = json.load(f)

        assert edit_data["summary"]["total_edits"] == 0
        assert len(edit_data["edits"]) == 0


@pytest.mark.e2e
@pytest.mark.ynab
def test_ynab_generate_splits_malformed_json():
    """
    Test error handling for malformed JSON input.

    Verifies:
    - Command fails gracefully with malformed JSON
    - Provides helpful error message
    - Returns non-zero exit code
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)

        # Create malformed JSON file
        match_file = tmpdir_path / "bad_matches.json"
        with open(match_file, "w") as f:
            f.write("{ this is not valid json }")

        # Run generate-splits
        output_dir = tmpdir_path / "ynab" / "edits"
        result = subprocess.run(
            [
                "uv",
                "run",
                "finances",
                "ynab",
                "generate-splits",
                "--input-file",
                str(match_file),
                "--output-dir",
                str(output_dir),
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )

        # Verify command failed
        assert result.returncode != 0


@pytest.mark.e2e
@pytest.mark.ynab
def test_ynab_cli_help_commands():
    """
    Test that all YNAB CLI commands display help correctly.

    Verifies:
    - Main ynab command shows help
    - All subcommands show help
    - Help output contains expected information
    """
    # Test main ynab help
    result = subprocess.run(
        ["uv", "run", "finances", "ynab", "--help"], capture_output=True, text=True, timeout=30
    )

    assert result.returncode == 0
    assert "YNAB transaction update" in result.stdout
    assert "sync-cache" in result.stdout
    assert "generate-splits" in result.stdout
    assert "apply-edits" in result.stdout

    # Test sync-cache help
    result = subprocess.run(
        ["uv", "run", "finances", "ynab", "sync-cache", "--help"], capture_output=True, text=True, timeout=30
    )

    assert result.returncode == 0
    assert "Sync YNAB data to local cache" in result.stdout
    assert "--days" in result.stdout

    # Test generate-splits help
    result = subprocess.run(
        ["uv", "run", "finances", "ynab", "generate-splits", "--help"],
        capture_output=True,
        text=True,
        timeout=30,
    )

    assert result.returncode == 0
    assert "Generate transaction split edits" in result.stdout
    assert "--input-file" in result.stdout
    assert "--confidence-threshold" in result.stdout
    assert "--dry-run" in result.stdout

    # Test apply-edits help
    result = subprocess.run(
        ["uv", "run", "finances", "ynab", "apply-edits", "--help"], capture_output=True, text=True, timeout=30
    )

    assert result.returncode == 0
    assert "Apply transaction edits to YNAB" in result.stdout
    assert "--edit-file" in result.stdout
    assert "--force" in result.stdout
