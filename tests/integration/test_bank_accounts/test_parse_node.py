"""Integration tests for account_data_parse flow node."""

import shutil
import tempfile
from pathlib import Path

from finances.bank_accounts.format_handlers.base import BankExportFormatHandler, ParseResult
from finances.bank_accounts.format_handlers.registry import FormatHandlerRegistry
from finances.bank_accounts.models import AccountConfig, BankAccountsConfig, BankTransaction, ImportPattern
from finances.bank_accounts.nodes import parse_account_data
from finances.core import FinancialDate, Money


class TestCsvHandler(BankExportFormatHandler):
    """Test CSV format handler."""

    @property
    def format_name(self) -> str:
        return "test_csv"

    @property
    def supported_extensions(self) -> tuple[str, ...]:
        return (".csv",)

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
        """Test parse node returns ParseResult with transactions."""
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
        results = parse_account_data(config, self.base_dir, self.registry)

        # Verify result structure
        assert "test-checking" in results
        result = results["test-checking"]

        # Verify ParseResult has transactions
        assert len(result.transactions) == 3
        assert result.transactions[0].posted_date == FinancialDate.from_string("2024-01-01")
        assert result.transactions[0].description == "Coffee Shop"
        assert result.transactions[0].amount.to_milliunits() == -5000

        # Verify coverage_intervals auto-detection (min to max posted_date for single CSV file)
        assert result.coverage_intervals == (
            (FinancialDate.from_string("2024-01-01"), FinancialDate.from_string("2024-01-03")),
        )

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
        results = parse_account_data(config, self.base_dir, self.registry)
        result = results["test-checking"]

        # Verify deduplication: Jan 1 from file1, Jan 2-3 from file2 (newer), Jan 4 from file2
        assert len(result.transactions) == 4
        assert result.transactions[0].description == "Old Transaction Jan 1"  # From file1
        assert result.transactions[1].description == "New Transaction Jan 2"  # From file2 (newer)
        assert result.transactions[2].description == "New Transaction Jan 3"  # From file2 (newer)
        assert result.transactions[3].description == "New Transaction Jan 4"  # From file2

    def test_parse_auto_detects_date_range(self) -> None:
        """Test that statement_date is auto-detected from transactions."""
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
        results = parse_account_data(config, self.base_dir, self.registry)
        result = results["test-checking"]

        # Verify coverage_intervals cover the transaction range
        assert result.coverage_intervals == (
            (FinancialDate.from_string("2024-03-15"), FinancialDate.from_string("2024-07-10")),
        )
        assert len(result.transactions) == 3

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
        results = parse_account_data(config, self.base_dir, self.registry)
        result = results["test-checking"]

        # Verify both files were parsed
        assert len(result.transactions) == 2
        # Transactions should be sorted by date
        assert result.transactions[0].description == "CSV Transaction"
        assert result.transactions[1].description == "OFX Transaction"

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
        results = parse_account_data(config, self.base_dir, self.registry)
        result = results["test-checking"]

        # Verify empty ParseResult was created
        assert len(result.transactions) == 0
        assert len(result.balance_points) == 0
        assert result.coverage_intervals == ()

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
        results = parse_account_data(config, self.base_dir, self.registry)

        # Verify both accounts processed
        assert "chase-checking" in results
        assert "chase-credit" in results

        # Verify transaction counts
        assert len(results["chase-checking"].transactions) == 1
        assert len(results["chase-credit"].transactions) == 1

    def test_coverage_intervals_single_file(self) -> None:
        """Single file produces one interval from min to max posted_date."""
        raw_dir = self.base_dir / "raw" / "test-checking"
        raw_dir.mkdir(parents=True)
        (raw_dir / "statement.csv").write_text(
            "Date,Description,Amount\n"
            "2024-01-05,Coffee,-500\n"
            "2024-01-10,Grocery,-2500\n"
            "2024-01-20,Paycheck,100000"
        )
        config = BankAccountsConfig(
            accounts=(
                AccountConfig(
                    ynab_account_id="acct_123",
                    ynab_account_name="Test",
                    slug="test-checking",
                    bank_name="Test Bank",
                    account_type="checking",
                    statement_frequency="monthly",
                    source_directory="/tmp/source",  # noqa: S108
                    download_instructions="",
                    import_patterns=(ImportPattern(pattern="*.csv", format_handler="test_csv"),),
                ),
            )
        )
        results = parse_account_data(config, self.base_dir, self.registry)
        result = results["test-checking"]
        assert result.coverage_intervals == (
            (FinancialDate.from_string("2024-01-05"), FinancialDate.from_string("2024-01-20")),
        )

    def test_coverage_intervals_two_non_overlapping_files(self) -> None:
        """Two non-overlapping statement files produce two independent intervals."""
        raw_dir = self.base_dir / "raw" / "test-checking"
        raw_dir.mkdir(parents=True)
        # January statement
        (raw_dir / "jan.csv").write_text(
            "Date,Description,Amount\n" "2024-01-01,Jan A,-100\n" "2024-01-31,Jan B,-200"
        )
        # March statement (February gap)
        (raw_dir / "mar.csv").write_text(
            "Date,Description,Amount\n" "2024-03-01,Mar A,-300\n" "2024-03-31,Mar B,-400"
        )
        config = BankAccountsConfig(
            accounts=(
                AccountConfig(
                    ynab_account_id="acct_123",
                    ynab_account_name="Test",
                    slug="test-checking",
                    bank_name="Test Bank",
                    account_type="checking",
                    statement_frequency="monthly",
                    source_directory="/tmp/source",  # noqa: S108
                    download_instructions="",
                    import_patterns=(ImportPattern(pattern="*.csv", format_handler="test_csv"),),
                ),
            )
        )
        results = parse_account_data(config, self.base_dir, self.registry)
        result = results["test-checking"]
        # Two separate intervals preserved
        assert result.coverage_intervals == (
            (FinancialDate.from_string("2024-01-01"), FinancialDate.from_string("2024-01-31")),
            (FinancialDate.from_string("2024-03-01"), FinancialDate.from_string("2024-03-31")),
        )

    def test_coverage_intervals_overlapping_files_union(self) -> None:
        """Two overlapping files (different boundaries) produce their union.

        Simulates e.g. OFX Jan 1-5 + CSV Jan 3-31: the union is [Jan 1, Jan 31],
        covering the full range of both files.
        """
        raw_dir = self.base_dir / "raw" / "test-checking"
        raw_dir.mkdir(parents=True)
        # File A covers Jan 1-5 (earlier start, earlier end)
        (raw_dir / "file_a.csv").write_text(
            "Date,Description,Amount\n" "2024-01-01,File A Jan 1,-100\n" "2024-01-05,File A Jan 5,-200"
        )
        # File B covers Jan 3-31 (later start, later end)
        (raw_dir / "file_b.csv").write_text(
            "Date,Description,Amount\n" "2024-01-03,File B Jan 3,-300\n" "2024-01-31,File B Jan 31,-400"
        )
        config = BankAccountsConfig(
            accounts=(
                AccountConfig(
                    ynab_account_id="acct_123",
                    ynab_account_name="Test",
                    slug="test-checking",
                    bank_name="Test Bank",
                    account_type="checking",
                    statement_frequency="monthly",
                    source_directory="/tmp/source",  # noqa: S108
                    download_instructions="",
                    import_patterns=(ImportPattern(pattern="*.csv", format_handler="test_csv"),),
                ),
            )
        )
        results = parse_account_data(config, self.base_dir, self.registry)
        result = results["test-checking"]
        # Union of [Jan 1, Jan 5] and [Jan 3, Jan 31] → [Jan 1, Jan 31] (overlapping → merge)
        assert result.coverage_intervals == (
            (FinancialDate.from_string("2024-01-01"), FinancialDate.from_string("2024-01-31")),
        )

    def test_deduplication_preserves_multiple_identical_transactions(self) -> None:
        """Cross-format dedup must not over-drop when N identical txs exist.

        Scenario mirrors real Apple Savings September 2023 data:
        - OFX file (newer) has TWO $0.11 Daily Cash Deposits on 2023-09-27.
        - CSV file (older) has ONE $0.11 Daily Cash Deposit with
          transaction_date=2023-09-27 but posted_date=2023-09-28.

        The cross-format dedup logic should drop exactly ONE OFX 09/27 entry
        (the CSV counterpart) and keep the second OFX 09/27 plus the CSV 09/28,
        yielding two $0.11 transactions total — not one.
        """
        import time

        raw_dir = self.base_dir / "raw" / "test-savings"
        raw_dir.mkdir(parents=True)

        # Older CSV: one $0.11 tx with transaction_date=09/27, posted=09/28
        csv_content = (
            "posted_date,transaction_date,description,amount_cents\n"
            "2023-09-28,2023-09-27,Daily Cash Deposit,11\n"
        )
        csv_file = raw_dir / "sep_2023.csv"
        csv_file.write_text(csv_content)

        # Newer OFX: two $0.11 txs both on 09/27 (no transaction_date)
        time.sleep(0.01)  # ensure OFX mtime > CSV mtime
        ofx_content = "2023-09-27,Daily Cash Deposit,11\n" "2023-09-27,Daily Cash Deposit,11\n"
        ofx_file = raw_dir / "sep_2023.ofx"
        ofx_file.write_text(ofx_content)

        # Handlers: CSV produces txs with transaction_date; OFX produces txs without
        class SavingsCsvHandler(BankExportFormatHandler):
            @property
            def format_name(self) -> str:
                return "savings_csv"

            @property
            def supported_extensions(self) -> tuple[str, ...]:
                return (".csv",)

            def parse(self, file_path: Path) -> ParseResult:
                txs = []
                for line in file_path.read_text().strip().split("\n")[1:]:
                    p = line.split(",")
                    txs.append(
                        BankTransaction(
                            posted_date=FinancialDate.from_string(p[0]),
                            transaction_date=FinancialDate.from_string(p[1]),
                            description=p[2],
                            amount=Money.from_cents(int(p[3])),
                        )
                    )
                return ParseResult.create(transactions=txs)

        class SavingsOfxHandler(BankExportFormatHandler):
            @property
            def format_name(self) -> str:
                return "savings_ofx"

            @property
            def supported_extensions(self) -> tuple[str, ...]:
                return (".ofx",)

            def parse(self, file_path: Path) -> ParseResult:
                txs = []
                for line in file_path.read_text().strip().split("\n"):
                    p = line.split(",")
                    txs.append(
                        BankTransaction(
                            posted_date=FinancialDate.from_string(p[0]),
                            description=p[1].strip(),
                            amount=Money.from_cents(int(p[2])),
                        )
                    )
                return ParseResult.create(transactions=txs)

        registry = FormatHandlerRegistry()
        registry.register(SavingsCsvHandler)
        registry.register(SavingsOfxHandler)

        config = BankAccountsConfig(
            accounts=(
                AccountConfig(
                    ynab_account_id="acct_savings",
                    ynab_account_name="Test Savings",
                    slug="test-savings",
                    bank_name="Test Bank",
                    account_type="savings",
                    statement_frequency="monthly",
                    source_directory="/tmp/source",  # noqa: S108
                    download_instructions="",
                    import_patterns=(
                        ImportPattern(pattern="*.csv", format_handler="savings_csv"),
                        ImportPattern(pattern="*.ofx", format_handler="savings_ofx"),
                    ),
                ),
            )
        )

        results = parse_account_data(config, self.base_dir, registry)
        result = results["test-savings"]

        # Expect 2 transactions: OFX 09/27 (2nd copy kept) + CSV 09/28
        # The dedup should drop only ONE OFX 09/27, not both.
        daily_cash = [tx for tx in result.transactions if tx.description == "Daily Cash Deposit"]
        assert len(daily_cash) == 2, f"Expected 2 Daily Cash Deposit txs but got {len(daily_cash)}: " + str(
            [(str(tx.posted_date), tx.transaction_date) for tx in daily_cash]
        )
        dates = {str(tx.posted_date) for tx in daily_cash}
        assert "2023-09-27" in dates, "Expected one tx on 2023-09-27 (from OFX)"
        assert "2023-09-28" in dates, "Expected one tx on 2023-09-28 (from CSV)"
