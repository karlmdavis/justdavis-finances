#!/usr/bin/env python3
"""
Cash Flow Analysis Flow Node

Flow node implementation for cash flow analysis and dashboard generation.
"""

from pathlib import Path

from ..core.flow import FlowContext, FlowNode, FlowResult, NodeDataSummary


class CashFlowAnalysisFlowNode(FlowNode):
    """Generate cash flow analysis charts and dashboards."""

    def __init__(self, data_dir: Path):
        super().__init__("cash_flow_analysis")
        self.data_dir = data_dir
        self._dependencies = {"ynab_sync"}

        # Initialize DataStore
        from .datastore import CashFlowResultsStore

        self.store = CashFlowResultsStore(data_dir / "cash_flow" / "charts")

    def check_changes(self, context: FlowContext) -> tuple[bool, list[str]]:
        """Check if cash flow analysis needs updating."""
        ynab_cache = self.data_dir / "ynab" / "cache" / "transactions.json"

        if not ynab_cache.exists():
            return False, ["No YNAB cache available"]

        if not self.store.exists():
            return True, ["No cash flow charts found"]

        # Check if YNAB data is newer than charts
        latest_chart_time = self.store.last_modified()
        ynab_mtime = ynab_cache.stat().st_mtime

        if latest_chart_time and ynab_mtime > latest_chart_time.timestamp():
            return True, ["YNAB data updated since last analysis"]

        # Check if charts are more than 7 days old
        age_days = self.store.age_days()
        if age_days and age_days > 7:
            return True, [f"Charts are {age_days} days old"]

        return False, ["Cash flow analysis is up to date"]

    def get_data_summary(self, context: FlowContext) -> NodeDataSummary:
        """Get cash flow analysis summary."""
        return self.store.to_node_data_summary()

    def execute(self, context: FlowContext) -> FlowResult:
        """Execute cash flow analysis and generate dashboard."""
        from ..analysis.cash_flow import CashFlowAnalyzer

        try:
            # Initialize analyzer
            ynab_cache_dir = self.data_dir / "ynab" / "cache"
            output_dir = self.data_dir / "cash_flow" / "charts"
            output_dir.mkdir(parents=True, exist_ok=True)

            analyzer = CashFlowAnalyzer()

            # Load data
            analyzer.load_data(ynab_cache_dir)

            # Generate dashboard (returns single Path, not list)
            dashboard_file = analyzer.generate_dashboard(output_dir)

            return FlowResult(
                success=True,
                items_processed=1,
                outputs=[dashboard_file],
                metadata={
                    "charts_generated": 1,
                    "output_dir": str(output_dir),
                    "dashboard_file": str(dashboard_file),
                },
            )
        except Exception as e:
            return FlowResult(
                success=False,
                error_message=f"Cash flow analysis failed: {e}",
            )
