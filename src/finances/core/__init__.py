"""
Core Utilities Package

Shared business logic, data models, and utilities used across all financial domains.

This package provides:
- Currency handling with integer arithmetic for precision
- Common data models for transactions, receipts, and financial entities
- Configuration management for environment-specific settings
- Shared utilities for data validation and processing
"""

from .config import (
    Config,
    Environment,
    get_cache_dir,
    get_config,
    get_data_dir,
    get_output_dir,
    is_development,
    is_production,
    is_test,
    reload_config,
)
from .currency import (
    allocate_remainder,
    cents_to_dollars_str,
    cents_to_milliunits,
    format_cents,
    format_milliunits,
    parse_dollars_to_cents,
    safe_currency_to_cents,
    validate_sum_equals_total,
)
from .dates import FinancialDate
from .models import (
    Account,
    Category,
    MatchConfidence,
    MatchResult,
    ProcessingResult,
    Receipt,
    Transaction,
    TransactionType,
    validate_match_result,
    validate_receipt,
    validate_transaction,
)
from .money import Money

__all__ = [
    "Account",
    "Category",
    # Configuration
    "Config",
    "Environment",
    "FinancialDate",
    "MatchConfidence",
    "MatchResult",
    "Money",
    "ProcessingResult",
    "Receipt",
    # Data models
    "Transaction",
    "TransactionType",
    "allocate_remainder",
    "cents_to_dollars_str",
    "cents_to_milliunits",
    "format_cents",
    "format_milliunits",
    "get_cache_dir",
    "get_config",
    "get_data_dir",
    "get_output_dir",
    "is_development",
    "is_production",
    "is_test",
    # Currency utilities
    "parse_dollars_to_cents",
    "reload_config",
    "safe_currency_to_cents",
    "validate_match_result",
    "validate_receipt",
    "validate_sum_equals_total",
    "validate_transaction",
]
