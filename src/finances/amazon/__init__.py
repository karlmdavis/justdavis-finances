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
    get_order_candidates,
    group_orders,
)
from .matcher import (
    SimplifiedMatcher,
)
from .scorer import (
    ConfidenceThresholds,
    MatchScorer,
    MatchType,
)
from .split_matcher import (
    SplitPaymentMatcher,
)

__all__ = [
    "ConfidenceThresholds",
    # Order grouping
    "GroupingLevel",
    "MatchScorer",
    # Match scoring
    "MatchType",
    # Main matcher
    "SimplifiedMatcher",
    # Split payment matching
    "SplitPaymentMatcher",
    "get_order_candidates",
    "group_orders",
]
