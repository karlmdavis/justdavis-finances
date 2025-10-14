#!/usr/bin/env python3
"""
YNAB Data Loader

Utilities for loading cached YNAB data (accounts, categories, transactions)
from local JSON files.

Functions:
- load_transactions: Load transactions as domain models
- load_accounts: Load accounts as domain models
- load_categories: Load categories as domain models
- load_category_groups: Load category groups as domain models
- filter_transactions_by_payee: Filter transactions by payee
"""

import json
from pathlib import Path
from typing import Any

from ..core.config import get_config
from .models import YnabAccount, YnabCategory, YnabCategoryGroup, YnabTransaction


def load_transactions(cache_dir: str | Path | None = None) -> list[YnabTransaction]:
    """
    Load YNAB transactions from cache as domain models.

    Args:
        cache_dir: Directory containing cached YNAB data.
                   If None, uses config.data_dir/ynab/cache

    Returns:
        List of YnabTransaction domain models

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
    elif isinstance(data, list):
        transactions_list = data
    else:
        transactions_list = []

    # Convert dicts to domain models
    return [YnabTransaction.from_dict(tx) for tx in transactions_list]


def load_accounts(cache_dir: str | Path | None = None) -> list[YnabAccount]:
    """
    Load YNAB accounts from cache as domain models.

    Args:
        cache_dir: Directory containing cached YNAB data.
                   If None, uses config.data_dir/ynab/cache

    Returns:
        List of YnabAccount domain models

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
    elif isinstance(data, list):
        accounts_list = data
    else:
        accounts_list = []

    # Convert dicts to domain models
    return [YnabAccount.from_dict(acct) for acct in accounts_list]


def load_category_groups(cache_dir: str | Path | None = None) -> list[YnabCategoryGroup]:
    """
    Load YNAB category groups from cache as domain models.

    Args:
        cache_dir: Directory containing cached YNAB data.
                   If None, uses config.data_dir/ynab/cache

    Returns:
        List of YnabCategoryGroup domain models

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
        groups_list: list[dict[str, Any]] = data["category_groups"]
    elif isinstance(data, list):
        groups_list = data
    else:
        groups_list = []

    # Convert dicts to domain models
    return [YnabCategoryGroup.from_dict(group) for group in groups_list]


def load_categories(cache_dir: str | Path | None = None) -> list[YnabCategory]:
    """
    Load YNAB categories from cache as domain models.

    Flattens category groups into a single list of categories with their group information.

    Args:
        cache_dir: Directory containing cached YNAB data.
                   If None, uses config.data_dir/ynab/cache

    Returns:
        List of YnabCategory domain models

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
        groups_list: list[dict[str, Any]] = data["category_groups"]
    elif isinstance(data, list):
        groups_list = data
    else:
        groups_list = []

    # Flatten categories from all groups
    all_categories: list[YnabCategory] = []
    for group in groups_list:
        group_name = group.get("name")
        categories_in_group = group.get("categories", [])
        all_categories.extend(
            YnabCategory.from_dict(cat, category_group_name=group_name) for cat in categories_in_group
        )

    return all_categories


def filter_transactions_by_payee(
    transactions: list[YnabTransaction],
    payee: str | None = None,
) -> list[YnabTransaction]:
    """
    Filter transactions by payee name.

    Args:
        transactions: List of YnabTransaction domain models
        payee: Payee name pattern (case-insensitive substring match)

    Returns:
        Filtered list of transactions
    """
    if not payee:
        return transactions

    payee_lower = payee.lower()
    return [tx for tx in transactions if tx.payee_name and payee_lower in tx.payee_name.lower()]
