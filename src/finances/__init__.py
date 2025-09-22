"""
Davis Family Finances - Professional Financial Management System

A comprehensive system for automated transaction matching, receipt processing,
and financial analysis with YNAB integration.

Key Features:
- Amazon transaction matching with 94.7% accuracy
- Apple receipt processing with email integration
- YNAB API integration for automatic categorization
- Cash flow analysis and reporting
- Multi-account household support

Domain Packages:
- core: Currency handling, data models, configuration
- amazon: Amazon transaction matching system
- apple: Apple receipt processing and matching
- ynab: YNAB API integration and transaction updates
- analysis: Financial analysis and reporting tools (future)
- cli: Command-line interfaces (future)

Example Usage:
    from finances.amazon import SimplifiedMatcher
    from finances.apple import AppleMatcher
    from finances.core.currency import milliunits_to_cents
    from finances.ynab import calculate_amazon_splits

Version: 0.2.0 (Package Restructure)
"""

__version__ = "0.2.0"
__author__ = "Karl Davis"

# Export core utilities for easy access
from .core.currency import (
    milliunits_to_cents,
    cents_to_milliunits,
    cents_to_dollars_str,
    safe_currency_to_cents,
)

# Export key domain functionality
from .core.models import Transaction, Receipt, MatchResult
from .core.config import get_config, Environment

__all__ = [
    # Core currency functions
    "milliunits_to_cents",
    "cents_to_milliunits",
    "cents_to_dollars_str",
    "safe_currency_to_cents",

    # Core models
    "Transaction",
    "Receipt",
    "MatchResult",

    # Configuration
    "get_config",
    "Environment",
]