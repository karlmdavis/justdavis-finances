#!/usr/bin/env python3
"""
YNAB DataStore Implementations

DataStore implementations for YNAB domain data management.
"""

from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

from finances.core.datastore_mixin import DataStoreMixin

from finances.core.json_utils import read_json, write_json

if TYPE_CHECKING:
    from finances.core.flow import NodeDataSummary


class YnabCacheStore(DataStoreMixin):
    """
    DataStore for YNAB cached data.

    Manages locally cached YNAB transactions, accounts, and categories
    synced via the YNAB API.
    """

    def __init__(self, cache_dir: Path):
        """
        Initialize YNAB cache store.

        Args:
            cache_dir: Directory containing YNAB cache files (data/ynab/cache)
        """
        super().__init__()
        self.cache_dir = cache_dir
        self._glob_pattern = "transactions.json"
        self.transactions_file = cache_dir / "transactions.json"

    def exists(self) -> bool:
        """Check if YNAB cache exists."""
        return self.transactions_file.exists()

    def load(self) -> dict:
        """
        Load YNAB cache data.

        Returns:
            Dictionary containing transactions, accounts, and categories

        Raises:
            FileNotFoundError: If cache doesn't exist
        """
        if not self.exists():
            raise FileNotFoundError(f"YNAB cache not found: {self.transactions_file}")

        # Load all cache components
        cache = {}
        cache["transactions"] = read_json(self.transactions_file)

        accounts_file = self.cache_dir / "accounts.json"
        if accounts_file.exists():
            cache["accounts"] = read_json(accounts_file)

        categories_file = self.cache_dir / "categories.json"
        if categories_file.exists():
            cache["categories"] = read_json(categories_file)

        return cache

    def save(self, data: dict) -> None:
        """
        Save YNAB cache data.

        Args:
            data: Dictionary with 'transactions', 'accounts', 'categories' keys
        """
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        if "transactions" in data:
            write_json(self.transactions_file, data["transactions"])

        if "accounts" in data:
            write_json(self.cache_dir / "accounts.json", data["accounts"])

        if "categories" in data:
            write_json(self.cache_dir / "categories.json", data["categories"])

    def last_modified(self) -> datetime | None:
        """Get timestamp of transactions cache file."""
        if not self.exists():
            return None
        return datetime.fromtimestamp(self.transactions_file.stat().st_mtime)

    def age_days(self) -> int | None:
        """Get age in days of transactions cache."""
        last_mod = self.last_modified()
        if last_mod is None:
            return None
        return (datetime.now() - last_mod).days

    def item_count(self) -> int | None:
        """Get count of transactions in cache."""
        if not self.exists():
            return None

        try:
            data = read_json(self.transactions_file)
            return len(data) if isinstance(data, list) else 0
        except Exception:
            return 0

    def size_bytes(self) -> int | None:
        """Get total size of cache files."""
        if not self.exists():
            return None

        total = self.transactions_file.stat().st_size

        accounts_file = self.cache_dir / "accounts.json"
        if accounts_file.exists():
            total += accounts_file.stat().st_size

        categories_file = self.cache_dir / "categories.json"
        if categories_file.exists():
            total += categories_file.stat().st_size

        return total

    def summary_text(self) -> str:
        """Get human-readable summary."""
        count = self.item_count()
        if count is None:
            return "No YNAB cache found"
        return f"YNAB cache: {count} transactions"

    def to_node_data_summary(self) -> "NodeDataSummary":
        """Convert to NodeDataSummary for FlowNode integration."""
        from finances.core.flow import NodeDataSummary

        return NodeDataSummary(
            exists=self.exists(),
            last_updated=self.last_modified(),
            age_days=self.age_days(),
            item_count=self.item_count(),
            size_bytes=self.size_bytes(),
            summary_text=self.summary_text(),
        )


class YnabEditsStore(DataStoreMixin):
    """
    DataStore for YNAB transaction edits.

    Manages JSON files containing proposed transaction updates
    (e.g., retirement account balance adjustments).
    """

    def __init__(self, edits_dir: Path):
        """
        Initialize YNAB edits store.

        Args:
            edits_dir: Directory containing edit files (data/ynab/edits)
        """
        super().__init__()
        self.edits_dir = edits_dir
        self._glob_pattern = "*.json"

    def exists(self) -> bool:
        """Check if any edit files exist."""
        if not self.edits_dir.exists():
            return False
        return len(list(self.edits_dir.glob("*.json"))) > 0

    def load(self) -> dict:
        """
        Load most recent edit file.

        Returns:
            Dictionary containing edit metadata and updates

        Raises:
            FileNotFoundError: If no edit files exist
            ValueError: If JSON data is not a dictionary
        """
        if not self.exists():
            raise FileNotFoundError(f"No edit files found in {self.edits_dir}")

        latest_file = max(self.edits_dir.glob("*.json"), key=lambda p: p.stat().st_mtime)
        result = read_json(latest_file)
        if not isinstance(result, dict):
            raise ValueError(f"Invalid edit data format: expected dict, got {type(result).__name__}")
        return result

    def save(self, data: dict) -> None:
        """
        Save edit file with timestamp.

        Args:
            data: Edit data dictionary with metadata and updates
        """
        self.edits_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        output_file = self.edits_dir / f"{timestamp}_transaction_edits.json"

        write_json(output_file, data)

    def last_modified(self) -> datetime | None:
        """Get timestamp of most recent edit file."""
        if not self.exists():
            return None

        latest_file = max(self.edits_dir.glob("*.json"), key=lambda p: p.stat().st_mtime)
        return datetime.fromtimestamp(latest_file.stat().st_mtime)

    def age_days(self) -> int | None:
        """Get age in days of most recent edit file."""
        last_mod = self.last_modified()
        if last_mod is None:
            return None
        return (datetime.now() - last_mod).days

    def item_count(self) -> int | None:
        """Get count of edits in most recent file."""
        if not self.exists():
            return None

        try:
            data = self.load()
            # Check multiple possible structures
            if "edits" in data:
                edits = data["edits"]
                return len(edits) if isinstance(edits, list) else 0
            elif "updates" in data:
                updates = data["updates"]
                return len(updates) if isinstance(updates, list) else 0
            return 0
        except (FileNotFoundError, ValueError, KeyError):
            return 0

    def size_bytes(self) -> int | None:
        """Get size of most recent edit file."""
        if not self.exists():
            return None

        latest_file = max(self.edits_dir.glob("*.json"), key=lambda p: p.stat().st_mtime)
        return latest_file.stat().st_size

    def summary_text(self) -> str:
        """Get human-readable summary."""
        count = self.item_count()
        if count is None:
            return "No YNAB edits found"
        return f"YNAB edits: {count} updates"

    def get_retirement_edits(self) -> list[Path]:
        """
        Get all retirement-specific edit files.

        Returns:
            List of paths to retirement edit files
        """
        if not self.edits_dir.exists():
            return []
        return list(self.edits_dir.glob("*retirement_edits*.json"))

    def load_retirement_edits(self) -> dict | None:
        """
        Load most recent retirement edit file.

        Returns:
            Dictionary containing retirement edit data, or None if not found

        Raises:
            ValueError: If JSON data is not a dictionary
        """
        retirement_files = self.get_retirement_edits()
        if not retirement_files:
            return None

        latest_file = max(retirement_files, key=lambda p: p.stat().st_mtime)
        result = read_json(latest_file)
        if not isinstance(result, dict):
            raise ValueError(
                f"Invalid retirement edit data format: expected dict, got {type(result).__name__}"
            )
        return result

    def to_node_data_summary(self) -> "NodeDataSummary":
        """Convert to NodeDataSummary for FlowNode integration."""
        from finances.core.flow import NodeDataSummary

        return NodeDataSummary(
            exists=self.exists(),
            last_updated=self.last_modified(),
            age_days=self.age_days(),
            item_count=self.item_count(),
            size_bytes=self.size_bytes(),
            summary_text=self.summary_text(),
        )
