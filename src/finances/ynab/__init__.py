"""
YNAB Integration Package

Secure integration with YNAB API for transaction updates and data caching.

This package provides:
- YNAB API client with authentication and error handling
- Local data caching for performance and offline operation
- Three-phase edit workflow (generate → review → apply)
- Transaction splitting with item-level memos
- Retirement account balance management
- Audit trail for all changes with reversibility

Key Components:
- split_calculator: Transaction splitting with tax allocation
- retirement: Retirement account discovery and balance adjustments
- edits: Edit generation, review, and execution
- client: YNAB API integration (future)
- cache: Local data storage and synchronization (future)

Safety Features:
- Dry-run mode for testing changes
- Complete audit trail with delete logging
- Confidence thresholds for automatic approval
- Manual review workflow for complex cases
"""

from .split_calculator import (
    calculate_amazon_splits,
    calculate_apple_splits,
    calculate_generic_splits,
    validate_split_calculation,
    sort_splits_for_stability,
    create_split_summary,
    SplitCalculationError,
)

from .retirement import (
    YnabRetirementService,
    RetirementAccount,
    discover_retirement_accounts,
    generate_retirement_edits,
)

__all__ = [
    # Split calculation
    "calculate_amazon_splits",
    "calculate_apple_splits",
    "calculate_generic_splits",
    "validate_split_calculation",
    "sort_splits_for_stability",
    "create_split_summary",
    "SplitCalculationError",
    # Retirement management
    "YnabRetirementService",
    "RetirementAccount",
    "discover_retirement_accounts",
    "generate_retirement_edits",
]