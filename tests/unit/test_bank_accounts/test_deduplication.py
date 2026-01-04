"""Unit tests for transaction deduplication logic."""

from pathlib import Path

from finances.bank_accounts.deduplication import deduplicate_transactions
from finances.bank_accounts.format_handlers.base import ParseResult
from finances.bank_accounts.models import BankTransaction
from finances.core import FinancialDate, Money


class TestDeduplicateTransactions:
    """Test deduplicate_transactions function."""

    def test_deduplicate_transactions_by_date(self):
        """Test that for overlapping dates, newer file wins."""
        # Create test transactions
        # File 1 (older, mtime=1000): Jan 1-3
        file1 = Path("/tmp/old_file.csv")  # noqa: S108
        tx1_jan1 = BankTransaction(
            posted_date=FinancialDate.from_string("2024-01-01"),
            description="Old transaction Jan 1",
            amount=Money.from_cents(-1000),
        )
        tx1_jan2 = BankTransaction(
            posted_date=FinancialDate.from_string("2024-01-02"),
            description="Old transaction Jan 2",
            amount=Money.from_cents(-2000),
        )
        tx1_jan3 = BankTransaction(
            posted_date=FinancialDate.from_string("2024-01-03"),
            description="Old transaction Jan 3",
            amount=Money.from_cents(-3000),
        )
        parse1 = ParseResult.create(transactions=[tx1_jan1, tx1_jan2, tx1_jan3])

        # File 2 (newer, mtime=2000): Jan 2-4
        file2 = Path("/tmp/new_file.csv")  # noqa: S108
        tx2_jan2 = BankTransaction(
            posted_date=FinancialDate.from_string("2024-01-02"),
            description="New transaction Jan 2",
            amount=Money.from_cents(-2500),
        )
        tx2_jan3 = BankTransaction(
            posted_date=FinancialDate.from_string("2024-01-03"),
            description="New transaction Jan 3",
            amount=Money.from_cents(-3500),
        )
        tx2_jan4 = BankTransaction(
            posted_date=FinancialDate.from_string("2024-01-04"),
            description="New transaction Jan 4",
            amount=Money.from_cents(-4000),
        )
        parse2 = ParseResult.create(transactions=[tx2_jan2, tx2_jan3, tx2_jan4])

        # Input: [(file, parse_result, mtime)]
        input_data = [
            (file1, parse1, 1000.0),
            (file2, parse2, 2000.0),
        ]

        # Deduplicate
        result = deduplicate_transactions(input_data)

        # Expected: Jan 1 from file1 (only file with that date)
        #           Jan 2-3 from file2 (newer file)
        #           Jan 4 from file2 (only file with that date)
        assert len(result) == 4

        # Verify chronological order
        assert result[0].posted_date == FinancialDate.from_string("2024-01-01")
        assert result[1].posted_date == FinancialDate.from_string("2024-01-02")
        assert result[2].posted_date == FinancialDate.from_string("2024-01-03")
        assert result[3].posted_date == FinancialDate.from_string("2024-01-04")

        # Verify transactions from correct files
        assert result[0].description == "Old transaction Jan 1"  # Only in file1
        assert result[1].description == "New transaction Jan 2"  # Newer file wins
        assert result[2].description == "New transaction Jan 3"  # Newer file wins
        assert result[3].description == "New transaction Jan 4"  # Only in file2

    def test_deduplicate_preserves_non_overlapping_dates(self):
        """Test that transactions from non-overlapping dates are all preserved."""
        # File 1: Jan 1-2
        file1 = Path("/tmp/file1.csv")  # noqa: S108
        tx1_jan1 = BankTransaction(
            posted_date=FinancialDate.from_string("2024-01-01"),
            description="Transaction Jan 1",
            amount=Money.from_cents(-1000),
        )
        tx1_jan2 = BankTransaction(
            posted_date=FinancialDate.from_string("2024-01-02"),
            description="Transaction Jan 2",
            amount=Money.from_cents(-2000),
        )
        parse1 = ParseResult.create(transactions=[tx1_jan1, tx1_jan2])

        # File 2: Jan 5-6
        file2 = Path("/tmp/file2.csv")  # noqa: S108
        tx2_jan5 = BankTransaction(
            posted_date=FinancialDate.from_string("2024-01-05"),
            description="Transaction Jan 5",
            amount=Money.from_cents(-5000),
        )
        tx2_jan6 = BankTransaction(
            posted_date=FinancialDate.from_string("2024-01-06"),
            description="Transaction Jan 6",
            amount=Money.from_cents(-6000),
        )
        parse2 = ParseResult.create(transactions=[tx2_jan5, tx2_jan6])

        # Input with arbitrary mtimes (no overlap, so mtime shouldn't matter)
        input_data = [
            (file1, parse1, 1000.0),
            (file2, parse2, 2000.0),
        ]

        # Deduplicate
        result = deduplicate_transactions(input_data)

        # All 4 transactions should be preserved
        assert len(result) == 4

        # Verify chronological order
        assert result[0].posted_date == FinancialDate.from_string("2024-01-01")
        assert result[1].posted_date == FinancialDate.from_string("2024-01-02")
        assert result[2].posted_date == FinancialDate.from_string("2024-01-05")
        assert result[3].posted_date == FinancialDate.from_string("2024-01-06")

    def test_deduplicate_same_file_not_duplicates(self):
        """Test that multiple transactions on same date in same file are ALL preserved."""
        # Single file with multiple transactions on same date
        file1 = Path("/tmp/file.csv")  # noqa: S108
        tx1 = BankTransaction(
            posted_date=FinancialDate.from_string("2024-01-01"),
            description="Transaction 1",
            amount=Money.from_cents(-1000),
        )
        tx2 = BankTransaction(
            posted_date=FinancialDate.from_string("2024-01-01"),
            description="Transaction 2",
            amount=Money.from_cents(-2000),
        )
        tx3 = BankTransaction(
            posted_date=FinancialDate.from_string("2024-01-01"),
            description="Transaction 3",
            amount=Money.from_cents(-3000),
        )
        parse1 = ParseResult.create(transactions=[tx1, tx2, tx3])

        # Input
        input_data = [(file1, parse1, 1000.0)]

        # Deduplicate
        result = deduplicate_transactions(input_data)

        # All 3 transactions should be preserved (same file, same date)
        assert len(result) == 3
        assert result[0].description == "Transaction 1"
        assert result[1].description == "Transaction 2"
        assert result[2].description == "Transaction 3"

    def test_deduplicate_empty_input(self):
        """Test that empty input returns empty list."""
        result = deduplicate_transactions([])
        assert result == []

    def test_deduplicate_multiple_files_same_date(self):
        """Test that when 3+ files have same date, file with latest mtime wins."""
        # File 1 (oldest, mtime=1000)
        file1 = Path("/tmp/file1.csv")  # noqa: S108
        tx1 = BankTransaction(
            posted_date=FinancialDate.from_string("2024-01-01"),
            description="File 1 transaction",
            amount=Money.from_cents(-1000),
        )
        parse1 = ParseResult.create(transactions=[tx1])

        # File 2 (middle, mtime=2000)
        file2 = Path("/tmp/file2.csv")  # noqa: S108
        tx2 = BankTransaction(
            posted_date=FinancialDate.from_string("2024-01-01"),
            description="File 2 transaction",
            amount=Money.from_cents(-2000),
        )
        parse2 = ParseResult.create(transactions=[tx2])

        # File 3 (newest, mtime=3000)
        file3 = Path("/tmp/file3.csv")  # noqa: S108
        tx3 = BankTransaction(
            posted_date=FinancialDate.from_string("2024-01-01"),
            description="File 3 transaction",
            amount=Money.from_cents(-3000),
        )
        parse3 = ParseResult.create(transactions=[tx3])

        # Input
        input_data = [
            (file1, parse1, 1000.0),
            (file2, parse2, 2000.0),
            (file3, parse3, 3000.0),
        ]

        # Deduplicate
        result = deduplicate_transactions(input_data)

        # Only file3's transaction should be included (newest mtime)
        assert len(result) == 1
        assert result[0].description == "File 3 transaction"
