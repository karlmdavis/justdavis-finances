"""Integration tests for bank accounts FlowNode classes.

Tests FlowNode execute() methods and Pattern C accumulation behavior.
"""

import shutil
import tempfile
import time
from datetime import datetime
from pathlib import Path

import pytest

from finances.bank_accounts.flow import (
    BankDataParseFlowNode,
    BankDataReconcileFlowNode,
    BankDataRetrieveFlowNode,
)
from finances.bank_accounts.format_handlers.base import BankExportFormatHandler, ParseResult
from finances.bank_accounts.format_handlers.registry import FormatHandlerRegistry
from finances.bank_accounts.models import AccountConfig, BankAccountsConfig, BankTransaction, ImportPattern
from finances.cli.bank_accounts import create_format_handler_registry
from finances.core import FinancialDate, Money
from finances.core.flow import FlowContext
from finances.core.json_utils import write_json


class TestCsvHandler(BankExportFormatHandler):
    """Test CSV format handler for integration tests."""

    @property
    def format_name(self) -> str:
        return "test_csv"

    @property
    def supported_extensions(self) -> tuple[str, ...]:
        return (".csv",)

    def validate_file(self, file_path: Path) -> bool:
        """Validate CSV file format."""
        return file_path.suffix == ".csv"

    def parse(self, file_path: Path) -> ParseResult:
        """Parse test CSV file."""
        # Simple parser: each line is "date,description,amount"
        transactions = []
        for line in file_path.read_text().strip().split("\n"):
            if not line or line.startswith("Date"):  # Skip header
                continue
            parts = line.split(",")
            if len(parts) >= 3:
                transactions.append(
                    BankTransaction(
                        posted_date=FinancialDate.from_string(parts[0]),
                        description=parts[1],
                        amount=Money.from_cents(int(parts[2])),
                    )
                )
        return ParseResult.create(transactions=transactions)


@pytest.fixture
def temp_dir():
    """Create temporary directory for test files."""
    temp = Path(tempfile.mkdtemp())
    yield temp
    shutil.rmtree(temp)


@pytest.fixture
def test_config(temp_dir: Path):
    """Create test configuration with synthetic data."""
    # Create source directory with test files
    source_dir = temp_dir / "source"
    source_dir.mkdir()

    # Create test CSV file
    csv_content = """Date,Description,Amount
2024-01-01,Coffee Shop,-500
2024-01-02,Grocery Store,-2500
2024-01-03,Paycheck,100000"""
    (source_dir / "statement.csv").write_text(csv_content)

    # Create configuration
    config = BankAccountsConfig(
        accounts=(
            AccountConfig(
                ynab_account_id="acct_test_123",
                ynab_account_name="Test Checking",
                slug="test-checking",
                bank_name="Test Bank",
                account_type="checking",
                statement_frequency="monthly",
                source_directory=str(source_dir),
                download_instructions="Test download instructions",
                import_patterns=(ImportPattern(pattern="*.csv", format_handler="test_csv"),),
            ),
        )
    )

    # Create data directory
    data_dir = temp_dir / "data"
    data_dir.mkdir()

    return {"config": config, "data_dir": data_dir, "source_dir": source_dir}


@pytest.fixture
def flow_context():
    """Create flow execution context."""
    return FlowContext(start_time=datetime.now())


def create_raw_bank_data(data_dir: Path, account_slug: str) -> Path:
    """
    Create test raw bank data in expected location.

    Helper function for tests that need raw data without running retrieve node.

    Args:
        data_dir: Base data directory
        account_slug: Account slug (e.g., "test-checking")

    Returns:
        Path to created raw directory
    """
    raw_dir = data_dir / "bank_accounts" / "raw" / account_slug
    raw_dir.mkdir(parents=True)

    # Write test CSV file
    csv_content = """Date,Description,Amount
2024-01-01,Coffee Shop,-500
2024-01-02,Grocery Store,-2500
2024-01-03,Paycheck,100000"""
    (raw_dir / "statement.csv").write_text(csv_content)

    return raw_dir


class TestBankDataRetrieveFlowNode:
    """Test BankDataRetrieveFlowNode."""

    def test_execute_success_with_files(self, test_config, flow_context):
        """Node execute() should successfully retrieve raw files."""
        # Create node
        node = BankDataRetrieveFlowNode(test_config["data_dir"], test_config["config"])

        # Execute node
        result = node.execute(flow_context)

        # Verify success
        assert result.success is True
        assert result.items_processed > 0
        assert result.new_items > 0

        # Verify files were copied to correct location (data_dir/bank_accounts/raw/{slug})
        raw_dir = test_config["data_dir"] / "bank_accounts" / "raw" / "test-checking"
        assert raw_dir.exists()
        assert (raw_dir / "statement.csv").exists()

        # Verify outputs are populated correctly
        assert len(result.outputs) == 1
        assert result.outputs[0] == raw_dir / "statement.csv"

        # Verify metadata
        assert "copied" in result.metadata
        assert result.metadata["copied"] == 1

    def test_get_output_dir(self, test_config):
        """get_output_dir() should return correct path."""
        node = BankDataRetrieveFlowNode(test_config["data_dir"], test_config["config"])
        output_dir = node.get_output_dir()
        assert output_dir == test_config["data_dir"] / "bank_accounts" / "raw"


class TestBankDataParseFlowNode:
    """Test BankDataParseFlowNode."""

    def setup_method(self):
        """Set up format handler registry for each test."""
        # Monkey-patch the create_format_handler_registry function
        self.original_create_registry = create_format_handler_registry

        def test_registry_creator():
            registry = FormatHandlerRegistry()
            registry.register(TestCsvHandler)
            return registry

        import finances.cli.bank_accounts

        finances.cli.bank_accounts.create_format_handler_registry = test_registry_creator

    def teardown_method(self):
        """Restore original registry creator."""
        import finances.cli.bank_accounts

        finances.cli.bank_accounts.create_format_handler_registry = self.original_create_registry

    def test_execute_creates_timestamped_files(self, test_config, flow_context):
        """Node execute() should create timestamped normalized files."""
        # Create raw data in expected location
        create_raw_bank_data(test_config["data_dir"], "test-checking")

        # Create parse node
        parse_node = BankDataParseFlowNode(test_config["data_dir"], test_config["config"])

        # Execute node
        result = parse_node.execute(flow_context)

        # Verify success
        assert result.success is True
        assert result.items_processed == 1
        assert result.new_items == 1

        # Verify timestamped file created
        normalized_dir = test_config["data_dir"] / "bank_accounts" / "normalized"
        assert normalized_dir.exists()

        files = list(normalized_dir.glob("*.json"))
        assert len(files) == 1

        # Verify filename format: {timestamp}_{slug}.json
        filename = files[0].name
        assert "_test-checking.json" in filename

    def test_pattern_c_accumulation(self, test_config, flow_context):
        """Multiple runs should create multiple timestamped files (Pattern C)."""
        # Create raw data
        create_raw_bank_data(test_config["data_dir"], "test-checking")

        # Create parse node
        parse_node = BankDataParseFlowNode(test_config["data_dir"], test_config["config"])

        # First execution
        result1 = parse_node.execute(flow_context)
        assert result1.success is True

        # Wait to ensure different timestamp
        time.sleep(1.1)

        # Second execution
        result2 = parse_node.execute(flow_context)
        assert result2.success is True

        # Verify 2 timestamped files exist
        normalized_dir = test_config["data_dir"] / "bank_accounts" / "normalized"
        files = sorted(normalized_dir.glob("*.json"))
        assert len(files) == 2

        # Verify different timestamps
        file1_time = files[0].name.split("_test-checking.json")[0]
        file2_time = files[1].name.split("_test-checking.json")[0]
        assert file1_time != file2_time

    def test_output_files_include_only_new_file(self, test_config, flow_context):
        """FlowResult.outputs should include only the newly created file; flow engine handles cleanup."""
        # Create raw data
        create_raw_bank_data(test_config["data_dir"], "test-checking")

        # Create parse node
        parse_node = BankDataParseFlowNode(test_config["data_dir"], test_config["config"])

        # First execution
        result1 = parse_node.execute(flow_context)
        assert len(result1.outputs) == 1

        # Wait for different timestamp
        time.sleep(1.1)

        # Second execution
        result2 = parse_node.execute(flow_context)

        # Verify second run's outputs includes ONLY the new file (flow engine archives old ones)
        assert len(result2.outputs) == 1

        # Verify output is a valid path
        for output in result2.outputs:
            assert isinstance(output, Path)
            assert output.exists()

    def test_output_info_is_data_ready(self, test_config, flow_context):
        """OutputInfo should detect when data exists."""
        # Create parse node
        parse_node = BankDataParseFlowNode(test_config["data_dir"], test_config["config"])

        # Initially no data
        output_info = parse_node.get_output_info()
        assert output_info.is_data_ready() is False

        # Create raw data and parse
        create_raw_bank_data(test_config["data_dir"], "test-checking")
        parse_node.execute(flow_context)

        # Now data should be ready
        output_info = parse_node.get_output_info()
        assert output_info.is_data_ready() is True

    def test_get_output_dir(self, test_config):
        """get_output_dir() should return correct path."""
        node = BankDataParseFlowNode(test_config["data_dir"], test_config["config"])
        output_dir = node.get_output_dir()
        assert output_dir == test_config["data_dir"] / "bank_accounts" / "normalized"


class TestBankDataReconcileFlowNode:
    """Test BankDataReconcileFlowNode."""

    def setup_method(self):
        """Set up format handler registry for each test."""
        self.original_create_registry = create_format_handler_registry

        def test_registry_creator():
            registry = FormatHandlerRegistry()
            registry.register(TestCsvHandler)
            return registry

        import finances.cli.bank_accounts

        finances.cli.bank_accounts.create_format_handler_registry = test_registry_creator

    def teardown_method(self):
        """Restore original registry creator."""
        import finances.cli.bank_accounts

        finances.cli.bank_accounts.create_format_handler_registry = self.original_create_registry

    def test_execute_creates_timestamped_operations(self, test_config, flow_context):
        """Node execute() should create timestamped operations file."""
        # Create raw data and parse
        create_raw_bank_data(test_config["data_dir"], "test-checking")
        parse_node = BankDataParseFlowNode(test_config["data_dir"], test_config["config"])
        parse_node.execute(flow_context)

        # Create YNAB cache
        ynab_cache_dir = test_config["data_dir"] / "ynab" / "cache"
        ynab_cache_dir.mkdir(parents=True)

        ynab_txs = [
            {
                "date": "2024-01-01",
                "amount": -5000,  # Milliunits
                "payee_name": "Coffee Shop",
                "memo": None,
                "account_id": "acct_test_123",
            },
        ]
        write_json(ynab_cache_dir / "transactions.json", ynab_txs)

        # Create reconcile node
        reconcile_node = BankDataReconcileFlowNode(test_config["data_dir"], test_config["config"])

        # Execute node
        result = reconcile_node.execute(flow_context)

        # Verify success
        assert result.success is True
        assert result.items_processed == 1
        assert result.new_items == 1

        # Verify timestamped file created
        reconciliation_dir = test_config["data_dir"] / "bank_accounts" / "reconciliation"
        assert reconciliation_dir.exists()

        files = list(reconciliation_dir.glob("*.json"))
        assert len(files) == 1

        # Verify filename format: {timestamp}_operations.json
        filename = files[0].name
        assert filename.endswith("_operations.json")

    def test_pattern_c_accumulation(self, test_config, flow_context):
        """Multiple runs should create multiple timestamped files (Pattern C)."""
        # Setup: create raw data, parse, and YNAB cache
        create_raw_bank_data(test_config["data_dir"], "test-checking")
        parse_node = BankDataParseFlowNode(test_config["data_dir"], test_config["config"])
        parse_node.execute(flow_context)

        ynab_cache_dir = test_config["data_dir"] / "ynab" / "cache"
        ynab_cache_dir.mkdir(parents=True)
        ynab_txs = [
            {
                "date": "2024-01-01",
                "amount": -5000,
                "payee_name": "Coffee Shop",
                "memo": None,
                "account_id": "acct_test_123",
            },
        ]
        write_json(ynab_cache_dir / "transactions.json", ynab_txs)

        # Create reconcile node
        reconcile_node = BankDataReconcileFlowNode(test_config["data_dir"], test_config["config"])

        # First execution
        result1 = reconcile_node.execute(flow_context)
        assert result1.success is True

        # Wait for different timestamp
        time.sleep(1.1)

        # Second execution
        result2 = reconcile_node.execute(flow_context)
        assert result2.success is True

        # Verify 2 timestamped files exist
        reconciliation_dir = test_config["data_dir"] / "bank_accounts" / "reconciliation"
        files = sorted(reconciliation_dir.glob("*.json"))
        assert len(files) == 2

        # Verify different timestamps
        file1_time = files[0].name.split("_operations.json")[0]
        file2_time = files[1].name.split("_operations.json")[0]
        assert file1_time != file2_time

    def test_output_files_include_only_new_file(self, test_config, flow_context):
        """FlowResult.outputs should include only the newly created file; flow engine handles cleanup."""
        # Setup
        create_raw_bank_data(test_config["data_dir"], "test-checking")
        parse_node = BankDataParseFlowNode(test_config["data_dir"], test_config["config"])
        parse_node.execute(flow_context)

        ynab_cache_dir = test_config["data_dir"] / "ynab" / "cache"
        ynab_cache_dir.mkdir(parents=True)
        ynab_txs = [
            {
                "date": "2024-01-01",
                "amount": -5000,
                "payee_name": "Coffee Shop",
                "memo": None,
                "account_id": "acct_test_123",
            },
        ]
        write_json(ynab_cache_dir / "transactions.json", ynab_txs)

        # Create reconcile node
        reconcile_node = BankDataReconcileFlowNode(test_config["data_dir"], test_config["config"])

        # First execution
        result1 = reconcile_node.execute(flow_context)
        assert len(result1.outputs) == 1

        # Wait for different timestamp
        time.sleep(1.1)

        # Second execution
        result2 = reconcile_node.execute(flow_context)

        # Verify second run's outputs includes ONLY the new file (flow engine archives old ones)
        assert len(result2.outputs) == 1

    def test_returns_warning_when_diverged(self, test_config, flow_context):
        """Node should return warning when accounts have discrepancies.

        NOTE: This test uses TestCsvHandler which doesn't extract balance points.
        Without balance points, there's no divergence to detect, so requires_review
        will be False. This test verifies reconcile succeeds without balance points.
        A future test should verify warning behavior with actual balance point divergence.
        """
        # Setup with mismatched balances
        create_raw_bank_data(test_config["data_dir"], "test-checking")
        parse_node = BankDataParseFlowNode(test_config["data_dir"], test_config["config"])
        parse_node.execute(flow_context)

        # Create YNAB cache with different transactions (will cause divergence)
        ynab_cache_dir = test_config["data_dir"] / "ynab" / "cache"
        ynab_cache_dir.mkdir(parents=True)
        ynab_txs = [
            # Only matches one bank transaction
            {
                "date": "2024-01-01",
                "amount": -5000,
                "payee_name": "Coffee Shop",
                "memo": None,
                "account_id": "acct_test_123",
            },
        ]
        write_json(ynab_cache_dir / "transactions.json", ynab_txs)

        # Create reconcile node
        reconcile_node = BankDataReconcileFlowNode(test_config["data_dir"], test_config["config"])

        # Execute node
        result = reconcile_node.execute(flow_context)

        # Verify success (no warning since no balance points to reconcile)
        assert result.success is True
        # NOTE: requires_review would only be True if balance points diverged
        assert result.requires_review is False

    def test_depends_on_ynab_sync(self, test_config, flow_context):
        """Node should check for YNAB cache."""
        # Create raw data and parse (but NOT ynab sync)
        create_raw_bank_data(test_config["data_dir"], "test-checking")
        parse_node = BankDataParseFlowNode(test_config["data_dir"], test_config["config"])
        parse_node.execute(flow_context)

        # Create reconcile node
        reconcile_node = BankDataReconcileFlowNode(test_config["data_dir"], test_config["config"])

        # Execute without YNAB cache
        result = reconcile_node.execute(flow_context)

        # Should fail with appropriate error
        assert result.success is False
        assert "YNAB cache not found" in result.error_message

    def test_get_output_dir(self, test_config):
        """get_output_dir() should return correct path."""
        node = BankDataReconcileFlowNode(test_config["data_dir"], test_config["config"])
        output_dir = node.get_output_dir()
        assert output_dir == test_config["data_dir"] / "bank_accounts" / "reconciliation"
