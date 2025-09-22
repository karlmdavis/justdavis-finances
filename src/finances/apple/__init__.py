"""
Apple Transaction Matching Package

Automated matching of Apple receipt data to YNAB transactions with high accuracy.

This package provides:
- 2-strategy matching system optimized for Apple's 1:1 transaction model
- Apple receipt loading and normalization from email extracts
- Date and amount-based matching with confidence scoring
- Multi-Apple ID support for household accounts
- Simplified matching logic leveraging Apple's direct transaction model

Key Components:
- loader: Apple receipt data loading and normalization
- matcher: Core transaction matching logic

Current Performance: 85.1% match rate with 0.871 average confidence
"""

from .loader import (
    find_latest_apple_export,
    load_apple_receipts,
    normalize_apple_receipt_data,
    parse_apple_date,
    filter_receipts_by_date_range,
    get_apple_receipt_summary,
)

from .matcher import (
    MatchStrategy,
    AppleMatcher,
    batch_match_transactions,
    generate_match_summary,
)

__all__ = [
    # Receipt loading
    "find_latest_apple_export",
    "load_apple_receipts",
    "normalize_apple_receipt_data",
    "parse_apple_date",
    "filter_receipts_by_date_range",
    "get_apple_receipt_summary",

    # Transaction matching
    "MatchStrategy",
    "AppleMatcher",
    "batch_match_transactions",
    "generate_match_summary",
]