#!/usr/bin/env python3
"""
Cash Flow Analysis Flow Node

Flow node implementation for cash flow analysis and dashboard generation.
"""

from pathlib import Path

from ..core.flow import FlowContext, FlowNode, FlowResult, NodeDataSummary, OutputFile, OutputInfo


class CashFlowAnalysisOutputInfo(OutputInfo):
    """Output information for cash flow analysis node."""

    def __init__(self, output_dir: Path):
        self.output_dir = output_dir

    def is_data_ready(self) -> bool:
        """Ready if at least 1 chart file exists."""
        if not self.output_dir.exists():
            return False

        # Check for chart files (.png)
        return len(list(self.output_dir.glob("*.png"))) >= 1

    def get_output_files(self) -> list[OutputFile]:
        """Return chart PNG files."""
        if not self.output_dir.exists():
            return []

        # Each chart is 1 record
        return [OutputFile(path=png_file, record_count=1) for png_file in self.output_dir.glob("*.png")]


class CashFlowAnalysisFlowNode(FlowNode):
    """Generate cash flow analysis charts and dashboards."""

    def __init__(self, data_dir: Path):
        super().__init__("cash_flow_analysis")
        self.data_dir = data_dir
        self._dependencies = {"ynab_sync"}

        # Initialize DataStore
        from .datastore import CashFlowResultsStore

        self.store = CashFlowResultsStore(data_dir / "cash_flow" / "charts")

    def get_output_info(self) -> OutputInfo:
        """Get output information for cash flow analysis node."""
        return CashFlowAnalysisOutputInfo(self.data_dir / "cash_flow" / "charts")

    def get_output_dir(self) -> Path | None:
        """Return cash flow analysis output directory."""
        return self.data_dir / "cash_flow" / "charts"

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

            # Display report with clickable file link (iTerm2 compatible)
            import click

            click.echo("\n📈 Cash Flow Analysis Report Generated")
            click.echo("=" * 60)
            click.echo("\nDashboard file:")
            # Use file:// URL which iTerm2 recognizes for cmd+click
            file_url = f"file://{dashboard_file.resolve()}"
            click.echo(f"  {dashboard_file.name}")
            click.echo(f"  Location: {file_url}")
            click.echo("\n💡 Tip: Cmd+click the path to open in default app")
            click.echo("=" * 60)

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
            import logging
            import traceback

            logger = logging.getLogger(__name__)
            logger.error(f"Cash flow analysis failed: {e}")
            logger.error(f"Traceback:\n{traceback.format_exc()}")

            return FlowResult(
                success=False,
                error_message=f"Cash flow analysis failed: {e}",
            )
