#!/usr/bin/env python3
"""
DataStore Protocol - Standard interface for domain data persistence.

Provides common abstraction for data access patterns across all financial domains
(Amazon, Apple, YNAB, Analysis), separating data persistence concerns from flow
orchestration logic.
"""

from datetime import datetime
from typing import Protocol, TypeVar

from finances.core.flow import NodeDataSummary

T = TypeVar("T")


class DataStore(Protocol[T]):
    """
    Protocol for domain data persistence and metadata queries.

    Provides standard interface for checking data existence, loading/saving data,
    and querying metadata (age, size, item counts) without coupling to specific
    storage implementations.

    Type parameter T represents the domain-specific data type (e.g., list of orders,
    list of receipts, dict of YNAB data).
    """

    def exists(self) -> bool:
        """
        Check if data exists in storage.

        Returns:
            True if data files/directory exist, False otherwise
        """
        ...

    def load(self) -> T:
        """
        Load data from storage.

        Returns:
            Domain-specific data structure

        Raises:
            FileNotFoundError: If data doesn't exist
            ValueError: If data is invalid/corrupted
        """
        ...

    def save(self, data: T) -> None:
        """
        Save data to storage.

        Args:
            data: Domain-specific data to persist
        """
        ...

    def last_modified(self) -> datetime | None:
        """
        Get timestamp of most recent data modification.

        Returns:
            datetime of last modification, or None if data doesn't exist
        """
        ...

    def age_days(self) -> int | None:
        """
        Get age of data in days since last modification.

        Returns:
            Number of days since last modification, or None if data doesn't exist
        """
        ...

    def item_count(self) -> int | None:
        """
        Get count of items/records in stored data.

        Interpretation varies by domain:
        - Amazon: number of CSV files
        - Apple: number of email files
        - YNAB: number of transactions
        - Analysis: number of chart files

        Returns:
            Count of items/records, or None if data doesn't exist
        """
        ...

    def size_bytes(self) -> int | None:
        """
        Get total storage size in bytes.

        Returns:
            Total size of all data files in bytes, or None if data doesn't exist
        """
        ...

    def summary_text(self) -> str:
        """
        Get human-readable summary of current data state.

        Returns:
            Brief text description for display in CLI prompts and logs
        """
        ...

    def to_node_data_summary(self) -> NodeDataSummary:
        """
        Convert DataStore state to NodeDataSummary for FlowNode integration.

        This bridges DataStore abstraction with FlowNode's interactive prompt system,
        allowing FlowNodes to delegate data summary logic to DataStores.

        Returns:
            NodeDataSummary with current data state
        """
        ...
