"""
Apple Transaction Processing Package

Advanced Apple receipt processing and transaction matching with email integration.

This package provides:
- Apple receipt data loading from exported files
- Transaction matching with confidence scoring using 2-strategy system
- Email integration for direct receipt extraction
- Receipt parsing from HTML emails with multiple format support
- 1:1 transaction model optimized for Apple's billing structure

Key Components:
- loader: Apple receipt data loading and normalization
- matcher: Transaction matching with exact + date window strategies
- parser: HTML receipt parsing with format detection
- email_fetcher: IMAP-based email fetching for receipt extraction

Apple's simplified transaction model enables direct matching with high success rates.
Unlike Amazon's complex bundling, Apple typically has 1:1 correspondence between
receipts and credit card transactions.

Transaction Matching Features:
- Exact Match Strategy: Same date + exact amount (confidence 1.0)
- Date Window Strategy: ±1-2 days with exact amount (confidence 0.75-0.90)
- Multi-Apple ID Support: Handles family accounts with proper attribution
- High Performance: ~0.005 seconds per transaction
- Current Success Rate: 85.1% match rate with 0.871 average confidence

Receipt Processing Features:
- Multi-format HTML parsing (legacy aapl-*, modern custom-*, table-based)
- Email fetching with IMAP support and secure authentication
- Robust data extraction with fallback strategies
- Financial precision with currency handling
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

from .parser import (
    AppleReceiptParser,
    ParsedReceipt,
    ParsedItem,
)

from .email_fetcher import (
    AppleEmailFetcher,
    AppleReceiptEmail,
    EmailConfig,
    fetch_apple_receipts_cli,
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

    # Receipt parsing
    "AppleReceiptParser",
    "ParsedReceipt",
    "ParsedItem",

    # Email fetching
    "AppleEmailFetcher",
    "AppleReceiptEmail",
    "EmailConfig",
    "fetch_apple_receipts_cli",
]