#!/usr/bin/env python3
"""
Unit tests for YNAB DataStore implementations.
"""

import tempfile
from pathlib import Path

from finances.core.json_utils import write_json
from finances.ynab.datastore import YnabCacheStore, YnabEditsStore


class TestYnabCacheStore:
    """Test YnabCacheStore behavior."""

    def setup_method(self):
        """Set up test fixtures."""
        self.temp_dir = Path(tempfile.mkdtemp())
        self.cache_dir = self.temp_dir / "ynab" / "cache"
        self.store = YnabCacheStore(self.cache_dir)

    def teardown_method(self):
        """Clean up test fixtures."""
        import shutil

        shutil.rmtree(self.temp_dir)

    def test_load_returns_cache_data(self):
        """Test load() returns cache data with all components."""
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        write_json(self.cache_dir / "transactions.json", [{"id": "t1"}])
        write_json(self.cache_dir / "accounts.json", {"accounts": []})
        write_json(self.cache_dir / "categories.json", {"category_groups": []})

        result = self.store.load()
        assert "transactions" in result
        assert "accounts" in result
        assert "categories" in result

    def test_save_writes_all_cache_components(self):
        """Test save() writes all cache components."""
        cache_data = {
            "transactions": [{"id": "t1"}],
            "accounts": {"accounts": []},
            "categories": {"category_groups": []},
        }
        self.store.save(cache_data)

        assert (self.cache_dir / "transactions.json").exists()
        assert (self.cache_dir / "accounts.json").exists()
        assert (self.cache_dir / "categories.json").exists()

    def test_item_count_returns_transaction_count(self):
        """Test item_count() returns count of transactions."""
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        write_json(self.cache_dir / "transactions.json", [{"id": "t1"}, {"id": "t2"}])

        result = self.store.item_count()
        assert result == 2

    def test_item_count_returns_zero_for_non_list(self):
        """Test item_count() returns 0 for non-list data."""
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        write_json(self.cache_dir / "transactions.json", {"data": []})

        result = self.store.item_count()
        assert result == 0

    def test_size_bytes_returns_total_size(self):
        """Test size_bytes() returns total size of all cache files."""
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        write_json(self.cache_dir / "transactions.json", [{"id": "t1"}])
        write_json(self.cache_dir / "accounts.json", {"accounts": []})

        result = self.store.size_bytes()
        assert result is not None
        assert result > 0


class TestYnabEditsStore:
    """Test YnabEditsStore behavior."""

    def setup_method(self):
        """Set up test fixtures."""
        self.temp_dir = Path(tempfile.mkdtemp())
        self.edits_dir = self.temp_dir / "ynab" / "edits"
        self.store = YnabEditsStore(self.edits_dir)

    def teardown_method(self):
        """Clean up test fixtures."""
        import shutil

        shutil.rmtree(self.temp_dir)

    def test_load_returns_most_recent_edit_file(self):
        """Test load() returns most recent edit file."""
        self.edits_dir.mkdir(parents=True, exist_ok=True)
        edit_data = {"edits": [{"transaction_id": "t1"}]}
        edit_file = self.edits_dir / "2024-10-01_12-00-00_transaction_edits.json"
        write_json(edit_file, edit_data)

        result = self.store.load()
        assert "edits" in result

    def test_save_creates_timestamped_file(self):
        """Test save() creates file with timestamp."""
        edit_data = {"edits": [{"transaction_id": "t1"}]}
        self.store.save(edit_data)

        assert self.edits_dir.exists()
        json_files = list(self.edits_dir.glob("*.json"))
        assert len(json_files) == 1
        assert "transaction_edits" in json_files[0].name

    def test_item_count_handles_edits_key(self):
        """Test item_count() handles 'edits' key structure."""
        self.edits_dir.mkdir(parents=True, exist_ok=True)
        edit_data = {"edits": [{"transaction_id": "t1"}, {"transaction_id": "t2"}]}
        edit_file = self.edits_dir / "2024-10-01_12-00-00_transaction_edits.json"
        write_json(edit_file, edit_data)

        result = self.store.item_count()
        assert result == 2

    def test_item_count_handles_updates_key(self):
        """Test item_count() handles 'updates' key structure."""
        self.edits_dir.mkdir(parents=True, exist_ok=True)
        edit_data = {"updates": [{"transaction_id": "t1"}]}
        edit_file = self.edits_dir / "2024-10-01_12-00-00_transaction_edits.json"
        write_json(edit_file, edit_data)

        result = self.store.item_count()
        assert result == 1

    def test_item_count_returns_zero_for_empty_dict(self):
        """Test item_count() returns 0 for empty dict."""
        self.edits_dir.mkdir(parents=True, exist_ok=True)
        edit_data = {}
        edit_file = self.edits_dir / "2024-10-01_12-00-00_transaction_edits.json"
        write_json(edit_file, edit_data)

        result = self.store.item_count()
        assert result == 0

    def test_get_retirement_edits_returns_matching_files(self):
        """Test get_retirement_edits() returns files matching pattern."""
        self.edits_dir.mkdir(parents=True, exist_ok=True)
        retirement_file = self.edits_dir / "2024-10-01_12-00-00_retirement_edits.json"
        write_json(retirement_file, {"edits": []})
        regular_file = self.edits_dir / "2024-10-01_12-00-00_transaction_edits.json"
        write_json(regular_file, {"edits": []})

        result = self.store.get_retirement_edits()
        assert len(result) == 1
        assert "retirement" in result[0].name

    def test_load_retirement_edits_returns_most_recent(self):
        """Test load_retirement_edits() returns most recent retirement file."""
        self.edits_dir.mkdir(parents=True, exist_ok=True)
        retirement_data = {"retirement_accounts": [{"account_id": "a1"}]}
        retirement_file = self.edits_dir / "2024-10-01_12-00-00_retirement_edits.json"
        write_json(retirement_file, retirement_data)

        result = self.store.load_retirement_edits()
        assert result is not None
        assert "retirement_accounts" in result
