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
)
from .loader import (
    find_latest_amazon_export,
    load_orders,
)
from .matcher import (
    SimplifiedMatcher,
)
from .models import (
    AmazonMatch,
    AmazonMatchResult,
    AmazonOrderItem,
    AmazonOrderSummary,
    MatchedOrderItem,
    OrderGroup,
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
    "AmazonMatch",
    "AmazonMatchResult",
    "AmazonOrderItem",
    "AmazonOrderSummary",
    "ConfidenceThresholds",
    "GroupingLevel",
    "MatchScorer",
    "MatchType",
    "MatchedOrderItem",
    "OrderGroup",
    "SimplifiedMatcher",
    "SplitPaymentMatcher",
    "find_latest_amazon_export",
    "group_orders",
    "load_orders",
]
