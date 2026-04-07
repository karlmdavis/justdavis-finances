"""Unit tests for bank accounts DataStore classes."""

from pathlib import Path
from time import sleep

from finances.bank_accounts.datastore import (
    BankNormalizedDataStore,
    BankReconciliationStore,
)


class TestBankNormalizedDataStore:
    """Test BankNormalizedDataStore Pattern C behavior."""

    def test_exists_false_when_no_directory(self):
        """Store should not exist if directory doesn't exist."""
        store = BankNormalizedDataStore(Path("/nonexistent"))
        assert not store.exists()

    def test_exists_false_when_empty_directory(self, tmp_path):
        """Store should not exist if directory is empty."""
        store = BankNormalizedDataStore(tmp_path)
        assert not store.exists()

    def test_exists_true_after_save(self, tmp_path):
        """Store should exist after saving data."""
        store = BankNormalizedDataStore(tmp_path)
        store.save("apple-card", {"test": "data"})
        assert store.exists()

    def test_save_creates_timestamped_file(self, tmp_path):
        """Save should create file with timestamp and slug."""
        store = BankNormalizedDataStore(tmp_path)
        output_file = store.save("apple-card", {"test": "data"})

        assert output_file.exists()
        assert "apple-card" in output_file.name
        assert output_file.suffix == ".json"

    def test_item_count(self, tmp_path):
        """Item count should return number of files."""
        store = BankNormalizedDataStore(tmp_path)

        assert store.item_count() == 0

        store.save("apple-card", {"test": 1})
        assert store.item_count() == 1

        sleep(1.1)  # Ensure different timestamp (second precision)
        store.save("apple-savings", {"test": 2})
        assert store.item_count() == 2

    def test_last_modified(self, tmp_path):
        """Last modified should return most recent file time."""
        store = BankNormalizedDataStore(tmp_path)

        assert store.last_modified() is None

        store.save("apple-card", {"test": "data"})
        assert store.last_modified() is not None

    def test_size_bytes(self, tmp_path):
        """Size bytes should return total size of all files."""
        store = BankNormalizedDataStore(tmp_path)

        assert store.size_bytes() is None

        store.save("apple-card", {"test": "data"})
        size = store.size_bytes()
        assert size is not None
        assert size > 0

    def test_summary_text(self, tmp_path):
        """Summary should include count and age."""
        store = BankNormalizedDataStore(tmp_path)
        store.save("apple-card", {"test": "data"})

        summary = store.summary_text()
        assert "1 normalized files" in summary
        assert "0d old" in summary


class TestBankReconciliationStore:
    """Test BankReconciliationStore Pattern C behavior."""

    def test_exists_false_when_no_directory(self):
        """Store should not exist if directory doesn't exist."""
        store = BankReconciliationStore(Path("/nonexistent"))
        assert not store.exists()

    def test_exists_false_when_empty_directory(self, tmp_path):
        """Store should not exist if directory is empty."""
        store = BankReconciliationStore(tmp_path)
        assert not store.exists()

    def test_exists_true_after_save(self, tmp_path):
        """Store should exist after saving data."""
        store = BankReconciliationStore(tmp_path)
        store.save({"test": "data"})
        assert store.exists()

    def test_save_creates_timestamped_file(self, tmp_path):
        """Save should create file with timestamp and 'operations'."""
        store = BankReconciliationStore(tmp_path)
        output_file = store.save({"test": "data"})

        assert output_file.exists()
        assert "operations" in output_file.name
        assert output_file.suffix == ".json"

    def test_item_count(self, tmp_path):
        """Item count should return number of files."""
        store = BankReconciliationStore(tmp_path)

        assert store.item_count() == 0

        store.save({"test": 1})
        assert store.item_count() == 1

        sleep(1.1)  # Ensure different timestamp (second precision)
        store.save({"test": 2})
        assert store.item_count() == 2

    def test_last_modified(self, tmp_path):
        """Last modified should return most recent file time."""
        store = BankReconciliationStore(tmp_path)

        assert store.last_modified() is None

        store.save({"test": "data"})
        assert store.last_modified() is not None

    def test_size_bytes(self, tmp_path):
        """Size bytes should return total size of all files."""
        store = BankReconciliationStore(tmp_path)

        assert store.size_bytes() is None

        store.save({"test": "data"})
        size = store.size_bytes()
        assert size is not None
        assert size > 0

    def test_summary_text(self, tmp_path):
        """Summary should include count and age."""
        store = BankReconciliationStore(tmp_path)
        store.save({"test": "data"})

        summary = store.summary_text()
        assert "1 reconciliation files" in summary
        assert "0d old" in summary
