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
from finances.bank_accounts.matching import MatchingYnabTransaction
from finances.bank_accounts.models import AccountConfig, BankAccountsConfig, ImportPattern
from finances.bank_accounts.nodes.parse import parse_account_data
from finances.bank_accounts.nodes.reconcile import reconcile_account_data
from finances.bank_accounts.nodes.retrieve import retrieve_account_data
from finances.bank_accounts.operations import CreateOp, FlagOp
from finances.core import FinancialDate, Money


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
        MatchingYnabTransaction(
            date=FinancialDate.from_string("2024-01-15"),
            amount=Money.from_cents(-4567),  # Matches SAFEWAY -$45.67
            payee_name="Safeway",
            memo="Grocery shopping",
            account_id="test-account-123",
        ),
        MatchingYnabTransaction(
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
    assert retrieve_summary["chase_credit"]["copied"] == 1
    assert retrieve_summary["chase_credit"]["skipped"] == 0

    # Verify file was copied
    raw_file = base_dir / "raw" / "chase_credit" / "chase_transactions.csv"
    assert raw_file.exists()

    # Step 2: Parse
    registry = FormatHandlerRegistry()
    registry.register(ChaseCreditCsvHandler)
    parse_results = parse_account_data(bank_config, base_dir, registry)

    # Verify parse worked - returns dict[str, ParseResult]
    assert "chase_credit" in parse_results
    result = parse_results["chase_credit"]
    assert len(result.transactions) == 3
    assert len(result.balance_points) == 0  # Credit card CSV has no balances

    # Verify date range
    start_date = min(tx.posted_date for tx in result.transactions)
    end_date = max(tx.posted_date for tx in result.transactions)
    assert str(start_date) == "2024-01-15"
    assert str(end_date) == "2024-01-25"

    # Write normalized files for reconcile step (parse node no longer writes files)
    from finances.core.json_utils import write_json

    normalized_dir = base_dir / "normalized"
    normalized_dir.mkdir(parents=True, exist_ok=True)
    for account in bank_config.accounts:
        slug = account.slug
        if slug not in parse_results:
            continue
        result = parse_results[slug]
        data_period = None
        if result.transactions:
            start = min(tx.posted_date for tx in result.transactions)
            end = max(tx.posted_date for tx in result.transactions)
            data_period = {"start_date": str(start), "end_date": str(end)}
        normalized_data = {
            "account_id": slug,
            "account_name": account.ynab_account_name,
            "account_type": account.account_type,
            "data_period": data_period,
            "balance_points": [b.to_dict() for b in result.balance_points],
            "transactions": [tx.to_dict() for tx in result.transactions],
        }
        write_json(normalized_dir / f"2024-01-01_00-00-00_{slug}.json", normalized_data)

    # Step 3: Reconcile
    results = reconcile_account_data(bank_config, base_dir, ynab_transactions)

    # Verify results structure
    assert "chase_credit" in results
    result = results["chase_credit"]

    # Verify operations
    operations = list(result.operations)

    # Should have 2 create_transaction operations (AMAZON and PAYMENT don't match)
    create_ops = [op for op in operations if isinstance(op, CreateOp)]
    assert len(create_ops) == 2

    # Verify create_transaction operations have correct structure
    for create_op in create_ops:
        assert create_op.source == "bank"
        assert create_op.transaction is not None
        assert create_op.account_id == "test-account-123"

        # Verify transaction has required fields
        tx = create_op.transaction
        assert tx.transaction_date is not None or tx.posted_date is not None
        assert tx.description is not None
        assert tx.amount is not None

    # Verify the specific unmatched transactions
    descriptions = [op.transaction.description for op in create_ops]
    assert "AMAZON MKTPL" in descriptions
    assert "PAYMENT RECEIVED" in descriptions

    # Verify amounts (in milliunits)
    amounts = [op.transaction.amount.to_milliunits() for op in create_ops]
    assert -123450 in amounts  # AMAZON: -$123.45 in milliunits
    assert 500000 in amounts  # PAYMENT: +$500.00 in milliunits

    # Verify unmatched transactions
    assert len(result.unmatched_bank_txs) == 2
    assert len(result.unmatched_ynab_txs) == 1  # Target transaction not in bank data

    # Verify balance reconciliation is included
    balance_recon = result.reconciliation
    assert balance_recon.account_id == "chase_credit"
    assert isinstance(balance_recon.points, tuple)


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
        MatchingYnabTransaction(
            date=FinancialDate.from_string("2024-01-15"),
            amount=Money.from_cents(-4567),  # SAFEWAY
            payee_name="Safeway",
            account_id="test-account-456",
        ),
        MatchingYnabTransaction(
            date=FinancialDate.from_string("2024-01-20"),
            amount=Money.from_cents(-12345),  # AMAZON
            payee_name="Amazon",
            account_id="test-account-456",
        ),
        MatchingYnabTransaction(
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
    parse_results = parse_account_data(config, base_dir, registry)

    # Write normalized files for reconcile step
    from finances.core.json_utils import write_json

    normalized_dir = base_dir / "normalized"
    normalized_dir.mkdir(parents=True, exist_ok=True)
    for account in config.accounts:
        slug = account.slug
        if slug not in parse_results:
            continue
        result = parse_results[slug]
        data_period = None
        if result.transactions:
            start = min(tx.posted_date for tx in result.transactions)
            end = max(tx.posted_date for tx in result.transactions)
            data_period = {"start_date": str(start), "end_date": str(end)}
        normalized_data = {
            "account_id": slug,
            "account_name": account.ynab_account_name,
            "account_type": account.account_type,
            "data_period": data_period,
            "balance_points": [b.to_dict() for b in result.balance_points],
            "transactions": [tx.to_dict() for tx in result.transactions],
        }
        write_json(normalized_dir / f"2024-01-01_00-00-00_{slug}.json", normalized_data)

    results = reconcile_account_data(config, base_dir, ynab_txs)

    # Verify results structure
    assert "chase_credit_all_matched" in results
    result = results["chase_credit_all_matched"]

    # Should have ZERO create_transaction operations (all matched)
    operations = list(result.operations)
    create_ops = [op for op in operations if isinstance(op, CreateOp)]
    assert len(create_ops) == 0

    # Verify no unmatched transactions
    assert len(result.unmatched_bank_txs) == 0
    assert len(result.unmatched_ynab_txs) == 0


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
        MatchingYnabTransaction(
            date=FinancialDate.from_string("2024-01-15"),
            amount=Money.from_cents(-5000),
            payee_name="Safeway",
            memo="Store A",
            account_id="test-account-789",
        ),
        MatchingYnabTransaction(
            date=FinancialDate.from_string("2024-01-15"),
            amount=Money.from_cents(-5000),
            payee_name="Trader Joes",
            memo="Store B",
            account_id="test-account-789",
        ),
        MatchingYnabTransaction(
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
    parse_results = parse_account_data(config, base_dir, registry)

    # Write normalized files for reconcile step
    from finances.core.json_utils import write_json

    normalized_dir = base_dir / "normalized"
    normalized_dir.mkdir(parents=True, exist_ok=True)
    for account in config.accounts:
        slug = account.slug
        if slug not in parse_results:
            continue
        result = parse_results[slug]
        data_period = None
        if result.transactions:
            start = min(tx.posted_date for tx in result.transactions)
            end = max(tx.posted_date for tx in result.transactions)
            data_period = {"start_date": str(start), "end_date": str(end)}
        normalized_data = {
            "account_id": slug,
            "account_name": account.ynab_account_name,
            "account_type": account.account_type,
            "data_period": data_period,
            "balance_points": [b.to_dict() for b in result.balance_points],
            "transactions": [tx.to_dict() for tx in result.transactions],
        }
        write_json(normalized_dir / f"2024-01-01_00-00-00_{slug}.json", normalized_data)

    results = reconcile_account_data(config, base_dir, ynab_txs)

    # Verify results structure
    assert "chase_credit_ambiguous" in results
    result = results["chase_credit_ambiguous"]

    # Should have ONE flag_discrepancy operation (ambiguous match)
    operations = list(result.operations)
    flag_ops = [op for op in operations if isinstance(op, FlagOp)]
    assert len(flag_ops) == 1

    # Verify flag_discrepancy structure
    flag_op = flag_ops[0]
    assert flag_op.source == "bank"
    assert flag_op.transaction is not None
    assert flag_op.candidates is not None
    assert flag_op.message == "Multiple possible matches - manual review required"

    # Verify candidates list contains all 3 YNAB transactions
    candidates = flag_op.candidates
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

    # Ambiguous bank txs count as unmatched for balance adjustment (they generated a FlagOp
    # but the bank recorded the transaction, so it must be reflected in the balance).
    assert len(result.unmatched_bank_txs) == 1
    assert len(result.unmatched_ynab_txs) == 3  # All candidates remain unmatched


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
    assert retrieve_summary["chase_credit_empty"]["copied"] == 0

    registry = FormatHandlerRegistry()
    registry.register(ChaseCreditCsvHandler)
    parse_results = parse_account_data(config, base_dir, registry)
    result = parse_results["chase_credit_empty"]
    assert len(result.transactions) == 0
    assert len(result.balance_points) == 0

    # Write normalized files for reconcile step
    from finances.core.json_utils import write_json

    normalized_dir = base_dir / "normalized"
    normalized_dir.mkdir(parents=True, exist_ok=True)
    for account in config.accounts:
        slug = account.slug
        if slug not in parse_results:
            continue
        result = parse_results[slug]
        data_period = None
        if result.transactions:
            start = min(tx.posted_date for tx in result.transactions)
            end = max(tx.posted_date for tx in result.transactions)
            data_period = {"start_date": str(start), "end_date": str(end)}
        normalized_data = {
            "account_id": slug,
            "account_name": account.ynab_account_name,
            "account_type": account.account_type,
            "data_period": data_period,
            "balance_points": [b.to_dict() for b in result.balance_points],
            "transactions": [tx.to_dict() for tx in result.transactions],
        }
        write_json(normalized_dir / f"2024-01-01_00-00-00_{slug}.json", normalized_data)

    results = reconcile_account_data(config, base_dir, [])

    # Accounts with no transactions and no balance points are skipped in reconciliation
    assert "chase_credit_empty" not in results


def test_reconcile_to_apply_round_trip(tmp_data_dir):
    """
    E2E round-trip: reconcile ops file → apply → verify apply log entries.

    Validates that an operations JSON file (as produced by the reconcile node) is
    correctly consumed by apply_reconciliation_operations, producing the expected
    NDJSON log entries for a two-account scenario.

    Uses synthetic data only; subprocess.run is mocked so no real YNAB calls occur.
    """
    import json
    from unittest.mock import patch

    from finances.bank_accounts.nodes.apply import apply_reconciliation_operations
    from finances.core.json_utils import write_json

    # --- synthetic operations file (two accounts, mixed operation types) ---
    ops = {
        "reconciled_at": "2024-03-01T12:00:00",
        "accounts": {
            "chase-checking": {
                "account_id": "acct-chase-checking",
                "operations": [
                    {
                        "type": "create_transaction",
                        "account_id": "acct-chase-checking",
                        "transaction": {
                            "posted_date": "2024-03-01",
                            "amount_milliunits": -12990,
                            "description": "SPOTIFY USA 8888812345 NY USA",
                            "merchant": "Spotify",
                        },
                    },
                    {
                        "type": "create_transaction",
                        "account_id": "acct-chase-checking",
                        "transaction": {
                            "posted_date": "2024-03-02",
                            "amount_milliunits": -6500,
                            "description": "STARBUCKS UTAH AVE WA USA",
                            "merchant": "Starbucks",
                        },
                    },
                ],
            },
            "apple-card": {
                "account_id": "acct-apple-card",
                "operations": [
                    {
                        "type": "flag_discrepancy",
                        "account_id": "acct-apple-card",
                        "transaction": {
                            "posted_date": "2024-03-05",
                            "amount_milliunits": -25000,
                            "description": "GROCERY STORE #1234",
                            "merchant": "Safeway",
                        },
                        "candidates": [
                            {
                                "payee_name": "Safeway",
                                "date": "2024-03-05",
                                "amount_milliunits": -25000,
                            },
                            {
                                "payee_name": "Target",
                                "date": "2024-03-05",
                                "amount_milliunits": -25000,
                            },
                        ],
                        "message": "Multiple possible matches - manual review required",
                    },
                ],
            },
        },
    }

    ops_file = tmp_data_dir / "ops.json"
    write_json(ops_file, ops)

    apply_log = tmp_data_dir / "apply_log.ndjson"
    delete_log = tmp_data_dir / "delete_log.ndjson"

    from finances.bank_accounts.models import BankAccountsConfig

    # No account entries needed in config: apply falls back to dict order for unknown slugs
    config = BankAccountsConfig(accounts=())

    # Input sequence:
    #   1. "y" — process chase-checking account
    #   2. "y" — apply 2024-03-01 create batch (Spotify)
    #   3. "y" — apply 2024-03-02 create batch (Starbucks)
    #   4. "y" — process apple-card account
    #   5. "a" — acknowledge 2024-03-05 flag batch
    with (
        patch("finances.bank_accounts.nodes.apply.subprocess.run") as mock_run,
        patch("builtins.input", side_effect=["y", "y", "y", "y", "a"]),
    ):
        mock_run.return_value.returncode = 0
        mock_run.return_value.stdout = ""
        mock_run.return_value.stderr = ""
        counts = apply_reconciliation_operations(ops_file, apply_log, delete_log, config)

    # --- verify counts ---
    assert counts["applied"] == 2  # two create_transactions applied
    assert counts["acknowledged"] == 1  # one flag_discrepancy acknowledged
    assert counts["skipped"] == 0
    assert counts["failed"] == 0

    # --- verify apply log entries ---
    log_entries = [json.loads(line) for line in apply_log.read_text().strip().splitlines()]
    assert len(log_entries) == 3

    applied_entries = [e for e in log_entries if e["action"] == "applied"]
    ack_entries = [e for e in log_entries if e["action"] == "acknowledged"]
    assert len(applied_entries) == 2
    assert len(ack_entries) == 1

    # Creates logged in chronological order across both accounts
    posted_dates = [e["posted_date"] for e in applied_entries]
    assert sorted(posted_dates) == posted_dates

    # Flag entry has expected candidate names
    ack = ack_entries[0]
    assert set(ack["candidates"]) == {"Safeway", "Target"}
    assert ack["account_slug"] == "apple-card"
