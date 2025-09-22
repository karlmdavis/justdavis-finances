"""
Amazon Transaction Matching Package

Automated matching of Amazon order data to YNAB transactions with high accuracy.

This package provides:
- Order grouping at multiple levels (complete orders, shipments, daily)
- 3-strategy matching system (Complete Match, Split Payment, Fuzzy Match)
- Confidence scoring with precise date and amount calculations
- Multi-account support for household Amazon accounts
- Split payment handling for partial order matches

Key Components:
- grouper: Order grouping functionality
- scorer: Match confidence calculation
- split_matcher: Split payment handling

Current Performance: 94.7% match rate with simplified architecture
"""

from .grouper import (
    GroupingLevel,
    group_orders,
    get_order_candidates,
)

from .scorer import (
    MatchType,
    MatchScorer,
    ConfidenceThresholds,
)

from .split_matcher import (
    SplitPaymentMatcher,
)

from .matcher import (
    SimplifiedMatcher,
)

__all__ = [
    # Order grouping
    "GroupingLevel",
    "group_orders",
    "get_order_candidates",

    # Match scoring
    "MatchType",
    "MatchScorer",
    "ConfidenceThresholds",

    # Split payment matching
    "SplitPaymentMatcher",

    # Main matcher
    "SimplifiedMatcher",
]