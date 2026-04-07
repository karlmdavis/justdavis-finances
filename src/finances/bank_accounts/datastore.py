"""DataStore implementations for bank accounts domain."""

from datetime import datetime
from pathlib import Path
from typing import Any

from finances.core.datastore_mixin import DataStoreMixin
from finances.core.json_utils import write_json


class BankNormalizedDataStore(DataStoreMixin):
    """
    Pattern C: Timestamped Accumulation for normalized account data.

    Files are stored as: {timestamp}_{slug}.json
    Each parse run creates new files (one per account).
    Files accumulate forever (no cleanup).
    """

    def __init__(self, normalized_dir: Path):
        """Initialize store with normalized data directory."""
        super().__init__()
        self.normalized_dir = normalized_dir

    def exists(self) -> bool:
        """Check if any normalized files exist."""
        return self.normalized_dir.exists() and len(self._get_files_cached(self.normalized_dir, "*.json")) > 0

    def save(self, account_slug: str, data: dict[str, Any]) -> Path:
        """
        Save normalized data with timestamp and account slug.

        Args:
            account_slug: Account identifier (e.g., "apple-card")
            data: Normalized account data (transactions, balances)

        Returns:
            Path to created file
        """
        self.normalized_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        output_file = self.normalized_dir / f"{timestamp}_{account_slug}.json"

        write_json(output_file, data)
        self._invalidate_cache()

        return output_file

    def last_modified(self) -> datetime | None:
        """Return most recent file modification time."""
        files = self._get_files_cached(self.normalized_dir, "*.json")
        most_recent = self._get_latest_file(files)
        if most_recent is None:
            return None
        return datetime.fromtimestamp(most_recent.stat().st_mtime)

    def item_count(self) -> int | None:
        """Return count of normalized files."""
        return len(self._get_files_cached(self.normalized_dir, "*.json"))

    def size_bytes(self) -> int | None:
        """Return total size of all normalized files."""
        files = self._get_files_cached(self.normalized_dir, "*.json")
        if not files:
            return None
        return self._get_total_size(files)

    def summary_text(self) -> str:
        """Provide human-readable summary."""
        count = self.item_count() or 0
        age = self.age_days()
        age_str = f"{age}d old" if age is not None else "never"
        return f"{count} normalized files, last modified {age_str}"


class BankReconciliationStore(DataStoreMixin):
    """
    Pattern C: Timestamped Accumulation for reconciliation operations.

    Files are stored as: {timestamp}_operations.json
    Each reconcile run creates one file covering all accounts.
    Files accumulate forever (no cleanup).
    """

    def __init__(self, reconciliation_dir: Path):
        """Initialize store with reconciliation directory."""
        super().__init__()
        self.reconciliation_dir = reconciliation_dir

    def exists(self) -> bool:
        """Check if any operations files exist."""
        return (
            self.reconciliation_dir.exists()
            and len(self._get_files_cached(self.reconciliation_dir, "*.json")) > 0
        )

    def save(self, data: dict[str, Any]) -> Path:
        """
        Save reconciliation with timestamp.

        Args:
            data: Reconciliation operations for all accounts

        Returns:
            Path to created file
        """
        self.reconciliation_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        output_file = self.reconciliation_dir / f"{timestamp}_operations.json"

        write_json(output_file, data)
        self._invalidate_cache()

        return output_file

    def last_modified(self) -> datetime | None:
        """Return most recent file modification time."""
        files = self._get_files_cached(self.reconciliation_dir, "*.json")
        most_recent = self._get_latest_file(files)
        if most_recent is None:
            return None
        return datetime.fromtimestamp(most_recent.stat().st_mtime)

    def item_count(self) -> int | None:
        """Return count of operations files."""
        return len(self._get_files_cached(self.reconciliation_dir, "*.json"))

    def size_bytes(self) -> int | None:
        """Return total size of all operations files."""
        files = self._get_files_cached(self.reconciliation_dir, "*.json")
        if not files:
            return None
        return self._get_total_size(files)

    def summary_text(self) -> str:
        """Provide human-readable summary."""
        count = self.item_count() or 0
        age = self.age_days()
        age_str = f"{age}d old" if age is not None else "never"
        return f"{count} reconciliation files, last modified {age_str}"
