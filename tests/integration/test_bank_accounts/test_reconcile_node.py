"""Integration tests for account_data_reconcile flow node."""

import shutil
import tempfile
from pathlib import Path

from finances.bank_accounts.matching import MatchingYnabTransaction
from finances.bank_accounts.models import (
    AccountConfig,
    BalancePoint,
    BankAccountsConfig,
    BankTransaction,
    ImportPattern,
)
from finances.bank_accounts.nodes import reconcile_account_data
from finances.core import FinancialDate, Money
from finances.core.json_utils import write_json


class TestReconcileNode:
    """Integration tests for reconcile_account_data function."""

    def setup_method(self) -> None:
        """Create temporary directories for each test."""
        self.temp_dir = Path(tempfile.mkdtemp())
        self.base_dir = self.temp_dir / "base"
        self.base_dir.mkdir()

    def teardown_method(self) -> None:
        """Clean up temporary directories."""
        shutil.rmtree(self.temp_dir)

    def test_reconcile_generates_operations(self) -> None:
        """Test reconcile node generates operations for unmatched transactions."""
        # Create config
        config = BankAccountsConfig(
            accounts=(
                AccountConfig(
                    ynab_account_id="acct_123",
                    ynab_account_name="Test Checking",
                    slug="test-checking",
                    bank_name="Test Bank",
                    account_type="checking",
                    statement_frequency="monthly",
                    source_directory="/tmp/source",  # noqa: S108
                    download_instructions="Test instructions",
                    import_patterns=(ImportPattern(pattern="*.csv", format_handler="test_csv"),),
                ),
            )
        )

        # Create normalized bank data (output from parse node)
        normalized_dir = self.base_dir / "normalized"
        normalized_dir.mkdir()

        bank_txs = [
            BankTransaction(
                posted_date=FinancialDate.from_string("2024-01-01"),
                description="Coffee Shop",
                amount=Money.from_cents(-500),
            ),
            BankTransaction(
                posted_date=FinancialDate.from_string("2024-01-02"),
                description="Grocery Store",
                amount=Money.from_cents(-2500),
            ),
            BankTransaction(
                posted_date=FinancialDate.from_string("2024-01-03"),
                description="Paycheck",
                amount=Money.from_cents(100000),
            ),
        ]

        balance_points = [
            BalancePoint(
                date=FinancialDate.from_string("2024-01-03"),
                amount=Money.from_cents(97000),
            ),
        ]

        normalized_data = {
            "account_slug": "test-checking",
            "parsed_at": "2024-01-08T14:23:45",
            "transactions": [tx.to_dict() for tx in bank_txs],
            "balance_points": [bp.to_dict() for bp in balance_points],
            "statement_date": "2024-01-03",
        }
        # Write timestamped file (Pattern C)
        write_json(normalized_dir / "2024-01-08_14-23-45_test-checking.json", normalized_data)

        # Create synthetic YNAB transactions (only matches one bank tx)
        ynab_txs = [
            MatchingYnabTransaction(
                date=FinancialDate.from_string("2024-01-01"),
                amount=Money.from_cents(-500),
                payee_name="Coffee Shop",
                memo=None,
                account_id="acct_123",
            ),
        ]

        # Run reconcile
        results = reconcile_account_data(config, self.base_dir, ynab_txs)

        # Verify results structure
        assert "test-checking" in results
        result = results["test-checking"]

        # Verify operations
        operations = list(result.operations)
        # Should have 2 create_transaction operations (unmatched bank txs)
        create_ops = [op for op in operations if op["type"] == "create_transaction"]
        assert len(create_ops) == 2

        # Verify operation structure
        assert create_ops[0]["source"] == "bank"
        assert create_ops[0]["account_id"] == "acct_123"
        assert "transaction" in create_ops[0]

        # Verify unmatched transactions
        assert len(result.unmatched_bank_txs) == 2
        assert len(result.unmatched_ynab_txs) == 0

        # Verify balance reconciliation exists
        assert result.reconciliation.account_id == "test-checking"

    def test_reconcile_with_matched_transactions(self) -> None:
        """Test reconcile when transactions match exactly."""
        # Create config
        config = BankAccountsConfig(
            accounts=(
                AccountConfig(
                    ynab_account_id="acct_123",
                    ynab_account_name="Test Checking",
                    slug="test-checking",
                    bank_name="Test Bank",
                    account_type="checking",
                    statement_frequency="monthly",
                    source_directory="/tmp/source",  # noqa: S108
                    download_instructions="Test instructions",
                    import_patterns=(ImportPattern(pattern="*.csv", format_handler="test_csv"),),
                ),
            )
        )

        # Create normalized bank data
        normalized_dir = self.base_dir / "normalized"
        normalized_dir.mkdir()

        bank_txs = [
            BankTransaction(
                posted_date=FinancialDate.from_string("2024-01-01"),
                description="Coffee Shop",
                amount=Money.from_cents(-500),
            ),
            BankTransaction(
                posted_date=FinancialDate.from_string("2024-01-02"),
                description="Grocery Store",
                amount=Money.from_cents(-2500),
            ),
        ]

        balance_points = [
            BalancePoint(
                date=FinancialDate.from_string("2024-01-02"),
                amount=Money.from_cents(-3000),
            ),
        ]

        normalized_data = {
            "account_slug": "test-checking",
            "parsed_at": "2024-01-08T14:23:45",
            "transactions": [tx.to_dict() for tx in bank_txs],
            "balance_points": [bp.to_dict() for bp in balance_points],
            "statement_date": "2024-01-02",
        }
        # Write timestamped file (Pattern C)
        write_json(normalized_dir / "2024-01-08_14-23-45_test-checking.json", normalized_data)

        # Create synthetic YNAB transactions that exactly match bank txs
        ynab_txs = [
            MatchingYnabTransaction(
                date=FinancialDate.from_string("2024-01-01"),
                amount=Money.from_cents(-500),
                payee_name="Coffee Shop",
                memo=None,
                account_id="acct_123",
            ),
            MatchingYnabTransaction(
                date=FinancialDate.from_string("2024-01-02"),
                amount=Money.from_cents(-2500),
                payee_name="Grocery Store",
                memo=None,
                account_id="acct_123",
            ),
        ]

        # Run reconcile
        results = reconcile_account_data(config, self.base_dir, ynab_txs)

        # Verify results structure
        assert "test-checking" in results
        result = results["test-checking"]

        # Verify operations
        operations = list(result.operations)

        # Should have NO create_transaction operations (all matched)
        create_ops = [op for op in operations if op["type"] == "create_transaction"]
        assert len(create_ops) == 0

        # Verify unmatched transactions
        assert len(result.unmatched_bank_txs) == 0
        assert len(result.unmatched_ynab_txs) == 0

        # Verify balance reconciliation exists
        assert result.reconciliation.account_id == "test-checking"
        assert len(result.reconciliation.points) == 1

    def test_reconcile_with_ambiguous_matches(self) -> None:
        """Test reconcile generates flag_discrepancy for ambiguous matches."""
        # Create config
        config = BankAccountsConfig(
            accounts=(
                AccountConfig(
                    ynab_account_id="acct_123",
                    ynab_account_name="Test Checking",
                    slug="test-checking",
                    bank_name="Test Bank",
                    account_type="checking",
                    statement_frequency="monthly",
                    source_directory="/tmp/source",  # noqa: S108
                    download_instructions="Test instructions",
                    import_patterns=(ImportPattern(pattern="*.csv", format_handler="test_csv"),),
                ),
            )
        )

        # Create normalized bank data
        normalized_dir = self.base_dir / "normalized"
        normalized_dir.mkdir()

        bank_txs = [
            BankTransaction(
                posted_date=FinancialDate.from_string("2024-01-01"),
                description="ATM Withdrawal",
                amount=Money.from_cents(-5000),
            ),
        ]

        balance_points = [
            BalancePoint(
                date=FinancialDate.from_string("2024-01-01"),
                amount=Money.from_cents(-5000),
            ),
        ]

        normalized_data = {
            "account_slug": "test-checking",
            "parsed_at": "2024-01-08T14:23:45",
            "transactions": [tx.to_dict() for tx in bank_txs],
            "balance_points": [bp.to_dict() for bp in balance_points],
            "statement_date": "2024-01-01",
        }
        # Write timestamped file (Pattern C)
        write_json(normalized_dir / "2024-01-08_14-23-45_test-checking.json", normalized_data)

        # Create YNAB transactions with same date/amount but different descriptions
        ynab_txs = [
            MatchingYnabTransaction(
                date=FinancialDate.from_string("2024-01-01"),
                amount=Money.from_cents(-5000),
                payee_name="Chase ATM 123",
                memo="Cash withdrawal",
                account_id="acct_123",
            ),
            MatchingYnabTransaction(
                date=FinancialDate.from_string("2024-01-01"),
                amount=Money.from_cents(-5000),
                payee_name="ATM 456",
                memo="Cash",
                account_id="acct_123",
            ),
        ]

        # Run reconcile
        results = reconcile_account_data(config, self.base_dir, ynab_txs)

        # Verify results structure
        assert "test-checking" in results
        result = results["test-checking"]

        # Verify operations
        operations = list(result.operations)

        # Should have 1 flag_discrepancy operation (ambiguous match)
        flag_ops = [op for op in operations if op["type"] == "flag_discrepancy"]
        assert len(flag_ops) == 1

        # Verify operation structure
        assert flag_ops[0]["source"] == "bank"
        assert "transaction" in flag_ops[0]
        assert "candidates" in flag_ops[0]
        assert len(flag_ops[0]["candidates"]) == 2
        assert "message" in flag_ops[0]
        assert "manual review" in flag_ops[0]["message"].lower()

    def test_reconcile_generates_delete_for_orphaned_ynab_tx(self) -> None:
        """Orphaned YNAB txs inside coverage generate delete ops; those outside do not."""
        config = BankAccountsConfig(
            accounts=(
                AccountConfig(
                    ynab_account_id="acct_123",
                    ynab_account_name="Test Checking",
                    slug="test-checking",
                    bank_name="Test Bank",
                    account_type="checking",
                    statement_frequency="monthly",
                    source_directory="/tmp/source",  # noqa: S108
                    download_instructions="Test instructions",
                    import_patterns=(ImportPattern(pattern="*.csv", format_handler="test_csv"),),
                ),
            )
        )

        normalized_dir = self.base_dir / "normalized"
        normalized_dir.mkdir()

        # Bank data covers Jan and Mar (two intervals; Feb gap)
        bank_txs = [
            BankTransaction(
                posted_date=FinancialDate.from_string("2024-01-15"),
                description="Matched Jan",
                amount=Money.from_cents(-500),
            ),
        ]

        normalized_data = {
            "account_slug": "test-checking",
            "parsed_at": "2024-04-01T10:00:00",
            "transactions": [tx.to_dict() for tx in bank_txs],
            "balance_points": [],
            "coverage_intervals": [
                {"start_date": "2024-01-01", "end_date": "2024-01-31"},
                {"start_date": "2024-03-01", "end_date": "2024-03-31"},
            ],
        }
        write_json(normalized_dir / "2024-04-01_10-00-00_test-checking.json", normalized_data)

        # YNAB transactions:
        #   - tx_jan: Jan 15, matches bank tx (gets claimed, not orphaned)
        #   - tx_feb: Feb 10, in gap between intervals — NOT flagged
        #   - tx_mar: Mar 20, inside Mar interval, unmatched — SHOULD be flagged for delete
        #   - tx_dec: Dec 2023, before window — NOT flagged
        ynab_txs = [
            MatchingYnabTransaction(
                date=FinancialDate.from_string("2024-01-15"),
                amount=Money.from_cents(-500),
                payee_name="Matched Jan",
                account_id="acct_123",
                id="ynab-jan-id",
            ),
            MatchingYnabTransaction(
                date=FinancialDate.from_string("2024-02-10"),
                amount=Money.from_cents(-999),
                payee_name="Feb Orphan (in gap)",
                account_id="acct_123",
                id="ynab-feb-id",
            ),
            MatchingYnabTransaction(
                date=FinancialDate.from_string("2024-03-20"),
                amount=Money.from_cents(-1234),
                payee_name="Mar Orphan",
                account_id="acct_123",
                id="ynab-mar-id",
            ),
            MatchingYnabTransaction(
                date=FinancialDate.from_string("2023-12-01"),
                amount=Money.from_cents(-777),
                payee_name="Dec 2023 (before window)",
                account_id="acct_123",
                id="ynab-dec-id",
            ),
        ]

        raw_ynab_by_id = {
            "ynab-jan-id": {"id": "ynab-jan-id", "date": "2024-01-15", "amount": -5000},
            "ynab-feb-id": {"id": "ynab-feb-id", "date": "2024-02-10", "amount": -9990},
            "ynab-mar-id": {"id": "ynab-mar-id", "date": "2024-03-20", "amount": -12340},
            "ynab-dec-id": {"id": "ynab-dec-id", "date": "2023-12-01", "amount": -7770},
        }

        results = reconcile_account_data(config, self.base_dir, ynab_txs, raw_ynab_by_id)

        assert "test-checking" in results
        result = results["test-checking"]

        delete_ops = [op for op in result.operations if op["type"] == "delete_ynab_transaction"]
        assert len(delete_ops) == 1, f"Expected 1 delete op, got {len(delete_ops)}: {delete_ops}"
        assert delete_ops[0]["transaction"]["id"] == "ynab-mar-id"
