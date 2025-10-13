#!/usr/bin/env python3
"""
Flow CLI - Financial Flow System Execution

Professional command-line interface for orchestrating the complete Financial
Flow System with dependency resolution and change detection.
"""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

import click

from ..core.archive import create_flow_archive
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
    flow_registry.register_node(AmazonOrderHistoryRequestFlowNode())
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
    config = get_config()

    # Setup flow nodes
    setup_flow_nodes()

    # Create flow context
    flow_context = FlowContext(start_time=datetime.now())

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

        # Detect initial changes for preview
        all_nodes = set(flow_registry.get_all_nodes().keys())

        changes = engine.detect_changes(flow_context, all_nodes)
        initially_changed = set()
        change_summary = {}

        for node_name, (has_changes, reasons) in changes.items():
            if has_changes:
                initially_changed.add(node_name)
                change_summary[node_name] = reasons

        potential_nodes = engine.dependency_graph.find_changed_subgraph(initially_changed)

        if not potential_nodes:
            click.echo("✅ No nodes need execution (no changes detected)")
            return

        click.echo(
            f"Dynamic execution will process up to {len(potential_nodes)} nodes as dependencies allow:"
        )

        # Show initially changed nodes
        if initially_changed:
            click.echo("\nInitially triggered nodes:")
            for node_name in sorted(initially_changed):
                node = flow_registry.get_node(node_name)
                display_name = node.get_display_name() if node is not None else node_name
                click.echo(f"  • {display_name}")
                if node_name in change_summary:
                    for reason in change_summary[node_name]:
                        click.echo(f"    - {reason}")

        # Show potentially affected nodes
        downstream_nodes = potential_nodes - initially_changed
        if downstream_nodes:
            click.echo(f"\nPotentially affected downstream nodes: {len(downstream_nodes)}")

        # Confirm execution
        if not click.confirm("\nProceed with dynamic execution?"):
            click.echo("Execution cancelled.")
            return

        # Create transaction archive
        click.echo("\n📦 Creating transaction archive...")
        try:
            archive_session = create_flow_archive(
                config.data_dir,
                "flow_execution",
                flow_context={
                    "execution_order": list(potential_nodes),
                    "change_summary": change_summary,
                },
            )
            flow_context.archive_manifest = {
                domain: Path(manifest.archive_path) for domain, manifest in archive_session.archives.items()
            }
            click.echo(
                f"✅ Archive created: {archive_session.total_files} files, {archive_session.total_size_bytes:,} bytes"
            )
        except Exception as e:
            if not click.confirm(f"Archive creation failed: {e}\nContinue without archive?"):
                raise click.ClickException("Execution aborted due to archive failure") from e

        # Execute flow
        click.echo("\n🚀 Executing flow...")
        start_time = datetime.now()

        executions = engine.execute_flow(flow_context)

        end_time = datetime.now()
        total_time = (end_time - start_time).total_seconds()

        # Display results
        click.echo("\n" + "=" * 50)
        click.echo("EXECUTION SUMMARY")
        click.echo("=" * 50)

        summary = engine.get_execution_summary(executions)

        click.echo(f"Total nodes: {summary['total_nodes']}")
        click.echo(f"Completed: {summary['completed']}")
        click.echo(f"Failed: {summary['failed']}")
        click.echo(f"Skipped: {summary['skipped']}")
        click.echo(f"Success rate: {summary['success_rate']:.1%}")
        click.echo(f"Total execution time: {total_time:.1f} seconds")

        # Show archive information
        if archive_session:
            click.echo(f"\n📦 Archive batch: {archive_session.session_id}")
            click.echo(f"Separate archives created for {len(archive_session.archives)} domains:")
            for domain, manifest in archive_session.archives.items():
                click.echo(
                    f"  • {domain}: {manifest.files_archived} files ({manifest.archive_size_bytes:,} bytes)"
                )

        # Show review items
        review_items = [
            execution
            for execution in executions.values()
            if execution.result and execution.result.requires_review
        ]

        if review_items:
            click.echo("\n🔍 Items requiring review:")
            for execution in review_items:
                click.echo(f"  • {execution.node_name}")
                if execution.result and execution.result.review_instructions:
                    click.echo(f"    {execution.result.review_instructions}")

        # Final status
        if summary["failed"] > 0:
            click.echo("\n⚠️ Flow completed with errors")
            exit_code = 1
        else:
            click.echo("\n✅ Flow completed successfully")
            exit_code = 0

        exit(exit_code)

    except Exception as e:
        click.echo(f"\n❌ Flow execution failed: {e}", err=True)
        raise click.ClickException(str(e)) from e


if __name__ == "__main__":
    flow()
