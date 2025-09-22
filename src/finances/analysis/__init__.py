"""
Financial Analysis Package

Comprehensive financial analysis tools including cash flow analysis,
trend detection, and statistical reporting.

Key Components:
- cash_flow: Cash flow analysis and visualization
- reports: Financial report generation
- statistics: Statistical analysis utilities

Features:
- Multiple moving averages for smoothing volatility
- Trend analysis with statistical confidence
- Monthly aggregation and burn rate calculation
- Account composition tracking over time
- Comprehensive dashboard generation
"""

from .cash_flow import CashFlowAnalyzer, CashFlowConfig

__all__ = [
    "CashFlowAnalyzer",
    "CashFlowConfig",
]