"""Integration tests for account_data_reconcile flow node."""

import shutil
import tempfile
from pathlib import Path

from finances.bank_accounts.matching import YnabTransaction
from finances.bank_accounts.models import (
    AccountConfig,
    BalancePoint,
    BankAccountsConfig,
    BankTransaction,
    ImportPattern,
)
from finances.bank_accounts.nodes import reconcile_account_data
from finances.core import FinancialDate, Money
from finances.core.json_utils import read_json, write_json


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
            "account_id": "test-checking",
            "account_name": "Test Checking",
            "account_type": "checking",
            "transactions": [tx.to_dict() for tx in bank_txs],
            "balances": [bp.to_dict() for bp in balance_points],
            "data_period": {
                "start_date": "2024-01-01",
                "end_date": "2024-01-03",
            },
        }
        write_json(normalized_dir / "test-checking.json", normalized_data)

        # Create synthetic YNAB transactions (only matches one bank tx)
        ynab_txs = [
            YnabTransaction(
                date=FinancialDate.from_string("2024-01-01"),
                amount=Money.from_cents(-500),
                payee_name="Coffee Shop",
                memo=None,
                account_id="acct_123",
            ),
        ]

        # Run reconcile
        result_file = reconcile_account_data(config, self.base_dir, ynab_txs)

        # Verify output file was created
        assert result_file.exists()
        assert result_file.parent == self.base_dir / "reconciliation"

        # Read and verify operations
        data = read_json(result_file)
        assert data["version"] == "1.0"
        assert "metadata" in data
        assert "accounts" in data

        # Verify account operations
        account_data = data["accounts"][0]
        assert account_data["account_id"] == "test-checking"

        operations = account_data["operations"]
        # Should have 2 create_transaction operations (unmatched bank txs)
        create_ops = [op for op in operations if op["type"] == "create_transaction"]
        assert len(create_ops) == 2

        # Verify operation structure
        assert create_ops[0]["source"] == "bank"
        assert create_ops[0]["account_id"] == "acct_123"
        assert "transaction" in create_ops[0]

        # Verify summary
        assert data["summary"]["total_operations"] == 2
        assert data["summary"]["operations_by_type"]["create_transaction"] == 2

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
            "account_id": "test-checking",
            "account_name": "Test Checking",
            "account_type": "checking",
            "transactions": [tx.to_dict() for tx in bank_txs],
            "balances": [bp.to_dict() for bp in balance_points],
            "data_period": {
                "start_date": "2024-01-01",
                "end_date": "2024-01-02",
            },
        }
        write_json(normalized_dir / "test-checking.json", normalized_data)

        # Create synthetic YNAB transactions that exactly match bank txs
        ynab_txs = [
            YnabTransaction(
                date=FinancialDate.from_string("2024-01-01"),
                amount=Money.from_cents(-500),
                payee_name="Coffee Shop",
                memo=None,
                account_id="acct_123",
            ),
            YnabTransaction(
                date=FinancialDate.from_string("2024-01-02"),
                amount=Money.from_cents(-2500),
                payee_name="Grocery Store",
                memo=None,
                account_id="acct_123",
            ),
        ]

        # Run reconcile
        result_file = reconcile_account_data(config, self.base_dir, ynab_txs)

        # Verify output file was created
        assert result_file.exists()

        # Read and verify operations
        data = read_json(result_file)

        # Verify account operations
        account_data = data["accounts"][0]
        operations = account_data["operations"]

        # Should have NO create_transaction operations (all matched)
        create_ops = [op for op in operations if op["type"] == "create_transaction"]
        assert len(create_ops) == 0

        # Verify summary shows no operations needed
        assert data["summary"]["total_operations"] == 0
        assert data["summary"]["operations_by_type"]["create_transaction"] == 0

        # Verify balance reconciliation exists
        assert "balance_reconciliation" in account_data
        balance_recon = account_data["balance_reconciliation"]
        assert balance_recon["account_id"] == "test-checking"
        assert len(balance_recon["points"]) == 1

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
            "account_id": "test-checking",
            "account_name": "Test Checking",
            "account_type": "checking",
            "transactions": [tx.to_dict() for tx in bank_txs],
            "balances": [bp.to_dict() for bp in balance_points],
            "data_period": {
                "start_date": "2024-01-01",
                "end_date": "2024-01-01",
            },
        }
        write_json(normalized_dir / "test-checking.json", normalized_data)

        # Create YNAB transactions with same date/amount but different descriptions
        ynab_txs = [
            YnabTransaction(
                date=FinancialDate.from_string("2024-01-01"),
                amount=Money.from_cents(-5000),
                payee_name="Chase ATM 123",
                memo="Cash withdrawal",
                account_id="acct_123",
            ),
            YnabTransaction(
                date=FinancialDate.from_string("2024-01-01"),
                amount=Money.from_cents(-5000),
                payee_name="ATM 456",
                memo="Cash",
                account_id="acct_123",
            ),
        ]

        # Run reconcile
        result_file = reconcile_account_data(config, self.base_dir, ynab_txs)

        # Verify output file was created
        assert result_file.exists()

        # Read and verify operations
        data = read_json(result_file)

        # Verify account operations
        account_data = data["accounts"][0]
        operations = account_data["operations"]

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

        # Verify summary
        assert data["summary"]["total_operations"] == 1
        assert data["summary"]["operations_by_type"]["flag_discrepancy"] == 1
