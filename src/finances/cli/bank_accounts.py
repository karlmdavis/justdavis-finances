"""CLI commands for bank account reconciliation."""

from pathlib import Path

import click

from finances.bank_accounts.config import load_config

# Import all format handlers
from finances.bank_accounts.format_handlers.apple_card_csv import AppleCardCsvHandler
from finances.bank_accounts.format_handlers.apple_card_ofx import AppleCardOfxHandler
from finances.bank_accounts.format_handlers.apple_savings_csv import AppleSavingsCsvHandler
from finances.bank_accounts.format_handlers.apple_savings_ofx import AppleSavingsOfxHandler
from finances.bank_accounts.format_handlers.chase_checking_csv import ChaseCheckingCsvHandler
from finances.bank_accounts.format_handlers.chase_credit_csv import ChaseCreditCsvHandler
from finances.bank_accounts.format_handlers.chase_credit_qif import ChaseCreditQifHandler
from finances.bank_accounts.format_handlers.registry import FormatHandlerRegistry
from finances.bank_accounts.matching import YnabTransaction
from finances.bank_accounts.nodes.parse import parse_account_data
from finances.bank_accounts.nodes.reconcile import reconcile_account_data
from finances.bank_accounts.nodes.retrieve import retrieve_account_data


def create_format_handler_registry() -> FormatHandlerRegistry:
    """Create and populate format handler registry with all available handlers."""
    registry = FormatHandlerRegistry()

    # Register all handlers
    registry.register(AppleCardCsvHandler)
    registry.register(AppleCardOfxHandler)
    registry.register(AppleSavingsCsvHandler)
    registry.register(AppleSavingsOfxHandler)
    registry.register(ChaseCheckingCsvHandler)
    registry.register(ChaseCreditCsvHandler)
    registry.register(ChaseCreditQifHandler)

    return registry


@click.group()
def bank() -> None:
    """Bank account reconciliation commands."""
    pass


@bank.command()
@click.option(
    "--config",
    type=click.Path(exists=True, path_type=Path),
    default=Path.home() / ".finances" / "bank_accounts_config.json",
    help="Path to bank accounts configuration file",
)
@click.option(
    "--base-dir",
    type=click.Path(path_type=Path),
    default=Path("data/bank_accounts"),
    help="Base directory for bank account data",
)
def retrieve(config: Path, base_dir: Path) -> None:
    """Copy bank export files from source directories to raw/.

    This command:
    - Reads your bank accounts configuration
    - Copies new files from download locations to data/bank_accounts/raw/
    - Skips files that already exist (based on name and size)
    - Displays summary of files copied per account

    Example:

        finances bank retrieve
        finances bank retrieve --config ~/my-config.json
    """
    try:
        # Load config
        click.echo(f"Loading configuration from {config}...")
        bank_config = load_config(config)
        click.echo(f"  Found {len(bank_config.accounts)} accounts\n")

        # Call retrieve_account_data()
        click.echo("Retrieving bank export files...")
        summary = retrieve_account_data(bank_config, base_dir)

        # Display summary
        click.echo("\nRetrieval Summary:")
        for account_slug, stats in summary.items():
            click.echo(f"  {account_slug}:")
            click.echo(f"    Files copied: {stats['files_copied']}")
            click.echo(f"    Files skipped: {stats['files_skipped']}")

        total_copied = sum(s["files_copied"] for s in summary.values())
        total_skipped = sum(s["files_skipped"] for s in summary.values())
        click.echo(f"\nTotal: {total_copied} copied, {total_skipped} skipped")

        click.echo("\nDone! account_data_retrieve completed")

    except FileNotFoundError as e:
        raise click.ClickException(str(e)) from e
    except Exception as e:
        raise click.ClickException(f"Retrieval failed: {e}") from e


@bank.command()
@click.option(
    "--config",
    type=click.Path(exists=True, path_type=Path),
    default=Path.home() / ".finances" / "bank_accounts_config.json",
    help="Path to bank accounts configuration file",
)
@click.option(
    "--base-dir",
    type=click.Path(path_type=Path),
    default=Path("data/bank_accounts"),
    help="Base directory for bank account data",
)
def parse(config: Path, base_dir: Path) -> None:
    """Parse raw bank files into normalized JSON.

    This command:
    - Reads raw bank export files from data/bank_accounts/raw/
    - Parses using appropriate format handlers (CSV, OFX, QIF)
    - De-duplicates overlapping transactions and balances
    - Writes normalized JSON to data/bank_accounts/normalized/

    Example:

        finances bank parse
        finances bank parse --base-dir custom/path
    """
    try:
        # Load config
        click.echo(f"Loading configuration from {config}...")
        bank_config = load_config(config)
        click.echo(f"  Found {len(bank_config.accounts)} accounts\n")

        # Create format handler registry
        registry = create_format_handler_registry()
        click.echo(f"Registered {len(registry.list_formats())} format handlers\n")

        # Call parse_account_data()
        click.echo("Parsing bank export files...")
        summary = parse_account_data(bank_config, base_dir, registry)

        # Display summary
        click.echo("\nParsing Summary:")
        for account_slug, stats in summary.items():
            click.echo(f"  {account_slug}:")
            click.echo(f"    Transactions: {stats['transaction_count']}")
            click.echo(f"    Date range: {stats['date_range']}")

        total_transactions = sum(s["transaction_count"] for s in summary.values())
        click.echo(f"\nTotal transactions parsed: {total_transactions}")

        click.echo("\nDone! account_data_parse completed")

    except FileNotFoundError as e:
        raise click.ClickException(str(e)) from e
    except Exception as e:
        raise click.ClickException(f"Parsing failed: {e}") from e


@bank.command()
@click.option(
    "--config",
    type=click.Path(exists=True, path_type=Path),
    default=Path.home() / ".finances" / "bank_accounts_config.json",
    help="Path to bank accounts configuration file",
)
@click.option(
    "--base-dir",
    type=click.Path(path_type=Path),
    default=Path("data/bank_accounts"),
    help="Base directory for bank account data",
)
def reconcile(config: Path, base_dir: Path) -> None:
    """Reconcile bank data with YNAB transactions.

    This command:
    - Loads normalized bank data
    - Matches bank transactions with YNAB transactions
    - Generates operations for unmatched transactions
    - Performs balance reconciliation
    - Writes operations JSON to data/bank_accounts/reconciliation/

    Example:

        finances bank reconcile

    Note: YNAB transaction loading is not yet implemented.
    This command currently generates operations for all bank transactions.
    """
    try:
        # Load config
        click.echo(f"Loading configuration from {config}...")
        bank_config = load_config(config)
        click.echo(f"  Found {len(bank_config.accounts)} accounts\n")

        # Load YNAB transactions (stub for now - empty list)
        click.echo("Loading YNAB transactions...")
        click.echo("  Note: YNAB transaction loading not yet implemented")
        click.echo("  Using empty YNAB transaction list (all bank txs will be unmatched)\n")
        ynab_transactions: list[YnabTransaction] = []

        # Call reconcile_account_data()
        click.echo("Reconciling bank data with YNAB...")
        operations_file = reconcile_account_data(bank_config, base_dir, ynab_transactions)

        # Display operations file path
        click.echo("\nReconciliation complete!")
        click.echo(f"Operations file: {operations_file}")
        click.echo("\nNext steps:")
        click.echo("  1. Review the operations file")
        click.echo("  2. Import missing transactions into YNAB")
        click.echo("  3. Resolve flagged discrepancies")

        click.echo("\nDone! account_data_reconcile completed")

    except FileNotFoundError as e:
        raise click.ClickException(str(e)) from e
    except Exception as e:
        raise click.ClickException(f"Reconciliation failed: {e}") from e
