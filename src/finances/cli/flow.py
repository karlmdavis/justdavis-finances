#!/usr/bin/env python3
"""
Flow CLI - Financial Flow System Execution

Professional command-line interface for orchestrating the complete Financial
Flow System with dependency resolution and change detection.
"""

import click
import json
import yaml
from datetime import datetime, date
from pathlib import Path
from typing import Optional, Set
import logging

from ..core.config import get_config
from ..core.flow import FlowContext, flow_registry
from ..core.flow_engine import FlowExecutionEngine
from ..core.archive import create_flow_archive
from ..core.change_detection import create_change_detectors, get_change_detector_function
from ..core.currency import format_cents

logger = logging.getLogger(__name__)


@click.group()
def flow():
    """Financial Flow System orchestration commands."""
    pass


def safe_get_callable_name(obj):
    """
    Safely extract a name from any callable object.

    Handles functions, Click Command objects, and other callables.

    Args:
        obj: Any callable object

    Returns:
        str: Best available name for the callable
    """
    if hasattr(obj, '__name__'):
        return obj.__name__
    elif hasattr(obj, 'name'):
        return obj.name
    else:
        return obj.__class__.__name__


def setup_flow_nodes():
    """
    Register all flow nodes with their dependencies and change detectors.

    This function configures the complete flow system by registering nodes
    and their change detection logic.
    """
    config = get_config()
    change_detectors = create_change_detectors(config.data_dir)

    # Import CLI command functions for real implementations
    from .ynab import sync_cache as ynab_sync_cmd
    from .amazon import unzip as amazon_unzip_cmd, match as amazon_match_cmd
    from .apple import fetch_emails as apple_fetch_cmd, parse_receipts as apple_parse_cmd, match as apple_match_cmd
    from .ynab import generate_splits as ynab_splits_cmd, apply_edits as ynab_apply_cmd
    from .retirement import update as retirement_update_cmd
    from .cashflow import analyze as cashflow_analyze_cmd

    def create_cli_executor(cli_func, **default_kwargs):
        """
        Create a flow executor that wraps a CLI command function.

        Args:
            cli_func: The CLI command function to execute
            **default_kwargs: Default parameters to pass to the CLI function
        """
        def executor(context: FlowContext):
            from ..core.flow import FlowResult
            try:
                # Create a mock click context for the CLI function
                import click
                from types import SimpleNamespace

                # Create mock context object
                mock_ctx = click.Context(cli_func)
                mock_ctx.obj = {
                    'verbose': context.verbose,
                    'config': config
                }

                # Merge flow context parameters with defaults
                kwargs = default_kwargs.copy()
                if context.date_range:
                    start_date, end_date = context.date_range
                    if start_date:
                        kwargs['start'] = start_date.strftime('%Y-%m-%d')
                    if end_date:
                        kwargs['end'] = end_date.strftime('%Y-%m-%d')

                kwargs['verbose'] = context.verbose

                # Execute the CLI function
                cli_name = safe_get_callable_name(cli_func)
                logger.info(f"Executing CLI function: {cli_name}")

                # Direct call approach: call the underlying callable function
                # Most CLI functions are decorated Click commands, we need to get the actual function
                actual_function = cli_func

                # If this is a Click command, get the underlying callback function
                if hasattr(cli_func, 'callback'):
                    actual_function = cli_func.callback

                # Call the function directly with just the kwargs, no context
                # Most CLI functions use the context just to access ctx.obj['verbose'] etc
                # We can simulate this by injecting what they need directly
                if 'ctx' in actual_function.__code__.co_varnames:
                    # Function expects a context parameter
                    result = actual_function(mock_ctx, **kwargs)
                else:
                    # Function doesn't need context
                    result = actual_function(**kwargs)

                return FlowResult(
                    success=True,
                    items_processed=1,  # CLI functions don't return item counts
                    metadata={"cli_function": cli_name, "executed": True}
                )

            except Exception as e:
                cli_name = safe_get_callable_name(cli_func)
                logger.error(f"CLI function {cli_name} failed: {e}")
                return FlowResult(
                    success=False,
                    error_message=str(e),
                    metadata={"cli_function": cli_name, "error": str(e)}
                )

        return executor

    # Register YNAB Sync Node
    flow_registry.register_function_node(
        name="ynab_sync",
        func=create_cli_executor(ynab_sync_cmd, days=30),
        dependencies=[],
        change_detector=get_change_detector_function(change_detectors["ynab_sync"])
    )

    # Register Amazon Order History Request Node (manual step)
    def amazon_order_history_request_executor(context: FlowContext):
        """Manual step - prompts user to download Amazon order history."""
        from ..core.flow import FlowResult
        logger.info("Amazon order history request - manual step")
        if context.interactive:
            import click
            click.echo("\n📋 Manual Step Required:")
            click.echo("1. Visit https://www.amazon.com/gp/privacycentral/dsar/preview.html")
            click.echo("2. Request 'Order Reports' for the desired date range")
            click.echo("3. Download the ZIP files when ready")
            click.echo("4. Place them in your download directory")
            if not click.confirm("Have you completed this step?"):
                return FlowResult(success=False, error_message="User cancelled manual step")

        return FlowResult(
            success=True,
            items_processed=0,
            metadata={"manual_step": True, "description": "Amazon order history request"}
        )

    flow_registry.register_function_node(
        name="amazon_order_history_request",
        func=amazon_order_history_request_executor,
        dependencies=[],
        change_detector=lambda ctx: (False, ["Manual step - user prompt required"])
    )

    # Register Amazon Unzip Node
    def amazon_unzip_executor(context: FlowContext):
        """Execute Amazon unzip with automatic download directory detection."""
        from ..core.flow import FlowResult
        import os
        from pathlib import Path

        # Try to find download directory
        download_dir = Path.home() / "Downloads"
        if not download_dir.exists():
            return FlowResult(
                success=False,
                error_message="Downloads directory not found"
            )

        return create_cli_executor(
            amazon_unzip_cmd,
            download_dir=str(download_dir),
            accounts=()  # All accounts
        )(context)

    flow_registry.register_function_node(
        name="amazon_unzip",
        func=amazon_unzip_executor,
        dependencies=["amazon_order_history_request"],
        change_detector=get_change_detector_function(change_detectors["amazon_unzip"])
    )

    # Register Amazon Matching Node
    flow_registry.register_function_node(
        name="amazon_matching",
        func=create_cli_executor(
            amazon_match_cmd,
            accounts=(),  # All accounts
            disable_split=False,
            output_dir=None
        ),
        dependencies=["ynab_sync", "amazon_unzip"],
        change_detector=get_change_detector_function(change_detectors["amazon_matching"])
    )

    # Register Apple Email Fetch Node
    flow_registry.register_function_node(
        name="apple_email_fetch",
        func=create_cli_executor(
            apple_fetch_cmd,
            days_back=90,
            max_emails=None,
            output_dir=None
        ),
        dependencies=[],
        change_detector=get_change_detector_function(change_detectors["apple_email_fetch"])
    )

    # Register Apple Receipt Parsing Node
    def apple_receipt_parsing_executor(context: FlowContext):
        """Execute Apple receipt parsing using the email fetch output directory."""
        from ..core.flow import FlowResult
        from pathlib import Path

        # Use default Apple email directory
        email_dir = config.data_dir / "apple" / "emails"
        if not email_dir.exists():
            return FlowResult(
                success=False,
                error_message="Apple emails directory not found. Run apple email fetch first."
            )

        return create_cli_executor(
            apple_parse_cmd,
            input_dir=str(email_dir),
            output_dir=None
        )(context)

    flow_registry.register_function_node(
        name="apple_receipt_parsing",
        func=apple_receipt_parsing_executor,
        dependencies=["apple_email_fetch"],
        change_detector=lambda ctx: (True, ["New email directories detected"])
    )

    # Register Apple Matching Node
    flow_registry.register_function_node(
        name="apple_matching",
        func=create_cli_executor(
            apple_match_cmd,
            apple_ids=(),  # All Apple IDs
            output_dir=None
        ),
        dependencies=["ynab_sync", "apple_receipt_parsing"],
        change_detector=get_change_detector_function(change_detectors["apple_matching"])
    )

    # Register Split Generation Node
    def split_generation_executor(context: FlowContext):
        """Generate splits from Amazon, Apple, and retirement updates."""
        from ..core.flow import FlowResult
        from pathlib import Path
        import glob

        # Find the most recent match results files
        data_dir = config.data_dir
        amazon_matches = list((data_dir / "amazon" / "transaction_matches").glob("*.json"))
        apple_matches = list((data_dir / "apple" / "transaction_matches").glob("*.json"))
        # Note: Retirement edits are already in the correct format, no split generation needed
        # They go directly to the edits directory

        results = []

        # Process Amazon matches
        if amazon_matches:
            latest_amazon = max(amazon_matches, key=lambda p: p.stat().st_mtime)
            try:
                result = create_cli_executor(
                    ynab_splits_cmd,
                    input_file=str(latest_amazon),
                    confidence_threshold=0.8,
                    dry_run=False,
                    output_dir=None
                )(context)
                results.append(result)
            except Exception as e:
                logger.warning(f"Failed to generate splits from Amazon matches: {e}")

        # Process Apple matches
        if apple_matches:
            latest_apple = max(apple_matches, key=lambda p: p.stat().st_mtime)
            try:
                result = create_cli_executor(
                    ynab_splits_cmd,
                    input_file=str(latest_apple),
                    confidence_threshold=0.8,
                    dry_run=False,
                    output_dir=None
                )(context)
                results.append(result)
            except Exception as e:
                logger.warning(f"Failed to generate splits from Apple matches: {e}")

        # Retirement edits are generated directly by retirement_update node
        # and placed in data/ynab/edits/, so they're ready for apply_edits

        if not results:
            # This is ok if only retirement was updated
            return FlowResult(
                success=True,
                items_processed=0,
                metadata={"note": "Retirement edits generated separately"}
            )

        # Return success if at least one succeeded
        success = any(r.success for r in results)
        return FlowResult(
            success=success,
            items_processed=len(results),
            metadata={"splits_generated_from": len(results), "sources": ["amazon", "apple", "retirement"]}
        )

    flow_registry.register_function_node(
        name="split_generation",
        func=split_generation_executor,
        dependencies=["amazon_matching", "apple_matching", "retirement_update"],
        change_detector=lambda ctx: (True, ["New match results from upstream"])
    )

    # Register YNAB Apply Node
    def ynab_apply_executor(context: FlowContext):
        """Apply the most recent YNAB edit files."""
        from ..core.flow import FlowResult
        from pathlib import Path

        # Find the most recent edit files
        edit_dir = config.data_dir / "ynab" / "edits"
        if not edit_dir.exists():
            return FlowResult(
                success=False,
                error_message="YNAB edits directory not found"
            )

        edit_files = list(edit_dir.glob("*.json"))
        if not edit_files:
            return FlowResult(
                success=False,
                error_message="No YNAB edit files found"
            )

        # Apply the most recent edit file
        latest_edit = max(edit_files, key=lambda p: p.stat().st_mtime)

        return create_cli_executor(
            ynab_apply_cmd,
            edit_file=str(latest_edit),
            force=not context.interactive  # Auto-apply in non-interactive mode
        )(context)

    flow_registry.register_function_node(
        name="ynab_apply",
        func=ynab_apply_executor,
        dependencies=["split_generation"],
        change_detector=lambda ctx: (True, ["New splits to apply"])
    )

    # Register Retirement Account Updates Node
    flow_registry.register_function_node(
        name="retirement_update",
        func=create_cli_executor(
            retirement_update_cmd,
            interactive=True,
            date_str=None,
            output_file=None
        ),
        dependencies=["ynab_sync"],  # Needs YNAB data to read current balances
        change_detector=get_change_detector_function(change_detectors["retirement_update"])
    )

    # Register Cash Flow Analysis Node
    flow_registry.register_function_node(
        name="cash_flow_analysis",
        func=create_cli_executor(
            cashflow_analyze_cmd,
            accounts=(),
            exclude_before=None,
            output_dir=None,
            format="png",
            start=None,  # Provide default value for required parameter
            end=None     # Provide default value for required parameter
        ),
        dependencies=["ynab_sync"],
        change_detector=lambda ctx: (True, ["YNAB data updated"])
    )

    logger.info(f"Registered {len(flow_registry.get_all_nodes())} flow nodes")


@flow.command()
@click.option('--interactive/--non-interactive', default=True,
              help='Interactive mode with prompts (default) or automated execution')
@click.option('--start', help='Start date filter (YYYY-MM-DD)')
@click.option('--end', help='End date filter (YYYY-MM-DD)')
@click.option('--confidence-threshold', type=int, default=10000,
              help='Confidence threshold in basis points (default: 10000 = 100%)')
@click.option('--perf', is_flag=True, help='Enable performance metrics tracking')
@click.option('--dry-run', is_flag=True, help='Show execution plan without running')
@click.option('--force', is_flag=True, help='Force execution of all nodes')
@click.option('--nodes', multiple=True, help='Specific nodes to execute')
@click.option('--skip-archive', is_flag=True, help='Skip archive creation')
@click.option('--verbose', '-v', is_flag=True, help='Enable verbose output')
@click.pass_context
def go(ctx: click.Context, interactive: bool, start: Optional[str], end: Optional[str],
           confidence_threshold: int, perf: bool, dry_run: bool, force: bool,
           nodes: tuple, skip_archive: bool, verbose: bool) -> None:
    """
    Execute the complete Financial Flow System.

    Orchestrates the entire financial data pipeline from source ingestion
    through YNAB updates with intelligent dependency management and change
    detection.

    Examples:

      finances flow go

      finances flow go --dry-run --verbose

      finances flow go --nodes ynab_sync --nodes amazon_matching

      finances flow go --start 2024-07-01 --end 2024-07-31

      finances flow go --non-interactive --force
    """
    config = get_config()

    # Parse date range
    date_range = None
    if start or end:
        try:
            start_date = datetime.strptime(start, "%Y-%m-%d").date() if start else None
            end_date = datetime.strptime(end, "%Y-%m-%d").date() if end else None
            date_range = (start_date, end_date)
        except ValueError as e:
            raise click.ClickException(f"Invalid date format: {e}")

    # Setup flow nodes
    setup_flow_nodes()

    # Create flow context
    flow_context = FlowContext(
        start_time=datetime.now(),
        interactive=interactive,
        performance_tracking=perf,
        confidence_threshold=confidence_threshold,
        date_range=date_range,
        dry_run=dry_run,
        force=force,
        verbose=verbose or (ctx.obj and ctx.obj.get('verbose', False))
    )

    if verbose or (ctx.obj and ctx.obj.get('verbose', False)):
        click.echo("Financial Flow System Execution")
        click.echo(f"Mode: {'Interactive' if interactive else 'Non-interactive'}")
        click.echo(f"Execution: {'Dry run' if dry_run else 'Live execution'}")
        if date_range:
            click.echo(f"Date range: {start} to {end}")
        if nodes:
            click.echo(f"Target nodes: {', '.join(nodes)}")
        click.echo(f"Confidence threshold: {confidence_threshold / 100:.2f}%")
        click.echo()

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

        # Determine target nodes
        target_nodes = set(nodes) if nodes else None

        # Detect initial changes for preview
        if target_nodes is None:
            all_nodes = set(flow_registry.get_all_nodes().keys())
        else:
            all_nodes = target_nodes

        changes = engine.detect_changes(flow_context, all_nodes)
        initially_changed = set()
        change_summary = {}

        for node_name, (has_changes, reasons) in changes.items():
            if has_changes or force:
                initially_changed.add(node_name)
                if force:
                    change_summary[node_name] = ["Force execution requested"] + reasons
                else:
                    change_summary[node_name] = reasons

        if force:
            initially_changed.update(all_nodes)
            for node_name in all_nodes:
                if node_name not in change_summary:
                    change_summary[node_name] = ["Force execution requested"]

        potential_nodes = engine.dependency_graph.find_changed_subgraph(initially_changed)

        if not potential_nodes:
            click.echo("✅ No nodes need execution (no changes detected)")
            if not force:
                click.echo("Use --force flag to execute all nodes regardless of changes")
            return

        click.echo(f"Dynamic execution will process up to {len(potential_nodes)} nodes as dependencies allow:")

        # Show initially changed nodes
        if initially_changed:
            click.echo("\nInitially triggered nodes:")
            for node_name in sorted(initially_changed):
                node = flow_registry.get_node(node_name)
                display_name = node.get_display_name() if node else node_name
                click.echo(f"  • {display_name}")
                if node_name in change_summary:
                    for reason in change_summary[node_name]:
                        click.echo(f"    - {reason}")

        # Show potentially affected nodes
        downstream_nodes = potential_nodes - initially_changed
        if downstream_nodes:
            click.echo(f"\nPotentially affected downstream nodes: {len(downstream_nodes)}")

        if dry_run:
            click.echo("\n🏃 Dry run mode - no changes will be made")
            return

        # Confirm execution in interactive mode
        if interactive and not click.confirm("\nProceed with dynamic execution?"):
            click.echo("Execution cancelled.")
            return

        # Create transaction archive
        archive_session = None
        if not skip_archive:
            click.echo("\n📦 Creating transaction archive...")
            try:
                archive_session = create_flow_archive(
                    config.data_dir,
                    "flow_execution",
                    flow_context={
                        "execution_order": list(potential_nodes),
                        "change_summary": change_summary,
                        "interactive": interactive,
                        "force": force
                    }
                )
                flow_context.archive_manifest = {
                    domain: Path(manifest.archive_path)
                    for domain, manifest in archive_session.archives.items()
                }
                click.echo(f"✅ Archive created: {archive_session.total_files} files, {archive_session.total_size_bytes:,} bytes")
            except Exception as e:
                if not click.confirm(f"Archive creation failed: {e}\nContinue without archive?"):
                    raise click.ClickException("Execution aborted due to archive failure")

        # Execute flow
        click.echo("\n🚀 Executing flow...")
        start_time = datetime.now()

        executions = engine.execute_flow(flow_context, target_nodes)

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

        if perf:
            click.echo(f"Items processed: {summary['total_items_processed']}")
            if summary['total_execution_time_seconds']:
                click.echo(f"Node execution time: {summary['total_execution_time_seconds']:.1f} seconds")

        # Show detailed results
        if verbose:
            click.echo("\nDetailed Results:")
            for node_name, execution in executions.items():
                status_icon = {
                    "completed": "✅",
                    "failed": "❌",
                    "skipped": "⏭️",
                    "running": "🔄"
                }.get(execution.status.value, "❓")

                click.echo(f"{status_icon} {node_name}: {execution.status.value}")

                if execution.result:
                    if execution.result.error_message:
                        click.echo(f"    Error: {execution.result.error_message}")
                    if execution.result.items_processed > 0:
                        click.echo(f"    Items processed: {execution.result.items_processed}")

        # Show archive information
        if archive_session:
            click.echo(f"\n📦 Archive batch: {archive_session.session_id}")
            click.echo(f"Separate archives created for {len(archive_session.archives)} domains:")
            for domain, manifest in archive_session.archives.items():
                click.echo(f"  • {domain}: {manifest.files_archived} files ({manifest.archive_size_bytes:,} bytes)")

        # Show review items
        review_items = [
            execution for execution in executions.values()
            if execution.result and execution.result.requires_review
        ]

        if review_items:
            click.echo("\n🔍 Items requiring review:")
            for execution in review_items:
                click.echo(f"  • {execution.node_name}")
                if execution.result.review_instructions:
                    click.echo(f"    {execution.result.review_instructions}")

        # Final status
        if summary['failed'] > 0:
            click.echo("\n⚠️ Flow completed with errors")
            exit_code = 1
        else:
            click.echo("\n✅ Flow completed successfully")
            exit_code = 0

        if not interactive:
            click.echo("\nNon-interactive execution summary saved to flow execution log")

        exit(exit_code)

    except Exception as e:
        click.echo(f"\n❌ Flow execution failed: {e}", err=True)
        if verbose:
            import traceback
            click.echo(traceback.format_exc(), err=True)
        raise click.ClickException(str(e))


@flow.command()
@click.option('--verbose', '-v', is_flag=True, help='Enable verbose output')
@click.pass_context
def validate(ctx: click.Context, verbose: bool) -> None:
    """
    Validate the flow system configuration.

    Checks dependency graph for cycles, missing nodes, and other
    configuration issues.

    Example:
      finances flow validate
    """
    setup_flow_nodes()

    if verbose or (ctx.obj and ctx.obj.get('verbose', False)):
        click.echo("Flow System Validation")
        click.echo()

    try:
        engine = FlowExecutionEngine()
        validation_errors = engine.validate_flow()

        if validation_errors:
            click.echo("❌ Flow validation failed:")
            for error in validation_errors:
                click.echo(f"  • {error}")
            raise click.ClickException("Flow validation failed")

        click.echo("✅ Flow validation passed")

        # Show flow graph information
        all_nodes = flow_registry.get_all_nodes()
        click.echo(f"Registered nodes: {len(all_nodes)}")

        if verbose:
            dependency_graph = engine.dependency_graph
            execution_levels = dependency_graph.get_execution_levels()

            click.echo(f"Execution levels: {len(execution_levels)}")
            for level, nodes in enumerate(execution_levels):
                click.echo(f"  Level {level + 1}: {', '.join(nodes)}")

    except Exception as e:
        click.echo(f"❌ Validation error: {e}", err=True)
        raise click.ClickException(str(e))


@flow.command()
@click.option('--format', 'output_format', type=click.Choice(['text', 'json']),
              default='text', help='Output format')
@click.option('--verbose', '-v', is_flag=True, help='Enable verbose output')
@click.pass_context
def graph(ctx: click.Context, output_format: str, verbose: bool) -> None:
    """
    Display the flow dependency graph.

    Shows the complete dependency graph with execution order and
    relationship information.

    Examples:
      finances flow graph
      finances flow graph --format json
    """
    setup_flow_nodes()

    try:
        engine = FlowExecutionEngine()
        all_nodes = flow_registry.get_all_nodes()
        dependency_graph = engine.dependency_graph

        if output_format == 'json':
            # JSON output
            graph_data = {
                "nodes": {},
                "execution_levels": dependency_graph.get_execution_levels()
            }

            for node_name, node in all_nodes.items():
                graph_data["nodes"][node_name] = {
                    "display_name": node.get_display_name(),
                    "dependencies": list(node.dependencies)
                }

            click.echo(json.dumps(graph_data, indent=2))

        else:
            # Text output
            click.echo("Financial Flow System Dependency Graph")
            click.echo("=" * 45)

            execution_levels = dependency_graph.get_execution_levels()

            click.echo(f"Total nodes: {len(all_nodes)}")
            click.echo(f"Execution levels: {len(execution_levels)}")
            click.echo()

            for level, nodes in enumerate(execution_levels):
                click.echo(f"Level {level + 1}:")
                for node_name in nodes:
                    node = all_nodes[node_name]
                    display_name = node.get_display_name()
                    dependencies = list(node.dependencies)

                    if dependencies:
                        dep_str = f" (depends on: {', '.join(dependencies)})"
                    else:
                        dep_str = " (no dependencies)"

                    click.echo(f"  • {display_name}{dep_str}")
                click.echo()

    except Exception as e:
        click.echo(f"❌ Error generating graph: {e}", err=True)
        raise click.ClickException(str(e))


if __name__ == '__main__':
    flow()