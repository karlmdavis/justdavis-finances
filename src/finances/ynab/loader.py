#!/usr/bin/env python3
"""
YNAB Data Loader

Utilities for loading cached YNAB data (accounts, categories, transactions)
from local JSON files.

Functions:
- load_ynab_transactions: Load transactions from cache
- load_ynab_accounts: Load accounts from cache
- load_ynab_categories: Load category groups from cache
- filter_transactions: Filter transactions by date range and criteria
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from ..core.config import get_config


def load_ynab_transactions(cache_dir: str | Path | None = None) -> list[dict[str, Any]]:
    """
    Load YNAB transactions from cache.

    Args:
        cache_dir: Directory containing cached YNAB data.
                   If None, uses config.data_dir/ynab/cache

    Returns:
        List of transaction dictionaries with fields:
        - id: Transaction ID
        - date: Transaction date (YYYY-MM-DD)
        - amount: Amount in milliunits (1000 = $1.00)
        - payee_name: Payee name
        - account_id: Account ID
        - account_name: Account name (if available)
        - memo: Transaction memo
        - cleared: Transaction cleared status

    Raises:
        FileNotFoundError: If cache directory or transactions file not found
    """
    if cache_dir is None:
        config = get_config()
        cache_dir = config.data_dir / "ynab" / "cache"
    else:
        cache_dir = Path(cache_dir)

    transactions_file = cache_dir / "transactions.json"

    if not transactions_file.exists():
        raise FileNotFoundError(f"YNAB transactions cache not found: {transactions_file}")

    with open(transactions_file) as f:
        data: Any = json.load(f)

    # Handle both array format and object format
    if isinstance(data, dict):
        transactions_list: list[dict[str, Any]] = data.get("transactions", [])
        return transactions_list

    return data if isinstance(data, list) else []


def load_ynab_accounts(cache_dir: str | Path | None = None) -> list[dict[str, Any]]:
    """
    Load YNAB accounts from cache.

    Args:
        cache_dir: Directory containing cached YNAB data.
                   If None, uses config.data_dir/ynab/cache

    Returns:
        List of account dictionaries

    Raises:
        FileNotFoundError: If cache directory or accounts file not found
    """
    if cache_dir is None:
        config = get_config()
        cache_dir = config.data_dir / "ynab" / "cache"
    else:
        cache_dir = Path(cache_dir)

    accounts_file = cache_dir / "accounts.json"

    if not accounts_file.exists():
        raise FileNotFoundError(f"YNAB accounts cache not found: {accounts_file}")

    with open(accounts_file) as f:
        data: Any = json.load(f)

    # Handle object format with "accounts" key
    if isinstance(data, dict) and "accounts" in data:
        accounts_list: list[dict[str, Any]] = data["accounts"]
        return accounts_list

    return data if isinstance(data, list) else []


def load_ynab_categories(cache_dir: str | Path | None = None) -> list[dict[str, Any]]:
    """
    Load YNAB category groups from cache.

    Args:
        cache_dir: Directory containing cached YNAB data.
                   If None, uses config.data_dir/ynab/cache

    Returns:
        List of category group dictionaries

    Raises:
        FileNotFoundError: If cache directory or categories file not found
    """
    if cache_dir is None:
        config = get_config()
        cache_dir = config.data_dir / "ynab" / "cache"
    else:
        cache_dir = Path(cache_dir)

    categories_file = cache_dir / "categories.json"

    if not categories_file.exists():
        raise FileNotFoundError(f"YNAB categories cache not found: {categories_file}")

    with open(categories_file) as f:
        data: Any = json.load(f)

    # Handle object format with "category_groups" key
    if isinstance(data, dict) and "category_groups" in data:
        categories_list: list[dict[str, Any]] = data["category_groups"]
        return categories_list

    return data if isinstance(data, list) else []


def filter_transactions(
    transactions: list[dict[str, Any]],
    start_date: str | None = None,
    end_date: str | None = None,
    payee: str | None = None,
) -> list[dict[str, Any]]:
    """
    Filter transactions by date range and/or payee name.

    Args:
        transactions: List of transaction dictionaries
        start_date: Start date in YYYY-MM-DD format (inclusive)
        end_date: End date in YYYY-MM-DD format (inclusive)
        payee: Payee name pattern (case-insensitive substring match)

    Returns:
        Filtered list of transactions
    """
    filtered = transactions

    # Filter by date range
    if start_date:
        start_dt = datetime.strptime(start_date, "%Y-%m-%d").date()
        filtered = [tx for tx in filtered if datetime.strptime(tx["date"], "%Y-%m-%d").date() >= start_dt]

    if end_date:
        end_dt = datetime.strptime(end_date, "%Y-%m-%d").date()
        filtered = [tx for tx in filtered if datetime.strptime(tx["date"], "%Y-%m-%d").date() <= end_dt]

    # Filter by payee
    if payee:
        payee_lower = payee.lower()
        filtered = [tx for tx in filtered if payee_lower in tx.get("payee_name", "").lower()]

    return filtered
