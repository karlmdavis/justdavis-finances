#!/usr/bin/env python3
"""
Main CLI Entry Point for Davis Family Finances

Provides unified command-line interface for all financial management tools.
"""


import click

from ..core.config import get_config


@click.group()
@click.option(
    "--config-env",
    type=click.Choice(["development", "test", "production"]),
    help="Override environment configuration",
)
@click.option("--verbose", "-v", is_flag=True, help="Enable verbose output")
@click.option("--debug", is_flag=True, help="Enable debug logging")
@click.pass_context
def main(ctx: click.Context, config_env: str | None, verbose: bool, debug: bool) -> None:
    """
    Davis Family Finances - Professional Financial Management System

    A comprehensive system for automated transaction matching, receipt processing,
    and financial analysis with YNAB integration.
    """
    # Ensure context object exists
    ctx.ensure_object(dict)

    # Set environment if specified
    if config_env:
        import os

        os.environ["FINANCES_ENV"] = config_env

    # Configure debug logging if requested
    if debug:
        import logging
        import os

        os.environ["LOG_LEVEL"] = "DEBUG"
        logging.getLogger().setLevel(logging.DEBUG)
        logging.getLogger("finances").setLevel(logging.DEBUG)

    # Store global options
    ctx.obj["verbose"] = verbose
    ctx.obj["debug"] = debug
    ctx.obj["config"] = get_config()

    if verbose:
        click.echo(f"Environment: {ctx.obj['config'].environment.value}")
        click.echo(f"Data directory: {ctx.obj['config'].data_dir}")

    if debug:
        click.echo("Debug logging enabled")


@main.command()
@click.pass_context
def version(ctx: click.Context) -> None:
    """Show version information."""
    from finances import __author__, __version__

    click.echo(f"Davis Family Finances v{__version__}")
    click.echo(f"Author: {__author__}")


@main.command()
@click.pass_context
def config(ctx: click.Context) -> None:
    """Show current configuration."""
    config_obj = ctx.obj["config"]

    click.echo("Current Configuration:")
    click.echo(f"  Environment: {config_obj.environment.value}")
    click.echo(f"  Data Directory: {config_obj.data_dir}")
    click.echo(f"  Cache Directory: {config_obj.cache_dir}")
    click.echo(f"  Output Directory: {config_obj.output_dir}")
    click.echo(f"  Debug Mode: {config_obj.debug}")
    click.echo(f"  Log Level: {config_obj.log_level}")


# Import flow command
from .flow import flow  # noqa: E402

# Register flow command (the unified interface for all operations)
main.add_command(flow)


if __name__ == "__main__":
    main()
