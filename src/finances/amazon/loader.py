#!/usr/bin/env python3
"""
Amazon Order Data Loader

Utilities for loading Amazon order history CSV files into structured data
for transaction matching.

Functions:
- find_latest_amazon_export: Discover most recent Amazon data export
- load_orders: Load Amazon order CSVs as domain models
"""

import logging
import re
from pathlib import Path

import pandas as pd

from ..core.config import get_config
from .models import AmazonOrderItem

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


def load_orders(
    data_dir: str | Path | None = None, accounts: tuple[str, ...] = ()
) -> dict[str, list[AmazonOrderItem]]:
    """
    Load Amazon order data from CSV files as domain models.

    Discovers all Amazon account directories and loads retail order history
    CSV files into AmazonOrderItem domain models.

    Args:
        data_dir: Base directory containing Amazon data exports.
                  If None, uses config.data_dir/amazon/raw
        accounts: Tuple of specific account names to load.
                  If empty, loads all discovered accounts.

    Returns:
        Dictionary mapping account names to lists of AmazonOrderItem objects.
        Each item represents one CSV row (one product within an order).

    Raises:
        FileNotFoundError: If data directory doesn't exist or no account data found

    Example:
        >>> orders_by_account = load_orders()
        >>> # Returns: {"karl": [AmazonOrderItem, ...], "erica": [AmazonOrderItem, ...]}
        >>> karl_orders = orders_by_account["karl"]
        >>> for order_item in karl_orders:
        ...     print(f"{order_item.product_name}: {order_item.total_owed}")
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

    orders_by_account: dict[str, list[AmazonOrderItem]] = {}
    accounts_filter = set(accounts) if accounts else None

    # Regex pattern to extract account name from directory
    dir_pattern = re.compile(r"^\d{4}-\d{2}-\d{2}_(.+?)_amazon_data$")

    for account_dir in amazon_dirs:
        # Extract account name from directory
        match = dir_pattern.match(account_dir.name)
        if not match:
            logger.warning("Skipping malformed directory name: %s", account_dir.name)
            continue

        account_name = match.group(1)

        # Skip if filtering accounts and this account not in filter
        if accounts_filter and account_name not in accounts_filter:
            continue

        # Load retail order CSV (may be nested in subdirectory)
        retail_csv_pattern = "**/Retail.OrderHistory.*.csv"
        retail_csv_files = list(account_dir.glob(retail_csv_pattern))

        if not retail_csv_files:
            continue

        # Load the retail CSV file (take first if multiple)
        retail_csv = retail_csv_files[0]
        try:
            # Load CSV with pandas to get parsed dates
            retail_df = pd.read_csv(retail_csv, parse_dates=["Order Date", "Ship Date"])

            # Convert each row to AmazonOrderItem
            order_items: list[AmazonOrderItem] = []
            for _, row in retail_df.iterrows():
                try:
                    item = AmazonOrderItem.from_csv_row(row.to_dict())
                    order_items.append(item)
                except (ValueError, KeyError, TypeError) as e:
                    logger.warning("Failed to parse row in %s: %s", retail_csv, e)
                    continue

            if order_items:
                orders_by_account[account_name] = order_items

        except (pd.errors.ParserError, FileNotFoundError, ValueError) as e:
            logger.warning("Failed to load %s: %s", retail_csv, e)
            continue

    if not orders_by_account:
        raise FileNotFoundError(
            f"No valid Amazon account data found in {data_dir}"
            + (f" for accounts: {list(accounts_filter)}" if accounts_filter else "")
        )

    return orders_by_account
