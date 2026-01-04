"""Integration tests for account_data_parse flow node."""

import shutil
import tempfile
from pathlib import Path

from finances.bank_accounts.format_handlers.base import BankExportFormatHandler, ParseResult
from finances.bank_accounts.format_handlers.registry import FormatHandlerRegistry
from finances.bank_accounts.models import AccountConfig, BankAccountsConfig, BankTransaction, ImportPattern
from finances.bank_accounts.nodes import parse_account_data
from finances.core import FinancialDate, Money
from finances.core.json_utils import read_json


class TestCsvHandler(BankExportFormatHandler):
    """Test CSV format handler."""

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


class TestOfxHandler(BankExportFormatHandler):
    """Test OFX format handler."""

    @property
    def format_name(self) -> str:
        return "test_ofx"

    @property
    def supported_extensions(self) -> tuple[str, ...]:
        return (".ofx",)

    def validate_file(self, file_path: Path) -> bool:
        """Validate OFX file format."""
        return file_path.suffix == ".ofx"

    def parse(self, file_path: Path) -> ParseResult:
        """Parse test OFX file."""
        # Simple parser: just read first transaction line
        content = file_path.read_text()
        if "DTPOSTED:" not in content:
            return ParseResult.create(transactions=[])

        # Extract single transaction (simplified)
        lines = content.split("\n")
        date_line = next(line for line in lines if "DTPOSTED:" in line)
        desc_line = next(line for line in lines if "NAME:" in line)
        amt_line = next(line for line in lines if "TRNAMT:" in line)

        date = date_line.split(":")[1].strip()[:8]  # YYYYMMDD
        desc = desc_line.split(":")[1].strip()
        amt = int(float(amt_line.split(":")[1].strip()) * 100)

        transaction = BankTransaction(
            posted_date=FinancialDate.from_string(f"{date[:4]}-{date[4:6]}-{date[6:8]}"),
            description=desc,
            amount=Money.from_cents(amt),
        )

        return ParseResult.create(transactions=[transaction])


class TestParseNode:
    """Integration tests for parse_account_data function."""

    def setup_method(self) -> None:
        """Create temporary directories and registry for each test."""
        self.temp_dir = Path(tempfile.mkdtemp())
        self.base_dir = self.temp_dir / "base"
        self.base_dir.mkdir()

        # Create registry with test handlers
        self.registry = FormatHandlerRegistry()
        self.registry.register(TestCsvHandler)
        self.registry.register(TestOfxHandler)

    def teardown_method(self) -> None:
        """Clean up temporary directories."""
        shutil.rmtree(self.temp_dir)

    def test_parse_creates_normalized_json(self) -> None:
        """Test parse node creates normalized JSON from raw files."""
        # Create raw directory with test files
        raw_dir = self.base_dir / "raw" / "test-checking"
        raw_dir.mkdir(parents=True)

        # Write test CSV file
        csv_content = """Date,Description,Amount
2024-01-01,Coffee Shop,-500
2024-01-02,Grocery Store,-2500
2024-01-03,Paycheck,100000"""
        (raw_dir / "statement.csv").write_text(csv_content)

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
                    source_directory="/tmp/source",  # noqa: S108 - Not used in parse
                    download_instructions="Test instructions",
                    import_patterns=(ImportPattern(pattern="*.csv", format_handler="test_csv"),),
                ),
            )
        )

        # Run parse
        result = parse_account_data(config, self.base_dir, self.registry)

        # Verify normalized JSON was created
        normalized_file = self.base_dir / "normalized" / "test-checking.json"
        assert normalized_file.exists()

        # Read and verify JSON structure
        data = read_json(normalized_file)
        assert data["account_id"] == "test-checking"
        assert data["account_name"] == "Test Checking"
        assert data["account_type"] == "checking"
        assert len(data["transactions"]) == 3
        assert data["transactions"][0]["posted_date"] == "2024-01-01"
        assert data["transactions"][0]["description"] == "Coffee Shop"
        assert data["transactions"][0]["amount_milliunits"] == -5000

        # Verify data_period auto-detection
        assert data["data_period"]["start_date"] == "2024-01-01"
        assert data["data_period"]["end_date"] == "2024-01-03"

        # Verify result summary
        assert "test-checking" in result
        assert result["test-checking"]["transaction_count"] == 3
        assert "2024-01-01 to 2024-01-03" in result["test-checking"]["date_range"]

    def test_parse_deduplicates_overlapping_files(self) -> None:
        """Test that overlapping date ranges are deduplicated."""
        # Create raw directory with overlapping files
        raw_dir = self.base_dir / "raw" / "test-checking"
        raw_dir.mkdir(parents=True)

        # File 1 (older): Jan 1-3
        csv1_content = """Date,Description,Amount
2024-01-01,Old Transaction Jan 1,-1000
2024-01-02,Old Transaction Jan 2,-2000
2024-01-03,Old Transaction Jan 3,-3000"""
        file1 = raw_dir / "statement_jan.csv"
        file1.write_text(csv1_content)

        # Wait a bit and create File 2 (newer): Jan 2-4
        import time

        time.sleep(0.01)  # Ensure different mtime
        csv2_content = """Date,Description,Amount
2024-01-02,New Transaction Jan 2,-2500
2024-01-03,New Transaction Jan 3,-3500
2024-01-04,New Transaction Jan 4,-4000"""
        file2 = raw_dir / "statement_feb.csv"
        file2.write_text(csv2_content)

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

        # Run parse
        parse_account_data(config, self.base_dir, self.registry)

        # Read normalized JSON
        normalized_file = self.base_dir / "normalized" / "test-checking.json"
        data = read_json(normalized_file)

        # Verify deduplication: Jan 1 from file1, Jan 2-3 from file2 (newer), Jan 4 from file2
        assert len(data["transactions"]) == 4
        assert data["transactions"][0]["description"] == "Old Transaction Jan 1"  # From file1
        assert data["transactions"][1]["description"] == "New Transaction Jan 2"  # From file2 (newer)
        assert data["transactions"][2]["description"] == "New Transaction Jan 3"  # From file2 (newer)
        assert data["transactions"][3]["description"] == "New Transaction Jan 4"  # From file2

    def test_parse_auto_detects_date_range(self) -> None:
        """Test that data_period is auto-detected from transactions."""
        # Create raw directory
        raw_dir = self.base_dir / "raw" / "test-checking"
        raw_dir.mkdir(parents=True)

        # Write test file with transactions spanning several months
        csv_content = """Date,Description,Amount
2024-03-15,Transaction 1,-1000
2024-05-20,Transaction 2,-2000
2024-07-10,Transaction 3,-3000"""
        (raw_dir / "statement.csv").write_text(csv_content)

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

        # Run parse
        result = parse_account_data(config, self.base_dir, self.registry)

        # Verify date range auto-detection
        normalized_file = self.base_dir / "normalized" / "test-checking.json"
        data = read_json(normalized_file)

        assert data["data_period"]["start_date"] == "2024-03-15"
        assert data["data_period"]["end_date"] == "2024-07-10"

        # Verify result summary
        assert result["test-checking"]["date_range"] == "2024-03-15 to 2024-07-10"

    def test_parse_handles_multiple_file_formats(self) -> None:
        """Test parse with multiple file formats per account."""
        # Create raw directory
        raw_dir = self.base_dir / "raw" / "test-checking"
        raw_dir.mkdir(parents=True)

        # CSV file
        csv_content = """Date,Description,Amount
2024-01-01,CSV Transaction,-1000"""
        (raw_dir / "statement.csv").write_text(csv_content)

        # OFX file
        ofx_content = """OFXHEADER:100
DTPOSTED:20240102
NAME:OFX Transaction
TRNAMT:-20.00"""
        (raw_dir / "statement.ofx").write_text(ofx_content)

        # Create config with multiple patterns
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
                    import_patterns=(
                        ImportPattern(pattern="*.csv", format_handler="test_csv"),
                        ImportPattern(pattern="*.ofx", format_handler="test_ofx"),
                    ),
                ),
            )
        )

        # Run parse
        parse_account_data(config, self.base_dir, self.registry)

        # Verify both files were parsed
        normalized_file = self.base_dir / "normalized" / "test-checking.json"
        data = read_json(normalized_file)

        assert len(data["transactions"]) == 2
        # Transactions should be sorted by date
        assert data["transactions"][0]["description"] == "CSV Transaction"
        assert data["transactions"][1]["description"] == "OFX Transaction"

    def test_parse_handles_empty_raw_directory(self) -> None:
        """Test parse when raw directory has no matching files."""
        # Create empty raw directory
        raw_dir = self.base_dir / "raw" / "test-checking"
        raw_dir.mkdir(parents=True)

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

        # Run parse
        result = parse_account_data(config, self.base_dir, self.registry)

        # Verify empty normalized JSON was created
        normalized_file = self.base_dir / "normalized" / "test-checking.json"
        assert normalized_file.exists()

        data = read_json(normalized_file)
        assert len(data["transactions"]) == 0
        assert len(data["balances"]) == 0
        assert data["data_period"] is None

        # Verify result summary
        assert result["test-checking"]["transaction_count"] == 0
        assert result["test-checking"]["date_range"] == "no data"

    def test_parse_multiple_accounts(self) -> None:
        """Test parse with multiple accounts."""
        # Create raw directories for two accounts
        raw_dir1 = self.base_dir / "raw" / "chase-checking"
        raw_dir1.mkdir(parents=True)
        raw_dir2 = self.base_dir / "raw" / "chase-credit"
        raw_dir2.mkdir(parents=True)

        # Write test files
        (raw_dir1 / "checking.csv").write_text("Date,Description,Amount\n2024-01-01,Checking,-1000")
        (raw_dir2 / "credit.csv").write_text("Date,Description,Amount\n2024-01-02,Credit,-2000")

        # Create config with two accounts
        config = BankAccountsConfig(
            accounts=(
                AccountConfig(
                    ynab_account_id="acct_123",
                    ynab_account_name="Chase Checking",
                    slug="chase-checking",
                    bank_name="Chase",
                    account_type="checking",
                    statement_frequency="monthly",
                    source_directory="/tmp/source1",  # noqa: S108
                    download_instructions="Test instructions",
                    import_patterns=(ImportPattern(pattern="*.csv", format_handler="test_csv"),),
                ),
                AccountConfig(
                    ynab_account_id="acct_456",
                    ynab_account_name="Chase Credit",
                    slug="chase-credit",
                    bank_name="Chase",
                    account_type="credit",
                    statement_frequency="monthly",
                    source_directory="/tmp/source2",  # noqa: S108
                    download_instructions="Test instructions",
                    import_patterns=(ImportPattern(pattern="*.csv", format_handler="test_csv"),),
                ),
            )
        )

        # Run parse
        result = parse_account_data(config, self.base_dir, self.registry)

        # Verify both accounts processed
        assert "chase-checking" in result
        assert "chase-credit" in result

        # Verify normalized files exist
        assert (self.base_dir / "normalized" / "chase-checking.json").exists()
        assert (self.base_dir / "normalized" / "chase-credit.json").exists()

        # Verify transaction counts
        assert result["chase-checking"]["transaction_count"] == 1
        assert result["chase-credit"]["transaction_count"] == 1
