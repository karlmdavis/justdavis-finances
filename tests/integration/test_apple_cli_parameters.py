#!/usr/bin/env python3
"""
Integration tests for Apple CLI command parameters.

Tests parameter acceptance and basic behavior for Apple CLI commands.
Note: Some commands have placeholder implementations, so tests verify
parameter handling rather than full functionality.
"""

import tempfile
from pathlib import Path

from click.testing import CliRunner

from finances.cli.apple import apple


class TestAppleCLIParameters:
    """Test Apple CLI command parameter handling."""

    def setup_method(self):
        """Set up test environment."""
        self.runner = CliRunner()
        self.temp_dir = Path(tempfile.mkdtemp())

    def teardown_method(self):
        """Clean up test environment."""
        import shutil

        shutil.rmtree(self.temp_dir)

    def test_parse_receipts_accepts_required_parameters(self):
        """Test apple parse-receipts accepts required --input-dir parameter."""
        # Create input directory
        input_dir = self.temp_dir / "input"
        input_dir.mkdir()

        result = self.runner.invoke(
            apple, ["parse-receipts", "--input-dir", str(input_dir), "--output-dir", str(self.temp_dir)]
        )

        # Should accept parameters (may have no emails, but that's OK)
        assert result.exit_code in [0, 1]

    def test_parse_receipts_verbose_flag(self):
        """Test apple parse-receipts --verbose flag is accepted."""
        input_dir = self.temp_dir / "input"
        input_dir.mkdir()

        result = self.runner.invoke(
            apple,
            [
                "parse-receipts",
                "--input-dir",
                str(input_dir),
                "--output-dir",
                str(self.temp_dir),
                "--verbose",
            ],
        )

        assert result.exit_code in [0, 1]

    def test_match_accepts_date_range_parameters(self):
        """Test apple match accepts --start and --end parameters."""
        result = self.runner.invoke(
            apple,
            ["match", "--start", "2024-07-01", "--end", "2024-07-31", "--output-dir", str(self.temp_dir)],
        )

        # Command should accept parameters (implementation is placeholder)
        assert result.exit_code in [0, 1]

    def test_match_verbose_flag(self):
        """Test apple match --verbose flag is accepted."""
        result = self.runner.invoke(
            apple,
            [
                "match",
                "--start",
                "2024-07-01",
                "--end",
                "2024-07-31",
                "--output-dir",
                str(self.temp_dir),
                "--verbose",
            ],
        )

        assert result.exit_code in [0, 1]

    def test_match_apple_ids_filter(self):
        """Test apple match --apple-ids parameter is accepted."""
        result = self.runner.invoke(
            apple,
            [
                "match",
                "--start",
                "2024-07-01",
                "--end",
                "2024-07-31",
                "--output-dir",
                str(self.temp_dir),
                "--apple-ids",
                "karl@example.com",
                "--apple-ids",
                "erica@example.com",
            ],
        )

        assert result.exit_code in [0, 1]

    def test_match_with_invalid_receipt_dates(self):
        """Test apple match handles receipts with null/invalid dates gracefully."""
        import sys
        from pathlib import Path

        # Add tests directory to path for fixture imports
        tests_dir = Path(__file__).parent.parent
        sys.path.insert(0, str(tests_dir))

        from finances.core.json_utils import write_json

        # Create YNAB cache with synthetic data including Apple transactions
        ynab_cache_dir = self.temp_dir / "ynab" / "cache"
        ynab_cache_dir.mkdir(parents=True)

        # Manually create YNAB data with Apple transactions
        accounts_data = {
            "accounts": [
                {
                    "id": "account-001",
                    "name": "Test Account",
                    "type": "checking",
                    "balance": 1000000,
                    "cleared_balance": 1000000,
                    "uncleared_balance": 0,
                    "closed": False,
                    "on_budget": True,
                }
            ],
            "server_knowledge": 12345,
        }

        # Create transactions with Apple payee
        transactions_data = [
            {
                "id": "tx-001",
                "date": "2025-01-15",
                "amount": -1999,  # $19.99
                "account_id": "account-001",
                "account_name": "Test Account",
                "payee_name": "Apple",
                "category_id": "cat-001",
                "category_name": "Shopping",
                "memo": None,
                "cleared": "cleared",
                "approved": True,
            },
            {
                "id": "tx-002",
                "date": "2025-02-20",
                "amount": -2999,  # $29.99
                "account_id": "account-001",
                "account_name": "Test Account",
                "payee_name": "Apple",
                "category_id": "cat-001",
                "category_name": "Shopping",
                "memo": None,
                "cleared": "cleared",
                "approved": True,
            },
        ]

        categories_data = {
            "category_groups": [
                {
                    "id": "group-001",
                    "name": "Test Group",
                    "categories": [{"id": "cat-001", "name": "Shopping"}],
                }
            ],
            "server_knowledge": 67890,
        }

        write_json(ynab_cache_dir / "accounts.json", accounts_data)
        write_json(ynab_cache_dir / "transactions.json", transactions_data)
        write_json(ynab_cache_dir / "categories.json", categories_data)

        # Create Apple exports directory with receipts containing invalid dates
        apple_exports_dir = self.temp_dir / "apple" / "exports" / "2025-01-01_00-00-00_apple_receipts_export"
        apple_exports_dir.mkdir(parents=True)

        # Create receipts with mixed valid and invalid dates
        receipts = [
            {
                "apple_id": "test@example.com",
                "receipt_date": "Jan 15, 2025",  # Valid date string
                "order_id": "ORDER-001",
                "document_number": "DOC-001",
                "total": 1999,  # $19.99 in cents
                "currency": "USD",
                "items": [{"name": "Test App", "amount": 1999}],
            },
            {
                "apple_id": "test@example.com",
                "receipt_date": None,  # NULL date - should be skipped
                "order_id": "ORDER-002",
                "document_number": "DOC-002",
                "total": 999,
                "currency": "USD",
                "items": [{"name": "Another App", "amount": 999}],
            },
            {
                "apple_id": "test@example.com",
                "receipt_date": "Feb 20, 2025",  # Valid date string
                "order_id": "ORDER-003",
                "document_number": "DOC-003",
                "total": 2999,
                "currency": "USD",
                "items": [{"name": "Third App", "amount": 2999}],
            },
        ]

        receipts_file = apple_exports_dir / "all_receipts_combined.json"
        write_json(receipts_file, receipts)

        # Create output directory
        output_dir = self.temp_dir / "output"
        output_dir.mkdir()

        # Run match command - should handle invalid dates without crashing
        result = self.runner.invoke(
            apple,
            [
                "match",
                "--output-dir",
                str(output_dir),
            ],
            env={
                "FINANCES_DATA_DIR": str(self.temp_dir),
                "FINANCES_ENV": "test",
            },
            obj={},  # Provide empty obj dict to avoid NoneType error
        )

        # Should complete successfully (exit 0) or with acceptable failure (exit 1 for no matches)
        # But should NOT crash with AttributeError about .dt accessor
        assert result.exit_code in [0, 1], f"Unexpected exit code {result.exit_code}: {result.output}"
        assert "AttributeError" not in result.output, f"Should not crash with AttributeError: {result.output}"
        assert (
            ".dt accessor" not in result.output.lower()
        ), f"Should not have .dt accessor error: {result.output}"
        assert (
            "Can only use .dt accessor with datetimelike values" not in result.output
        ), f"Should not have datetime accessor error: {result.output}"

        # Verify receipts with null dates were skipped (only 2 valid receipts should be processed)
        assert (
            "2 Apple receipts" in result.output or result.exit_code == 1
        ), "Should process only valid receipts"

    def test_match_with_date_objects_in_dataclasses(self):
        """Test apple match handles date objects in dataclasses and serializes to JSON correctly."""
        import json
        import sys
        from pathlib import Path

        # Add tests directory to path for fixture imports
        tests_dir = Path(__file__).parent.parent
        sys.path.insert(0, str(tests_dir))

        from finances.core.json_utils import write_json

        # Create YNAB cache with Apple transactions
        ynab_cache_dir = self.temp_dir / "ynab" / "cache"
        ynab_cache_dir.mkdir(parents=True)

        accounts_data = {
            "accounts": [
                {
                    "id": "account-001",
                    "name": "Test Account",
                    "type": "checking",
                    "balance": 1000000,
                    "cleared_balance": 1000000,
                    "uncleared_balance": 0,
                    "closed": False,
                    "on_budget": True,
                }
            ],
            "server_knowledge": 12345,
        }

        transactions_data = [
            {
                "id": "tx-001",
                "date": "2025-01-15",
                "amount": -1999,
                "account_id": "account-001",
                "account_name": "Test Account",
                "payee_name": "Apple",
                "category_id": "cat-001",
                "category_name": "Shopping",
                "memo": None,
                "cleared": "cleared",
                "approved": True,
            }
        ]

        categories_data = {
            "category_groups": [
                {
                    "id": "group-001",
                    "name": "Test Group",
                    "categories": [{"id": "cat-001", "name": "Shopping"}],
                }
            ],
            "server_knowledge": 67890,
        }

        write_json(ynab_cache_dir / "accounts.json", accounts_data)
        write_json(ynab_cache_dir / "transactions.json", transactions_data)
        write_json(ynab_cache_dir / "categories.json", categories_data)

        # Create Apple receipts with actual date objects (not strings)
        # This simulates what would happen if normalize_apple_receipt_data returns date objects
        apple_exports_dir = self.temp_dir / "apple" / "exports" / "2025-01-01_00-00-00_apple_receipts_export"
        apple_exports_dir.mkdir(parents=True)

        receipts = [
            {
                "apple_id": "test@example.com",
                "receipt_date": "Jan 15, 2025",  # String that will be parsed to date
                "order_id": "ORDER-001",
                "document_number": "DOC-001",
                "total": 1999,
                "currency": "USD",
                "items": [{"name": "Test App", "amount": 1999}],
            }
        ]

        receipts_file = apple_exports_dir / "all_receipts_combined.json"
        write_json(receipts_file, receipts)

        # Create output directory
        output_dir = self.temp_dir / "output"
        output_dir.mkdir()

        # Run match command - should serialize date objects correctly
        result = self.runner.invoke(
            apple,
            ["match", "--output-dir", str(output_dir)],
            env={"FINANCES_DATA_DIR": str(self.temp_dir), "FINANCES_ENV": "test"},
            obj={},
        )

        # Should complete successfully
        assert result.exit_code in [
            0,
            1,
        ], f"Unexpected exit code {result.exit_code}: {result.output}"

        # Should not crash with date serialization error
        assert (
            "Object of type date is not JSON serializable" not in result.output
        ), f"Should not crash with date serialization error: {result.output}"

        # Verify output file was created and contains valid JSON
        output_files = list(output_dir.glob("*_apple_matching_results.json"))
        if output_files:
            with open(output_files[0]) as f:
                data = json.load(f)
                assert "matches" in data, "Output should contain matches"
                # Dates should be serialized as strings in the output
                if data["matches"]:
                    for match in data["matches"]:
                        if "transaction" in match and "date" in match["transaction"]:
                            assert isinstance(
                                match["transaction"]["date"], str
                            ), "Transaction dates should be strings in JSON"
                        if "receipts" in match:
                            for receipt in match["receipts"]:
                                if "date" in receipt:
                                    assert isinstance(
                                        receipt["date"], str
                                    ), "Receipt dates should be strings in JSON"
