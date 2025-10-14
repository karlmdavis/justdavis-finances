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

from .loader import (
    filter_transactions,
    filter_transactions_by_payee,
    load_accounts,
    load_categories,
    load_category_groups,
    load_transactions,
    load_ynab_accounts,
    load_ynab_categories,
    load_ynab_transactions,
)
from .models import (
    YnabAccount,
    YnabCategory,
    YnabCategoryGroup,
    YnabSubtransaction,
    YnabTransaction,
)
from .retirement import (
    RetirementAccount,
    YnabRetirementService,
    discover_retirement_accounts,
    generate_retirement_edits,
)
from .split_calculator import (
    SplitCalculationError,
    calculate_amazon_splits,
    calculate_apple_splits,
    calculate_generic_splits,
    create_split_summary,
    sort_splits_for_stability,
    validate_split_calculation,
)

__all__ = [
    # Domain models (NEW)
    "YnabAccount",
    "YnabCategory",
    "YnabCategoryGroup",
    "YnabSubtransaction",
    "YnabTransaction",
    # Retirement management
    "RetirementAccount",
    "YnabRetirementService",
    "discover_retirement_accounts",
    "generate_retirement_edits",
    # Split calculation
    "SplitCalculationError",
    "calculate_amazon_splits",
    "calculate_apple_splits",
    "calculate_generic_splits",
    "create_split_summary",
    "sort_splits_for_stability",
    "validate_split_calculation",
    # Data loading (NEW domain model functions)
    "filter_transactions_by_payee",
    "load_accounts",
    "load_categories",
    "load_category_groups",
    "load_transactions",
    # Data loading (DEPRECATED - use domain model functions above)
    "filter_transactions",
    "load_ynab_accounts",
    "load_ynab_categories",
    "load_ynab_transactions",
]
