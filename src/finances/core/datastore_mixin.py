#!/usr/bin/env python3
"""
DataStore Mixin - Common functionality for all DataStore implementations.

Provides shared implementation of metadata methods and file caching
to reduce redundant file system operations.
"""

from abc import abstractmethod
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from finances.core.flow import NodeDataSummary


class DataStoreMixin:
    """
    Mixin providing common DataStore functionality.

    Provides:
    - Cached file listing to reduce redundant glob operations
    - Common metadata methods (age_days, to_node_data_summary)
    - File stat aggregation helpers

    Subclasses must implement:
    - exists() -> bool
    - last_modified() -> datetime | None
    - item_count() -> int | None
    - size_bytes() -> int | None
    - summary_text() -> str
    """

    def __init__(self):
        """Initialize mixin state."""
        self._file_cache: list[Path] | None = None
        self._cache_timestamp: float | None = None
        self._cache_ttl_seconds: float = 1.0  # Cache for 1 second

    def _invalidate_cache(self) -> None:
        """Invalidate the file cache."""
        self._file_cache = None
        self._cache_timestamp = None

    def _is_cache_valid(self) -> bool:
        """Check if file cache is still valid."""
        if self._file_cache is None or self._cache_timestamp is None:
            return False
        elapsed = datetime.now().timestamp() - self._cache_timestamp
        return elapsed < self._cache_ttl_seconds

    def _get_files_cached(self, directory: Path, pattern: str) -> list[Path]:
        """
        Get list of files matching pattern with caching.

        Caches results for 1 second to avoid redundant glob operations
        when multiple metadata methods are called in sequence.

        Args:
            directory: Directory to search
            pattern: Glob pattern to match files

        Returns:
            List of matching file paths
        """
        # Check if cache is still valid
        if self._is_cache_valid():
            return self._file_cache  # type: ignore

        # Refresh cache
        if directory.exists():
            self._file_cache = list(directory.glob(pattern))
        else:
            self._file_cache = []

        self._cache_timestamp = datetime.now().timestamp()
        return self._file_cache

    def _get_latest_file(self, files: list[Path]) -> Path | None:
        """
        Get most recently modified file from list.

        Args:
            files: List of file paths

        Returns:
            Path to most recent file, or None if list is empty
        """
        if not files:
            return None
        return max(files, key=lambda p: p.stat().st_mtime)

    def _get_total_size(self, files: list[Path]) -> int:
        """
        Get total size of all files.

        Args:
            files: List of file paths

        Returns:
            Sum of file sizes in bytes
        """
        return sum(f.stat().st_size for f in files)

    @abstractmethod
    def exists(self) -> bool:
        """Check if data exists in storage."""
        ...

    @abstractmethod
    def last_modified(self) -> datetime | None:
        """Get timestamp of most recent data modification."""
        ...

    @abstractmethod
    def item_count(self) -> int | None:
        """Get count of items/records in stored data."""
        ...

    @abstractmethod
    def size_bytes(self) -> int | None:
        """Get total storage size in bytes."""
        ...

    @abstractmethod
    def summary_text(self) -> str:
        """Get human-readable summary of current data state."""
        ...

    def age_days(self) -> int | None:
        """
        Get age of data in days since last modification.

        Returns:
            Number of days since last modification, or None if data doesn't exist
        """
        last_mod = self.last_modified()
        if last_mod is None:
            return None
        return (datetime.now() - last_mod).days

    def to_node_data_summary(self) -> "NodeDataSummary":
        """
        Convert DataStore state to NodeDataSummary for FlowNode integration.

        This bridges DataStore abstraction with FlowNode's interactive prompt system,
        allowing FlowNodes to delegate data summary logic to DataStores.

        Returns:
            NodeDataSummary with current data state
        """
        from finances.core.flow import NodeDataSummary

        return NodeDataSummary(
            exists=self.exists(),
            last_updated=self.last_modified(),
            age_days=self.age_days(),
            item_count=self.item_count(),
            size_bytes=self.size_bytes(),
            summary_text=self.summary_text(),
        )
