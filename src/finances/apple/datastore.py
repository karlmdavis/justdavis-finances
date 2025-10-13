#!/usr/bin/env python3
"""
Apple DataStore Implementations

DataStore implementations for Apple domain data management.
"""

from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

from finances.core.json_utils import read_json

if TYPE_CHECKING:
    from finances.core.flow import NodeDataSummary


class AppleEmailStore:
    """
    DataStore for Apple receipt emails.

    Manages .eml files containing Apple receipt emails fetched via IMAP.
    """

    def __init__(self, emails_dir: Path):
        """
        Initialize Apple email store.

        Args:
            emails_dir: Directory containing email files (data/apple/emails)
        """
        self.emails_dir = emails_dir

    def exists(self) -> bool:
        """Check if Apple email files exist."""
        if not self.emails_dir.exists():
            return False
        return len(list(self.emails_dir.glob("*.eml"))) > 0

    def load(self) -> list[Path]:
        """
        Load list of email file paths.

        Returns:
            List of paths to .eml files

        Raises:
            FileNotFoundError: If emails directory doesn't exist or has no emails
        """
        if not self.emails_dir.exists():
            raise FileNotFoundError(f"Apple emails directory not found: {self.emails_dir}")

        email_files = list(self.emails_dir.glob("*.eml"))
        if not email_files:
            raise FileNotFoundError(f"No Apple email files found in {self.emails_dir}")

        return email_files

    def save(self, data: list[Path]) -> None:
        """
        Save operation not applicable for email tracking.

        Apple emails are fetched via IMAP by external process,
        not directly saved through DataStore.

        Raises:
            NotImplementedError: Always
        """
        raise NotImplementedError("Apple emails are managed externally (IMAP fetcher)")

    def last_modified(self) -> datetime | None:
        """Get timestamp of most recently modified email file."""
        if not self.exists():
            return None

        email_files = list(self.emails_dir.glob("*.eml"))
        latest_file = max(email_files, key=lambda p: p.stat().st_mtime)
        return datetime.fromtimestamp(latest_file.stat().st_mtime)

    def age_days(self) -> int | None:
        """Get age in days of most recent email file."""
        last_mod = self.last_modified()
        if last_mod is None:
            return None
        return (datetime.now() - last_mod).days

    def item_count(self) -> int | None:
        """Get count of Apple email files."""
        if not self.exists():
            return None
        return len(list(self.emails_dir.glob("*.eml")))

    def size_bytes(self) -> int | None:
        """Get total size of all email files."""
        if not self.exists():
            return None
        email_files = list(self.emails_dir.glob("*.eml"))
        return sum(f.stat().st_size for f in email_files)

    def summary_text(self) -> str:
        """Get human-readable summary."""
        count = self.item_count()
        if count is None:
            return "No Apple emails found"
        return f"Apple emails: {count} receipts"

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


class AppleReceiptStore:
    """
    DataStore for parsed Apple receipts.

    Manages JSON files containing parsed Apple receipt data extracted from emails.
    """

    def __init__(self, exports_dir: Path):
        """
        Initialize Apple receipt store.

        Args:
            exports_dir: Directory containing parsed receipt JSON files
        """
        self.exports_dir = exports_dir

    def exists(self) -> bool:
        """Check if parsed receipt files exist."""
        if not self.exports_dir.exists():
            return False
        return len(list(self.exports_dir.glob("*.json"))) > 0

    def load(self) -> list[dict]:
        """
        Load all parsed receipt data.

        Returns:
            List of receipt dictionaries

        Raises:
            FileNotFoundError: If no receipt files exist
        """
        if not self.exists():
            raise FileNotFoundError(f"No parsed receipts found in {self.exports_dir}")

        json_files = list(self.exports_dir.glob("*.json"))
        return [read_json(json_file) for json_file in json_files]

    def save(self, data: list[dict]) -> None:
        """
        Save parsed receipt data.

        Args:
            data: List of receipt dictionaries
        """
        from finances.core.json_utils import write_json

        self.exports_dir.mkdir(parents=True, exist_ok=True)

        for receipt in data:
            # Use order_id or receipt_id as filename
            filename = receipt.get("order_id") or receipt.get("id") or "unknown"
            output_file = self.exports_dir / f"{filename}.json"
            write_json(output_file, receipt)

    def last_modified(self) -> datetime | None:
        """Get timestamp of most recent receipt file."""
        if not self.exists():
            return None

        json_files = list(self.exports_dir.glob("*.json"))
        latest_file = max(json_files, key=lambda p: p.stat().st_mtime)
        return datetime.fromtimestamp(latest_file.stat().st_mtime)

    def age_days(self) -> int | None:
        """Get age in days of most recent receipt file."""
        last_mod = self.last_modified()
        if last_mod is None:
            return None
        return (datetime.now() - last_mod).days

    def item_count(self) -> int | None:
        """Get count of parsed receipt files."""
        if not self.exists():
            return None
        return len(list(self.exports_dir.glob("*.json")))

    def size_bytes(self) -> int | None:
        """Get total size of all receipt files."""
        if not self.exists():
            return None
        json_files = list(self.exports_dir.glob("*.json"))
        return sum(f.stat().st_size for f in json_files)

    def summary_text(self) -> str:
        """Get human-readable summary."""
        count = self.item_count()
        if count is None:
            return "No parsed Apple receipts found"
        return f"Parsed receipts: {count} files"

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


class AppleMatchResultsStore:
    """
    DataStore for Apple transaction matching results.

    Manages JSON files containing YNAB transaction matches to Apple receipts,
    with match confidence scores and metadata.
    """

    def __init__(self, matches_dir: Path):
        """
        Initialize Apple match results store.

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
        return read_json(latest_file)

    def save(self, data: dict) -> None:
        """
        Save matching results with timestamp.

        Args:
            data: Matching results dictionary with metadata and matches
        """
        from finances.core.json_utils import write_json

        self.matches_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        output_file = self.matches_dir / f"{timestamp}_apple_matching_results.json"

        write_json(output_file, data)

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
            return "No Apple matches found"
        return f"Apple matches: {count} transactions"

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
