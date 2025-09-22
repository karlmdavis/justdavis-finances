"""
Core Utilities Package

Shared business logic, data models, and utilities used across all financial domains.

This package provides:
- Currency handling with integer arithmetic for precision
- Common data models for transactions, receipts, and financial entities
- Configuration management for environment-specific settings
- Shared utilities for data validation and processing
"""

from .currency import (
    milliunits_to_cents,
    cents_to_milliunits,
    cents_to_dollars_str,
    safe_currency_to_cents,
    parse_dollars_to_cents,
    format_cents,
    format_milliunits,
    validate_sum_equals_total,
    allocate_remainder,
)

from .models import (
    Transaction,
    Receipt,
    MatchResult,
    Account,
    Category,
    ProcessingResult,
    TransactionType,
    MatchConfidence,
    validate_transaction,
    validate_receipt,
    validate_match_result,
)

from .config import (
    Config,
    Environment,
    get_config,
    reload_config,
    get_data_dir,
    get_cache_dir,
    get_output_dir,
    is_development,
    is_test,
    is_production,
)

__all__ = [
    # Currency utilities
    "milliunits_to_cents",
    "cents_to_milliunits",
    "cents_to_dollars_str",
    "safe_currency_to_cents",
    "parse_dollars_to_cents",
    "format_cents",
    "format_milliunits",
    "validate_sum_equals_total",
    "allocate_remainder",

    # Data models
    "Transaction",
    "Receipt",
    "MatchResult",
    "Account",
    "Category",
    "ProcessingResult",
    "TransactionType",
    "MatchConfidence",
    "validate_transaction",
    "validate_receipt",
    "validate_match_result",

    # Configuration
    "Config",
    "Environment",
    "get_config",
    "reload_config",
    "get_data_dir",
    "get_cache_dir",
    "get_output_dir",
    "is_development",
    "is_test",
    "is_production",
]