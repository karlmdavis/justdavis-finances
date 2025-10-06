#!/usr/bin/env python3
"""
Amazon Order Data Loader

Utilities for loading Amazon order history CSV files into structured DataFrames
for transaction matching.

Functions:
- find_latest_amazon_export: Discover most recent Amazon data export
- load_amazon_data: Load Amazon order CSVs into matcher-compatible format
"""

import logging
from pathlib import Path
from typing import Any

import pandas as pd

from ..core.config import get_config

logger = logging.getLogger(__name__)


def find_latest_amazon_export(base_path: str | Path | None = None) -> Path | None:
    """
    Find the most recent Amazon data export directory.

    Searches for directories matching the pattern YYYY-MM-DD_accountname_amazon_data
    in the base path and returns the most recent one based on directory name.

    Args:
        base_path: Base directory to search. If None, uses config.data_dir/amazon/raw

    Returns:
        Path to the most recent export directory, or None if no exports found
    """
    if base_path is None:
        config = get_config()
        base_path = config.data_dir / "amazon" / "raw"
    else:
        base_path = Path(base_path)

    if not base_path.exists():
        return None

    # Find all Amazon data directories (pattern: YYYY-MM-DD_*_amazon_data)
    amazon_dirs = [
        d
        for d in base_path.iterdir()
        if d.is_dir() and d.name.endswith("_amazon_data") and d.name[0:4].isdigit()
    ]

    if not amazon_dirs:
        return None

    # Sort by directory name (descending) to get latest
    latest_dir = sorted(amazon_dirs, reverse=True)[0]
    return latest_dir


def load_amazon_data(
    data_dir: str | Path | None = None, accounts: tuple[str, ...] = ()
) -> dict[str, tuple[pd.DataFrame, pd.DataFrame]]:
    """
    Load Amazon order data from CSV files into matcher-compatible format.

    Discovers all Amazon account directories in the data directory and loads
    retail order history CSV files into pandas DataFrames.

    Args:
        data_dir: Base directory containing Amazon data exports.
                  If None, uses config.data_dir/amazon/raw
        accounts: Tuple of specific account names to load.
                  If empty, loads all discovered accounts.

    Returns:
        Dictionary mapping account names to (retail_df, digital_df) tuples.
        Digital DataFrame is currently empty as digital orders are not yet supported.

    Raises:
        FileNotFoundError: If data directory doesn't exist or no account data found

    Example:
        >>> account_data = load_amazon_data()
        >>> # Returns: {"karl": (retail_df, digital_df), "erica": (retail_df, digital_df)}
        >>> matcher = SimplifiedMatcher()
        >>> result = matcher.match_transaction(ynab_tx, account_data)
    """
    if data_dir is None:
        config = get_config()
        data_dir = config.data_dir / "amazon" / "raw"
    else:
        data_dir = Path(data_dir)

    if not data_dir.exists():
        raise FileNotFoundError(f"Amazon data directory not found: {data_dir}")

    # Find all Amazon account directories
    amazon_dirs = [
        d
        for d in data_dir.iterdir()
        if d.is_dir() and d.name.endswith("_amazon_data") and d.name[0:4].isdigit()
    ]

    if not amazon_dirs:
        raise FileNotFoundError(f"No Amazon data directories found in {data_dir}")

    account_data: dict[str, tuple[pd.DataFrame, pd.DataFrame]] = {}
    accounts_filter = set(accounts) if accounts else None

    for account_dir in amazon_dirs:
        # Extract account name from directory (pattern: YYYY-MM-DD_accountname_amazon_data)
        dir_parts = account_dir.name.split("_")
        if len(dir_parts) < 3:
            continue  # Skip malformed directory names

        account_name = dir_parts[1]  # e.g., "karl" from "2024-10-05_karl_amazon_data"

        # Skip if filtering accounts and this account not in filter
        if accounts_filter and account_name not in accounts_filter:
            continue

        # Load retail order CSV
        retail_csv_pattern = "Retail.OrderHistory.*.csv"
        retail_csv_files = list(account_dir.glob(retail_csv_pattern))

        if not retail_csv_files:
            # No retail CSV found - skip this account
            continue

        # Load the retail CSV file (take first if multiple)
        retail_csv = retail_csv_files[0]
        try:
            retail_df = pd.read_csv(retail_csv, parse_dates=["Order Date", "Ship Date"])
        except (pd.errors.ParserError, FileNotFoundError, ValueError) as e:
            # Skip accounts with malformed CSV files
            logger.warning("Failed to load %s: %s", retail_csv, e)
            continue

        # Digital orders not yet supported - use empty DataFrame
        digital_df = pd.DataFrame()

        # Store in account data dictionary
        account_data[account_name] = (retail_df, digital_df)

    if not account_data:
        raise FileNotFoundError(
            f"No valid Amazon account data found in {data_dir}"
            + (f" for accounts: {list(accounts_filter)}" if accounts_filter else "")
        )

    return account_data


def get_account_summary(account_data: dict[str, tuple[pd.DataFrame, pd.DataFrame]]) -> dict[str, Any]:
    """
    Generate summary statistics for loaded Amazon account data.

    Args:
        account_data: Dictionary of account data from load_amazon_data()

    Returns:
        Dictionary with summary information:
        - total_accounts: Number of accounts loaded
        - accounts: List of account names
        - total_orders: Total number of retail orders across all accounts
        - orders_by_account: Dictionary mapping account names to order counts
    """
    total_orders = 0
    orders_by_account: dict[str, int] = {}

    for account_name, (retail_df, _digital_df) in account_data.items():
        order_count = len(retail_df)
        total_orders += order_count
        orders_by_account[account_name] = order_count

    summary: dict[str, Any] = {
        "total_accounts": len(account_data),
        "accounts": list(account_data.keys()),
        "total_orders": total_orders,
        "orders_by_account": orders_by_account,
    }

    return summary
