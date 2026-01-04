#!/usr/bin/env python3
"""
E2E Tests for Bank Reconciliation Complete Flow

Tests the complete retrieve → parse → reconcile pipeline end-to-end.
"""

import tempfile
from pathlib import Path

import pytest

from finances.bank_accounts.format_handlers.chase_credit_csv import ChaseCreditCsvHandler
from finances.bank_accounts.format_handlers.registry import FormatHandlerRegistry
from finances.bank_accounts.matching import YnabTransaction
from finances.bank_accounts.models import AccountConfig, BankAccountsConfig, ImportPattern
from finances.bank_accounts.nodes.parse import parse_account_data
from finances.bank_accounts.nodes.reconcile import reconcile_account_data
from finances.bank_accounts.nodes.retrieve import retrieve_account_data
from finances.core import FinancialDate, Money
from finances.core.json_utils import read_json


@pytest.fixture
def tmp_data_dir():
    """Create temporary directory for test data."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def synthetic_bank_csv(tmp_data_dir):
    """
    Create synthetic bank CSV export file.

    Contains 3 transactions:
    - 01/15/2024: SAFEWAY #1234, -$45.67 (will match YNAB)
    - 01/20/2024: AMAZON MKTPL, -$123.45 (no match)
    - 01/25/2024: PAYMENT RECEIVED, +$500.00 (no match)
    """
    source_dir = tmp_data_dir / "source"
    source_dir.mkdir()

    csv_content = """Transaction Date,Post Date,Description,Category,Type,Amount,Memo
01/15/2024,01/15/2024,SAFEWAY #1234,Groceries,Sale,-45.67,Weekly groceries
01/20/2024,01/20/2024,AMAZON MKTPL,Shopping,Sale,-123.45,
01/25/2024,01/25/2024,PAYMENT RECEIVED,Payment/Credit,Payment,500.00,
"""

    csv_file = source_dir / "chase_transactions.csv"
    csv_file.write_text(csv_content)

    return source_dir


@pytest.fixture
def bank_config(synthetic_bank_csv):
    """Create bank accounts configuration."""
    return BankAccountsConfig(
        accounts=(
            AccountConfig(
                ynab_account_id="test-account-123",
                ynab_account_name="Chase Credit",
                slug="chase_credit",
                bank_name="Chase",
                account_type="credit",
                statement_frequency="monthly",
                source_directory=str(synthetic_bank_csv),
                import_patterns=(
                    ImportPattern(
                        pattern="*.csv",
                        format_handler="chase_credit_csv",
                    ),
                ),
                download_instructions="Download from chase.com",
            ),
        )
    )


@pytest.fixture
def ynab_transactions():
    """
    Create synthetic YNAB transactions.

    Only one transaction matches the bank data (SAFEWAY).
    """
    return [
        YnabTransaction(
            date=FinancialDate.from_string("2024-01-15"),
            amount=Money.from_cents(-4567),  # Matches SAFEWAY -$45.67
            payee_name="Safeway",
            memo="Grocery shopping",
            account_id="test-account-123",
        ),
        YnabTransaction(
            date=FinancialDate.from_string("2024-01-10"),
            amount=Money.from_cents(-2099),  # Different date - no match
            payee_name="Target",
            memo="Shopping",
            account_id="test-account-123",
        ),
    ]


def test_complete_bank_reconciliation_flow(tmp_data_dir, bank_config, ynab_transactions):
    """
    Test complete flow: retrieve → parse → reconcile.

    Setup:
    - Synthetic bank export files (CSV format)
    - Config file with account configuration
    - Synthetic YNAB transactions

    Execute:
    - retrieve: Copy files to raw/
    - parse: Create normalized JSON
    - reconcile: Generate operations JSON

    Assert:
    - Operations file exists
    - Contains expected create_transaction ops
    - Balance reconciliation in output
    """
    base_dir = tmp_data_dir / "bank_accounts"

    # Step 1: Retrieve
    retrieve_summary = retrieve_account_data(bank_config, base_dir)

    # Verify retrieve worked
    assert "chase_credit" in retrieve_summary
    assert retrieve_summary["chase_credit"]["files_copied"] == 1
    assert retrieve_summary["chase_credit"]["files_skipped"] == 0

    # Verify file was copied
    raw_file = base_dir / "raw" / "chase_credit" / "chase_transactions.csv"
    assert raw_file.exists()

    # Step 2: Parse
    registry = FormatHandlerRegistry()
    registry.register(ChaseCreditCsvHandler)
    parse_summary = parse_account_data(bank_config, base_dir, registry)

    # Verify parse worked
    assert "chase_credit" in parse_summary
    assert parse_summary["chase_credit"]["transaction_count"] == 3
    assert "2024-01-15 to 2024-01-25" in parse_summary["chase_credit"]["date_range"]

    # Verify normalized JSON was created
    normalized_file = base_dir / "normalized" / "chase_credit.json"
    assert normalized_file.exists()

    # Verify normalized JSON structure
    normalized_data = read_json(normalized_file)
    assert normalized_data["account_id"] == "chase_credit"
    assert normalized_data["account_name"] == "Chase Credit"
    assert normalized_data["account_type"] == "credit"
    assert len(normalized_data["transactions"]) == 3
    assert len(normalized_data["balances"]) == 0  # Credit card CSV has no balances

    # Step 3: Reconcile
    operations_file = reconcile_account_data(bank_config, base_dir, ynab_transactions)

    # Verify operations file exists
    assert operations_file.exists()
    assert operations_file.parent == base_dir / "reconciliation"
    assert operations_file.name.endswith("_reconciliation.json")

    # Read and verify operations
    operations_data = read_json(operations_file)

    # Verify structure
    assert operations_data["version"] == "1.0"
    assert "metadata" in operations_data
    assert "accounts" in operations_data
    assert "summary" in operations_data

    # Verify metadata
    assert operations_data["metadata"]["source_system"] == "bank_reconciliation"
    assert "generated_at" in operations_data["metadata"]

    # Verify accounts
    assert len(operations_data["accounts"]) == 1
    account_data = operations_data["accounts"][0]
    assert account_data["account_id"] == "chase_credit"

    # Verify operations
    operations = account_data["operations"]

    # Should have 2 create_transaction operations (AMAZON and PAYMENT don't match)
    create_ops = [op for op in operations if op["type"] == "create_transaction"]
    assert len(create_ops) == 2

    # Verify create_transaction operations have correct structure
    for create_op in create_ops:
        assert create_op["source"] == "bank"
        assert "transaction" in create_op
        assert "account_id" in create_op
        assert create_op["account_id"] == "test-account-123"

        # Verify transaction has required fields
        tx = create_op["transaction"]
        assert "transaction_date" in tx
        assert "posted_date" in tx
        assert "description" in tx
        assert "amount_milliunits" in tx
        assert "type" in tx
        assert "category" in tx

    # Verify the specific unmatched transactions
    descriptions = [op["transaction"]["description"] for op in create_ops]
    assert "AMAZON MKTPL" in descriptions
    assert "PAYMENT RECEIVED" in descriptions

    # Verify amounts (in milliunits)
    amounts = [op["transaction"]["amount_milliunits"] for op in create_ops]
    assert -123450 in amounts  # AMAZON: -$123.45 in milliunits
    assert 500000 in amounts  # PAYMENT: +$500.00 in milliunits

    # Verify balance reconciliation is included
    assert "balance_reconciliation" in account_data
    balance_recon = account_data["balance_reconciliation"]
    assert balance_recon["account_id"] == "chase_credit"
    assert "points" in balance_recon
    assert "last_reconciled_date" in balance_recon
    assert "first_diverged_date" in balance_recon

    # Verify points is a list (even if empty for credit card with no balance data)
    assert isinstance(balance_recon["points"], list)

    # Verify summary
    summary = operations_data["summary"]
    assert summary["total_operations"] == 2
    assert summary["operations_by_type"]["create_transaction"] == 2
    assert summary["operations_by_type"]["flag_discrepancy"] == 0


def test_complete_flow_with_all_matched_transactions(tmp_data_dir, synthetic_bank_csv):
    """
    Test E2E flow where all bank transactions match YNAB.

    This should result in zero create_transaction operations.
    """
    # Create config
    config = BankAccountsConfig(
        accounts=(
            AccountConfig(
                ynab_account_id="test-account-456",
                ynab_account_name="Chase Credit",
                slug="chase_credit_all_matched",
                bank_name="Chase",
                account_type="credit",
                statement_frequency="monthly",
                source_directory=str(synthetic_bank_csv),
                import_patterns=(
                    ImportPattern(
                        pattern="*.csv",
                        format_handler="chase_credit_csv",
                    ),
                ),
                download_instructions="Download from chase.com",
            ),
        )
    )

    # Create YNAB transactions that match ALL bank transactions
    ynab_txs = [
        YnabTransaction(
            date=FinancialDate.from_string("2024-01-15"),
            amount=Money.from_cents(-4567),  # SAFEWAY
            payee_name="Safeway",
            account_id="test-account-456",
        ),
        YnabTransaction(
            date=FinancialDate.from_string("2024-01-20"),
            amount=Money.from_cents(-12345),  # AMAZON
            payee_name="Amazon",
            account_id="test-account-456",
        ),
        YnabTransaction(
            date=FinancialDate.from_string("2024-01-25"),
            amount=Money.from_cents(50000),  # PAYMENT
            payee_name="Payment Received",
            account_id="test-account-456",
        ),
    ]

    base_dir = tmp_data_dir / "bank_accounts_matched"

    # Execute pipeline
    retrieve_account_data(config, base_dir)
    registry = FormatHandlerRegistry()
    registry.register(ChaseCreditCsvHandler)
    parse_account_data(config, base_dir, registry)
    operations_file = reconcile_account_data(config, base_dir, ynab_txs)

    # Verify operations
    operations_data = read_json(operations_file)

    # Should have ZERO create_transaction operations (all matched)
    account_data = operations_data["accounts"][0]
    create_ops = [op for op in account_data["operations"] if op["type"] == "create_transaction"]
    assert len(create_ops) == 0

    # Verify summary reflects no operations
    assert operations_data["summary"]["total_operations"] == 0
    assert operations_data["summary"]["operations_by_type"]["create_transaction"] == 0


def test_complete_flow_with_ambiguous_matches(tmp_data_dir):
    """
    Test E2E flow with ambiguous matches (multiple YNAB txs on same date/amount).

    This should result in flag_discrepancy operations.
    """
    # Create source directory with one transaction
    source_dir = tmp_data_dir / "source_ambiguous"
    source_dir.mkdir()

    csv_content = """Transaction Date,Post Date,Description,Category,Type,Amount,Memo
01/15/2024,01/15/2024,GROCERY STORE,Groceries,Sale,-50.00,
"""
    csv_file = source_dir / "chase_transactions.csv"
    csv_file.write_text(csv_content)

    # Create config
    config = BankAccountsConfig(
        accounts=(
            AccountConfig(
                ynab_account_id="test-account-789",
                ynab_account_name="Chase Credit",
                slug="chase_credit_ambiguous",
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
                download_instructions="Download from chase.com",
            ),
        )
    )

    # Create MULTIPLE YNAB transactions with SAME date and amount
    # but different descriptions (ambiguous match scenario)
    ynab_txs = [
        YnabTransaction(
            date=FinancialDate.from_string("2024-01-15"),
            amount=Money.from_cents(-5000),
            payee_name="Safeway",
            memo="Store A",
            account_id="test-account-789",
        ),
        YnabTransaction(
            date=FinancialDate.from_string("2024-01-15"),
            amount=Money.from_cents(-5000),
            payee_name="Trader Joes",
            memo="Store B",
            account_id="test-account-789",
        ),
        YnabTransaction(
            date=FinancialDate.from_string("2024-01-15"),
            amount=Money.from_cents(-5000),
            payee_name="Whole Foods",
            memo="Store C",
            account_id="test-account-789",
        ),
    ]

    base_dir = tmp_data_dir / "bank_accounts_ambiguous"

    # Execute pipeline
    retrieve_account_data(config, base_dir)
    registry = FormatHandlerRegistry()
    registry.register(ChaseCreditCsvHandler)
    parse_account_data(config, base_dir, registry)
    operations_file = reconcile_account_data(config, base_dir, ynab_txs)

    # Verify operations
    operations_data = read_json(operations_file)

    # Should have ONE flag_discrepancy operation (ambiguous match)
    account_data = operations_data["accounts"][0]
    flag_ops = [op for op in account_data["operations"] if op["type"] == "flag_discrepancy"]
    assert len(flag_ops) == 1

    # Verify flag_discrepancy structure
    flag_op = flag_ops[0]
    assert flag_op["source"] == "bank"
    assert "transaction" in flag_op
    assert "candidates" in flag_op
    assert "message" in flag_op
    assert flag_op["message"] == "Multiple possible matches - manual review required"

    # Verify candidates list contains all 3 YNAB transactions
    candidates = flag_op["candidates"]
    assert len(candidates) == 3

    # Verify candidate structure
    for candidate in candidates:
        assert "date" in candidate
        assert "amount_milliunits" in candidate
        assert "payee_name" in candidate
        assert candidate["date"] == "2024-01-15"
        assert candidate["amount_milliunits"] == -50000  # -$50.00 in milliunits

    # Verify payee names are included
    payee_names = [c["payee_name"] for c in candidates]
    assert "Safeway" in payee_names
    assert "Trader Joes" in payee_names
    assert "Whole Foods" in payee_names

    # Verify summary reflects flag operation
    assert operations_data["summary"]["total_operations"] == 1
    assert operations_data["summary"]["operations_by_type"]["flag_discrepancy"] == 1
    assert operations_data["summary"]["operations_by_type"]["create_transaction"] == 0


def test_complete_flow_empty_source_directory(tmp_data_dir):
    """
    Test E2E flow with empty source directory.

    Should complete successfully with zero transactions.
    """
    # Create empty source directory
    source_dir = tmp_data_dir / "source_empty"
    source_dir.mkdir()

    # Create config
    config = BankAccountsConfig(
        accounts=(
            AccountConfig(
                ynab_account_id="test-account-empty",
                ynab_account_name="Chase Credit",
                slug="chase_credit_empty",
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
                download_instructions="Download from chase.com",
            ),
        )
    )

    base_dir = tmp_data_dir / "bank_accounts_empty"

    # Execute pipeline
    retrieve_summary = retrieve_account_data(config, base_dir)
    assert retrieve_summary["chase_credit_empty"]["files_copied"] == 0

    registry = FormatHandlerRegistry()
    registry.register(ChaseCreditCsvHandler)
    parse_summary = parse_account_data(config, base_dir, registry)
    assert parse_summary["chase_credit_empty"]["transaction_count"] == 0
    assert parse_summary["chase_credit_empty"]["date_range"] == "no data"

    operations_file = reconcile_account_data(config, base_dir, [])

    # Verify operations
    operations_data = read_json(operations_file)
    assert operations_data["summary"]["total_operations"] == 0
