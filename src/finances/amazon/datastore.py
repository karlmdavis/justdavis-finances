#!/usr/bin/env python3
"""
Amazon DataStore Implementations

DataStore implementations for Amazon domain data management.
"""

from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

from finances.core.json_utils import read_json

if TYPE_CHECKING:
    from finances.core.flow import NodeDataSummary


class AmazonRawDataStore:
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
        self.raw_dir = raw_dir

    def exists(self) -> bool:
        """Check if Amazon raw data exists."""
        if not self.raw_dir.exists():
            return False
        return len(list(self.raw_dir.glob("**/Retail.OrderHistory.*.csv"))) > 0

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

        csv_files = list(self.raw_dir.glob("**/Retail.OrderHistory.*.csv"))
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

        csv_files = list(self.raw_dir.glob("**/Retail.OrderHistory.*.csv"))
        latest_file = max(csv_files, key=lambda p: p.stat().st_mtime)
        return datetime.fromtimestamp(latest_file.stat().st_mtime)

    def age_days(self) -> int | None:
        """Get age in days of most recent CSV file."""
        last_mod = self.last_modified()
        if last_mod is None:
            return None
        return (datetime.now() - last_mod).days

    def item_count(self) -> int | None:
        """Get count of Amazon CSV files (one per account)."""
        if not self.exists():
            return None
        return len(list(self.raw_dir.glob("**/Retail.OrderHistory.*.csv")))

    def size_bytes(self) -> int | None:
        """Get total size of all CSV files."""
        if not self.exists():
            return None
        csv_files = list(self.raw_dir.glob("**/Retail.OrderHistory.*.csv"))
        return sum(f.stat().st_size for f in csv_files)

    def summary_text(self) -> str:
        """Get human-readable summary."""
        count = self.item_count()
        if count is None:
            return "No Amazon raw data found"
        return f"Amazon data: {count} account(s)"

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


class AmazonMatchResultsStore:
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
        self.matches_dir = matches_dir

    def exists(self) -> bool:
        """Check if matching results exist."""
        if not self.matches_dir.exists():
            return False
        return len(list(self.matches_dir.glob("*.json"))) > 0

    def load(self) -> dict:
        """
        Load most recent matching results.

        Returns:
            Dictionary containing match metadata and results

        Raises:
            FileNotFoundError: If no match files exist
        """
        if not self.exists():
            raise FileNotFoundError(f"No match results found in {self.matches_dir}")

        latest_file = max(self.matches_dir.glob("*.json"), key=lambda p: p.stat().st_mtime)
        result = read_json(latest_file)
        return result if isinstance(result, dict) else {}

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

    def last_modified(self) -> datetime | None:
        """Get timestamp of most recent match file."""
        if not self.exists():
            return None

        latest_file = max(self.matches_dir.glob("*.json"), key=lambda p: p.stat().st_mtime)
        return datetime.fromtimestamp(latest_file.stat().st_mtime)

    def age_days(self) -> int | None:
        """Get age in days of most recent match file."""
        last_mod = self.last_modified()
        if last_mod is None:
            return None
        return (datetime.now() - last_mod).days

    def item_count(self) -> int | None:
        """Get count of matched transactions in most recent results."""
        if not self.exists():
            return None

        try:
            data = self.load()
            return len(data.get("matches", [])) if isinstance(data, dict) else 0
        except Exception:
            return 0

    def size_bytes(self) -> int | None:
        """Get size of most recent match file."""
        if not self.exists():
            return None

        latest_file = max(self.matches_dir.glob("*.json"), key=lambda p: p.stat().st_mtime)
        return latest_file.stat().st_size

    def summary_text(self) -> str:
        """Get human-readable summary."""
        count = self.item_count()
        if count is None:
            return "No Amazon matches found"
        return f"Amazon matches: {count} transactions"

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
