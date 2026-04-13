"""Integration tests for account_data_retrieve flow node."""

import shutil
import tempfile
from pathlib import Path

import pytest

from finances.bank_accounts.models import AccountConfig, BankAccountsConfig, ImportPattern
from finances.bank_accounts.retrieve import retrieve_account_data


class TestRetrieveNode:
    """Integration tests for retrieve_account_data function."""

    def setup_method(self) -> None:
        """Create temporary directories for each test."""
        self.temp_dir = Path(tempfile.mkdtemp())
        self.source_dir = self.temp_dir / "source"
        self.base_dir = self.temp_dir / "base"
        self.source_dir.mkdir()
        self.base_dir.mkdir()

    def teardown_method(self) -> None:
        """Clean up temporary directories."""
        shutil.rmtree(self.temp_dir)

    def test_retrieve_copies_matching_files(self) -> None:
        """Test retrieve node copies files matching patterns."""
        # Create test files in source directory
        (self.source_dir / "statement_jan.csv").write_text("transaction data")
        (self.source_dir / "statement_feb.csv").write_text("more data")
        (self.source_dir / "other_file.txt").write_text("not a match")

        # Create config with pattern matching CSV files
        config = BankAccountsConfig(
            accounts=(
                AccountConfig(
                    ynab_account_id="acct_123",
                    ynab_account_name="Test Account",
                    slug="test-checking",
                    bank_name="Test Bank",
                    source_directory=str(self.source_dir),
                    download_instructions="Download from bank",
                    import_patterns=(ImportPattern(pattern="statement_*.csv", format_handler="csv_handler"),),
                ),
            )
        )

        # Run retrieve
        result = retrieve_account_data(config, self.base_dir)

        # Verify files were copied
        dest_dir = self.base_dir / "raw" / "test-checking"
        assert dest_dir.exists()
        assert (dest_dir / "statement_jan.csv").exists()
        assert (dest_dir / "statement_feb.csv").exists()
        assert not (dest_dir / "other_file.txt").exists()

        # Verify result summary
        assert result == {"test-checking": {"copied": 2, "skipped": 0}}

    def test_retrieve_skips_existing_files(self) -> None:
        """Test that existing files with same name/size are skipped."""
        # Create test file in source
        (self.source_dir / "statement.csv").write_text("transaction data")

        # Create same file in destination (pre-existing)
        dest_dir = self.base_dir / "raw" / "test-checking"
        dest_dir.mkdir(parents=True)
        (dest_dir / "statement.csv").write_text("transaction data")

        # Create config
        config = BankAccountsConfig(
            accounts=(
                AccountConfig(
                    ynab_account_id="acct_123",
                    ynab_account_name="Test Account",
                    slug="test-checking",
                    bank_name="Test Bank",
                    source_directory=str(self.source_dir),
                    download_instructions="Download from bank",
                    import_patterns=(ImportPattern(pattern="statement.csv", format_handler="csv_handler"),),
                ),
            )
        )

        # Run retrieve
        result = retrieve_account_data(config, self.base_dir)

        # Verify file was skipped
        assert result == {"test-checking": {"copied": 0, "skipped": 1}}

    def test_retrieve_copies_file_with_different_size(self) -> None:
        """Test that files with same name but different size are copied."""
        # Create test file in source
        (self.source_dir / "statement.csv").write_text("new transaction data")

        # Create different file in destination (different size)
        dest_dir = self.base_dir / "raw" / "test-checking"
        dest_dir.mkdir(parents=True)
        (dest_dir / "statement.csv").write_text("old data")

        # Create config
        config = BankAccountsConfig(
            accounts=(
                AccountConfig(
                    ynab_account_id="acct_123",
                    ynab_account_name="Test Account",
                    slug="test-checking",
                    bank_name="Test Bank",
                    source_directory=str(self.source_dir),
                    download_instructions="Download from bank",
                    import_patterns=(ImportPattern(pattern="statement.csv", format_handler="csv_handler"),),
                ),
            )
        )

        # Run retrieve
        result = retrieve_account_data(config, self.base_dir)

        # Verify file was copied (replacing old one)
        assert result == {"test-checking": {"copied": 1, "skipped": 0}}
        assert (dest_dir / "statement.csv").read_text() == "new transaction data"

    def test_retrieve_fails_on_missing_source_dir(self) -> None:
        """Test that missing source directory fails with clear error."""
        # Create config with non-existent source directory
        nonexistent_dir = self.temp_dir / "nonexistent"
        config = BankAccountsConfig(
            accounts=(
                AccountConfig(
                    ynab_account_id="acct_123",
                    ynab_account_name="Test Account",
                    slug="test-checking",
                    bank_name="Test Bank",
                    source_directory=str(nonexistent_dir),
                    download_instructions="Download from bank",
                    import_patterns=(ImportPattern(pattern="*.csv", format_handler="csv_handler"),),
                ),
            )
        )

        # Run retrieve and expect error
        with pytest.raises(FileNotFoundError) as exc_info:
            retrieve_account_data(config, self.base_dir)

        assert "Source directory does not exist" in str(exc_info.value)
        assert str(nonexistent_dir) in str(exc_info.value)

    def test_retrieve_multiple_accounts(self) -> None:
        """Test retrieve with multiple accounts."""
        # Create source directories for two accounts
        source_dir1 = self.temp_dir / "source1"
        source_dir2 = self.temp_dir / "source2"
        source_dir1.mkdir()
        source_dir2.mkdir()

        # Create test files
        (source_dir1 / "checking_jan.csv").write_text("checking data")
        (source_dir2 / "credit_jan.csv").write_text("credit data")

        # Create config with two accounts
        config = BankAccountsConfig(
            accounts=(
                AccountConfig(
                    ynab_account_id="acct_123",
                    ynab_account_name="Checking Account",
                    slug="chase-checking",
                    bank_name="Chase",
                    source_directory=str(source_dir1),
                    download_instructions="Download checking",
                    import_patterns=(ImportPattern(pattern="checking_*.csv", format_handler="csv_handler"),),
                ),
                AccountConfig(
                    ynab_account_id="acct_456",
                    ynab_account_name="Credit Account",
                    slug="chase-credit",
                    bank_name="Chase",
                    source_directory=str(source_dir2),
                    download_instructions="Download credit",
                    import_patterns=(ImportPattern(pattern="credit_*.csv", format_handler="csv_handler"),),
                ),
            )
        )

        # Run retrieve
        result = retrieve_account_data(config, self.base_dir)

        # Verify both accounts processed
        assert result == {
            "chase-checking": {"copied": 1, "skipped": 0},
            "chase-credit": {"copied": 1, "skipped": 0},
        }

        # Verify files in correct directories
        assert (self.base_dir / "raw" / "chase-checking" / "checking_jan.csv").exists()
        assert (self.base_dir / "raw" / "chase-credit" / "credit_jan.csv").exists()

    def test_retrieve_multiple_patterns(self) -> None:
        """Test retrieve with multiple import patterns per account."""
        # Create test files with different patterns
        (self.source_dir / "transactions.csv").write_text("transactions")
        (self.source_dir / "statement.ofx").write_text("ofx data")
        (self.source_dir / "other.txt").write_text("other")

        # Create config with multiple patterns
        config = BankAccountsConfig(
            accounts=(
                AccountConfig(
                    ynab_account_id="acct_123",
                    ynab_account_name="Test Account",
                    slug="test-checking",
                    bank_name="Test Bank",
                    source_directory=str(self.source_dir),
                    download_instructions="Download from bank",
                    import_patterns=(
                        ImportPattern(pattern="*.csv", format_handler="csv_handler"),
                        ImportPattern(pattern="*.ofx", format_handler="ofx_handler"),
                    ),
                ),
            )
        )

        # Run retrieve
        result = retrieve_account_data(config, self.base_dir)

        # Verify matching files copied
        dest_dir = self.base_dir / "raw" / "test-checking"
        assert (dest_dir / "transactions.csv").exists()
        assert (dest_dir / "statement.ofx").exists()
        assert not (dest_dir / "other.txt").exists()
        assert result == {"test-checking": {"copied": 2, "skipped": 0}}

    def test_retrieve_no_matching_files(self) -> None:
        """Test retrieve when no files match patterns."""
        # Create files that don't match pattern
        (self.source_dir / "other.txt").write_text("not a match")

        # Create config
        config = BankAccountsConfig(
            accounts=(
                AccountConfig(
                    ynab_account_id="acct_123",
                    ynab_account_name="Test Account",
                    slug="test-checking",
                    bank_name="Test Bank",
                    source_directory=str(self.source_dir),
                    download_instructions="Download from bank",
                    import_patterns=(ImportPattern(pattern="*.csv", format_handler="csv_handler"),),
                ),
            )
        )

        # Run retrieve
        result = retrieve_account_data(config, self.base_dir)

        # Verify no files copied
        dest_dir = self.base_dir / "raw" / "test-checking"
        assert dest_dir.exists()  # Directory created even if empty
        assert list(dest_dir.iterdir()) == []
        assert result == {"test-checking": {"copied": 0, "skipped": 0}}

    def test_retrieve_expanduser_in_source_path(self) -> None:
        """Test that ~ in source_directory is expanded."""
        # Create test file
        (self.source_dir / "statement.csv").write_text("data")

        # Create config with ~ in path (we'll replace with actual path in test)
        # This tests the expanduser() functionality
        import os

        # Use a subdirectory to simulate ~ expansion
        home_sim = self.temp_dir / "home"
        home_sim.mkdir()
        downloads = home_sim / "Downloads"
        downloads.mkdir()
        (downloads / "statement.csv").write_text("data")

        # Temporarily change HOME for this test
        original_home = os.environ.get("HOME")
        os.environ["HOME"] = str(home_sim)

        try:
            config = BankAccountsConfig(
                accounts=(
                    AccountConfig(
                        ynab_account_id="acct_123",
                        ynab_account_name="Test Account",
                        slug="test-checking",
                        bank_name="Test Bank",
                        source_directory="~/Downloads",
                        download_instructions="Download from bank",
                        import_patterns=(ImportPattern(pattern="*.csv", format_handler="csv_handler"),),
                    ),
                )
            )

            # Run retrieve
            result = retrieve_account_data(config, self.base_dir)

            # Verify file was copied
            assert result == {"test-checking": {"copied": 1, "skipped": 0}}
            assert (self.base_dir / "raw" / "test-checking" / "statement.csv").exists()
        finally:
            # Restore original HOME
            if original_home:
                os.environ["HOME"] = original_home
            else:
                os.environ.pop("HOME", None)
