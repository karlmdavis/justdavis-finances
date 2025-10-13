#!/usr/bin/env python3
"""
Amazon DataStore Implementations

DataStore implementations for Amazon domain data management.
"""

from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

from finances.core.datastore_mixin import DataStoreMixin
from finances.core.json_utils import read_json

if TYPE_CHECKING:
    from finances.core.flow import NodeDataSummary


class AmazonRawDataStore(DataStoreMixin):
    """
    DataStore for Amazon raw order history CSV files.

    Manages extracted CSV files from Amazon order history exports,
    typically organized in account-specific directories.
    """

    def __init__(self, raw_dir: Path):
        """
        Initialize Amazon raw data store.

        Args:
            raw_dir: Directory containing Amazon raw data (data/amazon/raw)
        """
        super().__init__()
        self.raw_dir = raw_dir
        self._glob_pattern = "**/Retail.OrderHistory.*.csv"

    def exists(self) -> bool:
        """Check if Amazon raw data exists."""
        if not self.raw_dir.exists():
            return False
        files = self._get_files_cached(self.raw_dir, self._glob_pattern)
        return len(files) > 0

    def load(self) -> list[Path]:
        """
        Load list of Amazon CSV file paths.

        Returns:
            List of paths to Amazon order history CSV files

        Raises:
            FileNotFoundError: If raw directory doesn't exist or has no CSV files
        """
        if not self.raw_dir.exists():
            raise FileNotFoundError(f"Amazon raw directory not found: {self.raw_dir}")

        csv_files = self._get_files_cached(self.raw_dir, self._glob_pattern)
        if not csv_files:
            raise FileNotFoundError(f"No Amazon CSV files found in {self.raw_dir}")

        return csv_files

    def save(self, data: list[Path]) -> None:
        """
        Save operation not applicable for raw file tracking.

        Amazon raw data is extracted from ZIP files by external process,
        not directly saved through DataStore.

        Raises:
            NotImplementedError: Always
        """
        raise NotImplementedError("Amazon raw data is managed externally (ZIP extraction)")

    def last_modified(self) -> datetime | None:
        """Get timestamp of most recently modified CSV file."""
        if not self.exists():
            return None

        csv_files = self._get_files_cached(self.raw_dir, self._glob_pattern)
        latest_file = self._get_latest_file(csv_files)
        if latest_file is None:
            return None
        return datetime.fromtimestamp(latest_file.stat().st_mtime)

    def item_count(self) -> int | None:
        """Get count of Amazon CSV files (one per account)."""
        if not self.exists():
            return None
        files = self._get_files_cached(self.raw_dir, self._glob_pattern)
        return len(files)

    def size_bytes(self) -> int | None:
        """Get total size of all CSV files."""
        if not self.exists():
            return None
        csv_files = self._get_files_cached(self.raw_dir, self._glob_pattern)
        return self._get_total_size(csv_files)

    def summary_text(self) -> str:
        """Get human-readable summary."""
        count = self.item_count()
        if count is None:
            return "No Amazon raw data found"
        return f"Amazon data: {count} account(s)"


class AmazonMatchResultsStore(DataStoreMixin):
    """
    DataStore for Amazon transaction matching results.

    Manages JSON files containing YNAB transaction matches to Amazon orders,
    with match confidence scores and metadata.
    """

    def __init__(self, matches_dir: Path):
        """
        Initialize Amazon match results store.

        Args:
            matches_dir: Directory containing match result files
        """
        super().__init__()
        self.matches_dir = matches_dir
        self._glob_pattern = "*.json"

    def exists(self) -> bool:
        """Check if matching results exist."""
        if not self.matches_dir.exists():
            return False
        files = self._get_files_cached(self.matches_dir, self._glob_pattern)
        return len(files) > 0

    def load(self) -> dict:
        """
        Load most recent matching results.

        Returns:
            Dictionary containing match metadata and results

        Raises:
            FileNotFoundError: If no match files exist
            ValueError: If JSON data is not a dictionary
        """
        if not self.exists():
            raise FileNotFoundError(f"No match results found in {self.matches_dir}")

        files = self._get_files_cached(self.matches_dir, self._glob_pattern)
        latest_file = self._get_latest_file(files)
        if latest_file is None:
            raise FileNotFoundError(f"No match results found in {self.matches_dir}")

        result = read_json(latest_file)
        if not isinstance(result, dict):
            raise ValueError(
                f"Invalid match data format: expected dict, got {type(result).__name__}"
            )
        return result

    def save(self, data: dict) -> None:
        """
        Save matching results with timestamp.

        Args:
            data: Matching results dictionary with metadata and matches
        """
        self.matches_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        output_file = self.matches_dir / f"{timestamp}_amazon_matching_results.json"

        from finances.core.json_utils import write_json_with_defaults

        # Use write_json_with_defaults to handle pandas Timestamps from CSV parsing
        write_json_with_defaults(output_file, data, default=str)
        # Invalidate cache after write
        self._invalidate_cache()

    def last_modified(self) -> datetime | None:
        """Get timestamp of most recent match file."""
        if not self.exists():
            return None

        files = self._get_files_cached(self.matches_dir, self._glob_pattern)
        latest_file = self._get_latest_file(files)
        if latest_file is None:
            return None
        return datetime.fromtimestamp(latest_file.stat().st_mtime)

    def item_count(self) -> int | None:
        """Get count of matched transactions in most recent results."""
        if not self.exists():
            return None

        try:
            data = self.load()
            return len(data.get("matches", [])) if isinstance(data, dict) else None
        except (FileNotFoundError, ValueError, KeyError, AttributeError):
            return None

    def size_bytes(self) -> int | None:
        """Get size of most recent match file."""
        if not self.exists():
            return None

        files = self._get_files_cached(self.matches_dir, self._glob_pattern)
        latest_file = self._get_latest_file(files)
        if latest_file is None:
            return None
        return latest_file.stat().st_size

    def summary_text(self) -> str:
        """Get human-readable summary."""
        count = self.item_count()
        if count is None:
            return "No Amazon matches found"
        return f"Amazon matches: {count} transactions"
