#!/usr/bin/env python3
"""
Flow CLI - Financial Flow System Execution

Professional command-line interface for orchestrating the complete Financial
Flow System with dependency resolution and change detection.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import TYPE_CHECKING

import click

from ..core.config import get_config
from ..core.flow import FlowContext, FlowResult, flow_registry
from ..core.flow_engine import FlowExecutionEngine

if TYPE_CHECKING:
    from ..core.flow import FlowResult

logger = logging.getLogger(__name__)


def setup_flow_nodes() -> None:
    """
    Register all flow nodes with their dependencies.

    Discovers and registers FlowNode instances from domain modules.
    """
    config = get_config()

    # Import FlowNode classes from domain modules
    from ..amazon.flow import (
        AmazonMatchingFlowNode,
        AmazonOrderHistoryRequestFlowNode,
        AmazonUnzipFlowNode,
    )
    from ..analysis.flow import CashFlowAnalysisFlowNode
    from ..apple.flow import (
        AppleEmailFetchFlowNode,
        AppleMatchingFlowNode,
        AppleReceiptParsingFlowNode,
    )
    from ..ynab.flow import RetirementUpdateFlowNode, YnabSyncFlowNode
    from ..ynab.split_generation_flow import SplitGenerationFlowNode

    # Register nodes from domain modules
    flow_registry.register_node(YnabSyncFlowNode(config.data_dir))
    flow_registry.register_node(AmazonOrderHistoryRequestFlowNode(config.data_dir))
    flow_registry.register_node(AmazonUnzipFlowNode(config.data_dir))
    flow_registry.register_node(AmazonMatchingFlowNode(config.data_dir))
    flow_registry.register_node(AppleEmailFetchFlowNode(config.data_dir))
    flow_registry.register_node(AppleReceiptParsingFlowNode(config.data_dir))
    flow_registry.register_node(AppleMatchingFlowNode(config.data_dir))
    flow_registry.register_node(SplitGenerationFlowNode(config.data_dir))
    flow_registry.register_node(RetirementUpdateFlowNode(config.data_dir))
    flow_registry.register_node(CashFlowAnalysisFlowNode(config.data_dir))

    # YNAB apply: applies generated splits (manual step)
    def ynab_apply_executor(context: FlowContext) -> FlowResult:
        """Apply YNAB edits."""
        # For now, just inform user about manual step
        edit_dir = config.data_dir / "ynab" / "edits"
        edit_files = list(edit_dir.glob("*.json")) if edit_dir.exists() else []

        if not edit_files:
            return FlowResult(success=True, items_processed=0, metadata={"note": "No edits to apply"})

        return FlowResult(
            success=True,
            items_processed=len(edit_files),
            requires_review=True,
            review_instructions=f"Review and manually apply {len(edit_files)} edit file(s) in {edit_dir}",
        )

    flow_registry.register_function_node(
        name="ynab_apply",
        func=ynab_apply_executor,
        dependencies=["split_generation"],
    )

    logger.info(f"Registered {len(flow_registry.get_all_nodes())} flow nodes")


@click.command()
def flow() -> None:
    """
    Execute the Financial Flow System.

    Guides you through each data update step with interactive prompts.
    Each node will display its current data summary and ask if you want to update.

    Example:

      finances flow    # Execute the flow with interactive prompts
    """
    # Setup flow nodes
    setup_flow_nodes()

    try:
        # Initialize execution engine
        engine = FlowExecutionEngine()

        # Validate flow
        validation_errors = engine.validate_flow()
        if validation_errors:
            click.echo("❌ Flow validation failed:")
            for error in validation_errors:
                click.echo(f"  • {error}")
            raise click.ClickException("Cannot execute invalid flow")

        # Execute flow with interactive prompts
        click.echo("\n🚀 Starting flow execution...")
        click.echo("You will be prompted for each step.\n")
        start_time = datetime.now()

        engine.execute_flow()

        end_time = datetime.now()
        total_time = (end_time - start_time).total_seconds()

        # execute_flow() already prints its own execution summary
        # Just display total time
        click.echo(f"\n⏱️  Total execution time: {total_time:.1f} seconds")
        click.echo("\n✅ Flow completed successfully")

    except Exception as e:
        import traceback

        click.echo(f"\n❌ Flow execution failed: {e}", err=True)
        click.echo("\nFull traceback:", err=True)
        click.echo(traceback.format_exc(), err=True)
        raise click.ClickException(str(e)) from e


if __name__ == "__main__":
    flow()
