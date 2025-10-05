#!/usr/bin/env python3
"""
E2E Tests for Cash Flow Analysis and Retirement CLI Commands

End-to-end tests that execute actual CLI commands via subprocess.
Uses synthetic YNAB data to test real command execution without mocking.
"""

import json
import subprocess
import tempfile
from datetime import date, timedelta
from pathlib import Path

import pytest

from tests.fixtures.synthetic_data import generate_synthetic_ynab_cache


@pytest.mark.e2e
class TestCashFlowAnalysisCLI:
    """E2E tests for finances cashflow commands."""

    def setup_method(self):
        """Set up test environment with temporary directories and synthetic data."""
        self.temp_dir = Path(tempfile.mkdtemp())
        self.ynab_cache_dir = self.temp_dir / "ynab" / "cache"
        self.charts_dir = self.temp_dir / "charts"

        # Create directories
        self.ynab_cache_dir.mkdir(parents=True)
        self.charts_dir.mkdir(parents=True)

    def teardown_method(self):
        """Clean up temporary test environment."""
        import shutil

        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir)

    def _setup_synthetic_ynab_data(self, num_transactions: int = 100, days_back: int = 90) -> dict:
        """
        Create synthetic YNAB data with realistic transaction history.

        Args:
            num_transactions: Number of transactions to generate
            days_back: Number of days back to generate transactions for

        Returns:
            Dictionary with accounts, categories, and transactions
        """
        start_date = date.today() - timedelta(days=days_back)
        end_date = date.today()

        # Generate synthetic data
        data = generate_synthetic_ynab_cache(
            num_accounts=3,
            num_transactions=num_transactions,
            start_date=start_date,
            end_date=end_date,
        )

        # Write to cache directory
        with open(self.ynab_cache_dir / "accounts.json", "w") as f:
            json.dump(data["accounts"], f, indent=2)

        with open(self.ynab_cache_dir / "categories.json", "w") as f:
            json.dump(data["categories"], f, indent=2)

        with open(self.ynab_cache_dir / "transactions.json", "w") as f:
            json.dump(data["transactions"], f, indent=2)

        return data

    def test_cashflow_analyze_command(self):
        """Test finances cashflow analyze with synthetic transactions."""
        # Setup synthetic YNAB data with 90 days of transactions
        self._setup_synthetic_ynab_data(num_transactions=150, days_back=90)

        # Calculate date range
        start_date = (date.today() - timedelta(days=90)).strftime("%Y-%m-%d")
        end_date = date.today().strftime("%Y-%m-%d")

        # Run command
        result = subprocess.run(
            [
                "uv",
                "run",
                "finances",
                "--config-env",
                "test",
                "cashflow",
                "analyze",
                "--start",
                start_date,
                "--end",
                end_date,
                "--output-dir",
                str(self.charts_dir),
            ],
            capture_output=True,
            text=True,
            timeout=30,
            env={
                **dict(subprocess.os.environ),
                "FINANCES_DATA_DIR": str(self.temp_dir),
            },
        )

        # Verify command succeeded
        assert result.returncode == 0, f"Command failed with output: {result.stderr}"

        # Verify output mentions key operations
        assert "[ANALYSIS]" in result.stdout or "Loading" in result.stdout
        assert "[DASHBOARD]" in result.stdout or "Dashboard" in result.stdout
        assert "saved to:" in result.stdout or "✅" in result.stdout

        # Verify chart file was created
        chart_files = list(self.charts_dir.glob("*.png"))
        assert len(chart_files) > 0, "No chart files were created"

        # Verify file has reasonable size (not empty)
        chart_file = chart_files[0]
        assert chart_file.stat().st_size > 10000, "Chart file is suspiciously small"

    def test_cashflow_analyze_missing_data(self):
        """Test finances cashflow analyze error handling when no YNAB data exists."""
        # Don't create any YNAB data - directory is empty

        start_date = (date.today() - timedelta(days=90)).strftime("%Y-%m-%d")
        end_date = date.today().strftime("%Y-%m-%d")

        result = subprocess.run(
            [
                "uv",
                "run",
                "finances",
                "--config-env",
                "test",
                "cashflow",
                "analyze",
                "--start",
                start_date,
                "--end",
                end_date,
                "--output-dir",
                str(self.charts_dir),
            ],
            capture_output=True,
            text=True,
            timeout=30,
            env={
                **dict(subprocess.os.environ),
                "FINANCES_DATA_DIR": str(self.temp_dir),
            },
        )

        # Command should fail gracefully
        assert result.returncode != 0
        assert "YNAB data not found" in result.stderr or "FileNotFoundError" in result.stderr


@pytest.mark.e2e
class TestRetirementCLI:
    """E2E tests for finances retirement commands."""

    def setup_method(self):
        """Set up test environment with temporary directories and synthetic data."""
        self.temp_dir = Path(tempfile.mkdtemp())
        self.ynab_cache_dir = self.temp_dir / "ynab" / "cache"
        self.ynab_edits_dir = self.temp_dir / "ynab" / "edits"

        # Create directories
        self.ynab_cache_dir.mkdir(parents=True)
        self.ynab_edits_dir.mkdir(parents=True)

    def teardown_method(self):
        """Clean up temporary test environment."""
        import shutil

        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir)

    def _create_retirement_accounts_fixture(self) -> dict:
        """Create synthetic YNAB accounts with retirement accounts."""
        return {
            "accounts": [
                {
                    "id": "retirement-401k",
                    "name": "Test Retirement: 401(k) Plan",
                    "type": "otherAsset",
                    "on_budget": False,
                    "closed": False,
                    "balance": 100000000,  # $100,000.00 in milliunits
                    "cleared_balance": 100000000,
                    "last_reconciled_at": "2024-08-01T00:00:00Z",
                },
                {
                    "id": "retirement-ira",
                    "name": "Test Retirement: Roth IRA",
                    "type": "otherAsset",
                    "on_budget": False,
                    "closed": False,
                    "balance": 50000000,  # $50,000.00 in milliunits
                    "cleared_balance": 50000000,
                    "last_reconciled_at": "2024-08-01T00:00:00Z",
                },
                {
                    "id": "checking-account",
                    "name": "Test Checking",
                    "type": "checking",
                    "on_budget": True,
                    "closed": False,
                    "balance": 5000000,  # $5,000.00 in milliunits
                    "cleared_balance": 5000000,
                    "last_reconciled_at": None,
                },
            ],
            "server_knowledge": 12345,
        }

    def test_retirement_list_command(self):
        """Test finances retirement list displays retirement accounts."""
        # Create accounts fixture
        accounts_data = self._create_retirement_accounts_fixture()

        with open(self.ynab_cache_dir / "accounts.json", "w") as f:
            json.dump(accounts_data, f, indent=2)

        result = subprocess.run(
            [
                "uv",
                "run",
                "finances",
                "--config-env",
                "test",
                "retirement",
                "list",
            ],
            capture_output=True,
            text=True,
            timeout=10,
            env={
                **dict(subprocess.os.environ),
                "FINANCES_DATA_DIR": str(self.temp_dir),
            },
        )

        assert result.returncode == 0
        assert "Retirement Accounts (from YNAB):" in result.stdout
        assert "Test Retirement: 401(k) Plan" in result.stdout
        assert "Test Retirement: Roth IRA" in result.stdout
        assert "$100,000.00" in result.stdout
        assert "$50,000.00" in result.stdout

        # Should NOT show checking account
        assert "Test Checking" not in result.stdout

    def test_retirement_update_invalid_date_format(self):
        """Test finances retirement update with invalid date format."""
        # Create accounts fixture
        accounts_data = self._create_retirement_accounts_fixture()

        with open(self.ynab_cache_dir / "accounts.json", "w") as f:
            json.dump(accounts_data, f, indent=2)

        result = subprocess.run(
            [
                "uv",
                "run",
                "finances",
                "--config-env",
                "test",
                "retirement",
                "update",
                "--date",
                "08/31/2024",  # Invalid format
            ],
            capture_output=True,
            text=True,
            timeout=10,
            env={
                **dict(subprocess.os.environ),
                "FINANCES_DATA_DIR": str(self.temp_dir),
            },
        )

        assert result.returncode != 0
        assert "Invalid date format" in result.stderr or "Invalid date format" in result.stdout

    def test_retirement_update_multiple_accounts(self):
        """Test finances retirement update with multiple account updates."""
        # Create accounts fixture
        accounts_data = self._create_retirement_accounts_fixture()

        with open(self.ynab_cache_dir / "accounts.json", "w") as f:
            json.dump(accounts_data, f, indent=2)

        # Update both accounts:
        # First account ($100k): Update to $102,000 (+$2,000)
        # Second account ($50k): Update to $51,000 (+$1,000)
        # Confirm: Yes
        user_input = "102000\n51000\ny\n"

        result = subprocess.run(
            [
                "uv",
                "run",
                "finances",
                "--config-env",
                "test",
                "retirement",
                "update",
            ],
            input=user_input,
            capture_output=True,
            text=True,
            timeout=10,
            env={
                **dict(subprocess.os.environ),
                "FINANCES_DATA_DIR": str(self.temp_dir),
            },
        )

        assert result.returncode == 0
        assert "Adjustment:" in result.stdout
        assert "Total Net Adjustment:" in result.stdout
        assert "YNAB edits file created:" in result.stdout

        # Verify edits file has both mutations
        edits_files = list(self.ynab_edits_dir.glob("*retirement_edits.yaml"))
        assert len(edits_files) == 1

        with open(edits_files[0]) as f:
            import yaml

            edits_data = yaml.safe_load(f)

        assert edits_data["metadata"]["total_mutations"] == 2

    def test_retirement_list_no_accounts(self):
        """Test finances retirement list when no retirement accounts exist."""
        # Create accounts with only checking account
        accounts_data = {
            "accounts": [
                {
                    "id": "checking-only",
                    "name": "Test Checking",
                    "type": "checking",
                    "on_budget": True,
                    "closed": False,
                    "balance": 5000000,
                    "cleared_balance": 5000000,
                    "last_reconciled_at": None,
                }
            ],
            "server_knowledge": 123,
        }

        with open(self.ynab_cache_dir / "accounts.json", "w") as f:
            json.dump(accounts_data, f, indent=2)

        result = subprocess.run(
            [
                "uv",
                "run",
                "finances",
                "--config-env",
                "test",
                "retirement",
                "list",
            ],
            capture_output=True,
            text=True,
            timeout=10,
            env={
                **dict(subprocess.os.environ),
                "FINANCES_DATA_DIR": str(self.temp_dir),
            },
        )

        assert result.returncode == 0
        assert "No retirement accounts found in YNAB." in result.stdout

    def test_retirement_update_cancel_workflow(self):
        """Test canceling the retirement update workflow."""
        # Create accounts fixture
        accounts_data = self._create_retirement_accounts_fixture()

        with open(self.ynab_cache_dir / "accounts.json", "w") as f:
            json.dump(accounts_data, f, indent=2)

        # Update one account but decline to generate edits
        user_input = "101000\n\nn\n"  # Update first, skip second, decline generation

        result = subprocess.run(
            [
                "uv",
                "run",
                "finances",
                "--config-env",
                "test",
                "retirement",
                "update",
            ],
            input=user_input,
            capture_output=True,
            text=True,
            timeout=10,
            env={
                **dict(subprocess.os.environ),
                "FINANCES_DATA_DIR": str(self.temp_dir),
            },
        )

        assert result.returncode == 0
        assert "Cancelled." in result.stdout

        # Verify no edits file was created
        edits_files = list(self.ynab_edits_dir.glob("*retirement_edits.yaml"))
        assert len(edits_files) == 0
