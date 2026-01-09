#!/usr/bin/env python3
"""
E2E CLI tests for bank accounts flow command.

These tests execute the actual `finances flow` command via subprocess to verify
the complete bank account integration with the flow system.
"""

import json
import tempfile
from pathlib import Path

import pytest

from finances.bank_accounts.models import AccountConfig, BankAccountsConfig, ImportPattern
from finances.core.json_utils import write_json


def create_test_config_file(config_dir: Path, source_dir: Path) -> Path:
    """Create a bank_accounts_config.json file for testing."""
    config = BankAccountsConfig(
        accounts=(
            AccountConfig(
                ynab_account_id="test-account-123",
                ynab_account_name="Chase Credit Test",
                slug="chase_credit",
                bank_name="Chase",
                account_type="credit",
                statement_frequency="monthly",
                source_directory=str(source_dir),
                import_patterns=(
                    ImportPattern(
                        pattern="*.csv",
                        format_handler="chase_credit_csv",
                    ),
                ),
                download_instructions="Test download instructions",
            ),
        )
    )

    config_file = config_dir / "bank_accounts_config.json"
    write_json(config_file, config.to_dict())
    return config_file


def create_synthetic_bank_csv(source_dir: Path) -> Path:
    """Create synthetic Chase Credit CSV export file."""
    csv_content = """Transaction Date,Post Date,Description,Category,Type,Amount,Memo
01/15/2024,01/15/2024,SAFEWAY #1234,Groceries,Sale,-45.67,Weekly groceries
01/20/2024,01/20/2024,AMAZON MKTPL,Shopping,Sale,-123.45,
01/25/2024,01/25/2024,PAYMENT RECEIVED,Payment/Credit,Payment,500.00,
"""

    csv_file = source_dir / "chase_transactions.csv"
    csv_file.write_text(csv_content)
    return csv_file


def create_synthetic_ynab_cache(cache_dir: Path) -> None:
    """Create synthetic YNAB cache files."""
    transactions = [
        {
            "id": "tx-001",
            "date": "2024-01-15",
            "amount": -45670,  # -$45.67 in milliunits
            "payee_name": "Safeway",
            "memo": "Grocery shopping",
            "account_id": "test-account-123",
            "account_name": "Chase Credit Test",
            "category_name": "Groceries",
            "cleared": "cleared",
            "approved": True,
        },
        {
            "id": "tx-002",
            "date": "2024-01-10",
            "amount": -20990,  # -$20.99 in milliunits
            "payee_name": "Target",
            "memo": "Shopping",
            "account_id": "test-account-123",
            "account_name": "Chase Credit Test",
            "category_name": "Shopping",
            "cleared": "cleared",
            "approved": True,
        },
    ]

    accounts_data = {
        "accounts": [
            {
                "id": "test-account-123",
                "name": "Chase Credit Test",
                "type": "creditCard",
                "balance": -66660,
                "cleared_balance": -66660,
                "uncleared_balance": 0,
                "closed": False,
            }
        ],
        "server_knowledge": 100,
    }

    categories_data = {
        "category_groups": [
            {
                "id": "cg-001",
                "name": "Spending",
                "hidden": False,
                "categories": [
                    {"id": "cat-001", "name": "Groceries", "hidden": False},
                    {"id": "cat-002", "name": "Shopping", "hidden": False},
                ],
            }
        ],
        "server_knowledge": 100,
    }

    cache_dir.mkdir(parents=True, exist_ok=True)
    write_json(cache_dir / "transactions.json", transactions)
    write_json(cache_dir / "accounts.json", accounts_data)
    write_json(cache_dir / "categories.json", categories_data)


@pytest.mark.e2e
def test_finances_flow_bank_accounts_cli(tmp_path, monkeypatch):
    """
    Test complete bank accounts flow via CLI subprocess.

    This test verifies that the `finances flow` command properly integrates
    the bank account nodes and executes the full pipeline.

    Setup:
    - Create bank_accounts_config.json
    - Create raw CSV export file
    - Create YNAB cache

    Execute:
    - Run `finances flow` command (non-interactive with skips)

    Verify:
    - Command returns 0 (success)
    - Files created in correct directories:
      - bank_accounts/raw/chase_credit/
      - bank_accounts/normalized/
      - bank_accounts/reconciliation/
    """
    # Setup directory structure
    data_dir = tmp_path / "data"
    config_dir = tmp_path / "config"
    source_dir = tmp_path / "source"

    data_dir.mkdir()
    config_dir.mkdir()
    source_dir.mkdir()

    # Create test data
    create_test_config_file(config_dir, source_dir)
    create_synthetic_bank_csv(source_dir)
    ynab_cache_dir = data_dir / "ynab" / "cache"
    create_synthetic_ynab_cache(ynab_cache_dir)

    # Create other required directories for flow system
    (data_dir / "amazon" / "raw").mkdir(parents=True, exist_ok=True)
    (data_dir / "apple" / "emails").mkdir(parents=True, exist_ok=True)
    (data_dir / "ynab" / "edits").mkdir(parents=True, exist_ok=True)

    # Set environment variables
    import os

    env = os.environ.copy()
    env.update(
        {
            "FINANCES_DATA_DIR": str(data_dir),
            "FINANCES_CONFIG_DIR": str(config_dir),
            "FINANCES_ENV": "test",
            "YNAB_API_TOKEN": "test-token",
            "EMAIL_PASSWORD": "test-password",
        }
    )

    # Note: The flow command is interactive and requires user input.
    # For a true E2E test, we would need to use pexpect to send 'y' or 'n'
    # responses to each node prompt.
    #
    # For now, we'll mark this as a skip since the flow system doesn't have
    # a non-interactive mode yet. This test serves as documentation of what
    # we want to test once we have that capability.

    # TODO: Once flow system supports --yes flag or similar, execute this:
    # cmd = [
    #     "uv", "run", "finances", "flow",
    #     "bank_data_retrieve", "bank_data_parse", "bank_data_reconcile"
    # ]
    # result = subprocess.run(
    #     cmd,
    #     cwd="/Users/karl/workspaces/justdavis/personal/justdavis-finances",
    #     env=env,
    #     capture_output=True,
    #     text=True,
    # )
    #
    # assert result.returncode == 0, f"Command failed: {result.stderr}"
    #
    # # Verify output files exist
    # raw_dir = data_dir / "bank_accounts" / "raw" / "chase_credit"
    # assert raw_dir.exists(), "Raw directory should be created"
    # assert len(list(raw_dir.glob("*.csv"))) > 0, "Raw CSV should be copied"
    #
    # normalized_dir = data_dir / "bank_accounts" / "normalized"
    # assert normalized_dir.exists(), "Normalized directory should be created"
    # assert len(list(normalized_dir.glob("*.json"))) > 0, "Normalized JSON should be created"
    #
    # reconciliation_dir = data_dir / "bank_accounts" / "reconciliation"
    # assert reconciliation_dir.exists(), "Reconciliation directory should be created"
    # assert len(list(reconciliation_dir.glob("*.json"))) > 0, "Operations JSON should be created"

    pytest.skip("Flow command is interactive - needs --yes flag or pexpect integration")


@pytest.mark.e2e
@pytest.mark.skip(reason="Flow change detection not yet implemented")
def test_flow_skips_when_no_changes(tmp_path, monkeypatch):
    """
    Flow should skip nodes when dependencies haven't changed.

    Setup:
    - Run flow once (all nodes execute)
    - Run flow again without changing data

    Verify:
    - Second run detects no changes
    - Second run skips nodes that don't need to run
    """
    # This test will be implemented once:
    # 1. Flow system supports non-interactive mode
    # 2. Flow system implements change detection based on file timestamps

    pytest.skip("Change detection not yet implemented")


@pytest.mark.e2e
def test_bank_accounts_config_validation():
    """
    Test that invalid bank_accounts_config.json is rejected.

    This test doesn't need the full flow - just verifies config loading.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        config_dir = Path(tmpdir) / "config"
        config_dir.mkdir()

        # Create invalid config (missing required fields)
        invalid_config = {
            "accounts": [
                {
                    "ynab_account_id": "test-123",
                    "ynab_account_name": "Test Account",
                    "slug": "test_account",
                    # Missing required fields...
                }
            ]
        }

        config_file = config_dir / "bank_accounts_config.json"
        with open(config_file, "w") as f:
            json.dump(invalid_config, f)

        # Try to load config - should fail
        from finances.bank_accounts.models import BankAccountsConfig

        with pytest.raises(KeyError):  # Missing required 'accounts' field
            BankAccountsConfig.from_dict(invalid_config)
